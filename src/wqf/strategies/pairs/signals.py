"""Geração de sinais long/short de Pairs Trading integrada ao backtest comum (Issue #14).

Fluxo: barras diárias (``MarketBar``, as mesmas consumidas pelo motor da #9) ->
spread e z-score da #5 (janela estritamente passada) -> máquina de estados com
regras explícitas de entrada/saída -> ``TargetSignal`` em quantidades inteiras.

Convenções (provisórias, sujeitas à governança do fundo):

* **Temporalidade:** o z-score de uma sessão usa apenas fechamentos até ela,
  inclusive. A decisão ocorre no fechamento e o motor executa na abertura da
  sessão seguinte. Nenhuma decisão é tomada na última sessão (não há execução).
* **Lacunas:** o calendário é o conjunto de sessões presentes nas barras. Se
  uma perna não tiver barra numa sessão, não há decisão nessa sessão e a janela
  do z-score recomeça do zero (não se "pula" a lacuna). Lacuna com o par aberto
  gera erro explícito: o par não pode ser marcado nem encerrado com segurança.
* **Custos e NAV:** este módulo não calcula custo, caixa nem patrimônio; isso é
  responsabilidade exclusiva de ``wqf.backtest.engine.run_backtest``.

Protótipo de pesquisa: não equivale à aprovação da estratégia para operação.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

from wqf.backtest.costs import CostRates
from wqf.backtest.engine import MarketBar, TargetSignal, run_backtest
from wqf.backtest.ledger import BacktestResult
from wqf.strategies.pairs.spread import (
    VALID_SPREAD_METHODS,
    SpreadMethod,
    calculate_spread,
    compute_rolling_zscore,
)

PairState = Literal["flat", "long_spread", "short_spread"]
PairAction = Literal[
    "none",
    "enter_long_spread",
    "enter_short_spread",
    "exit_mean",
    "exit_stop",
    "exit_time",
    "gap",
    "end_of_data",
]


def _finite(value: float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class PairsSignalConfig:
    """Parâmetros de um par. Limiares em unidades de desvio-padrão do spread.

    - ``long_spread`` (z <= -entry_z): compra A e vende B.
    - ``short_spread`` (z >= entry_z): vende A e compra B.
    - Saída pela média quando |z| volta para dentro de ``exit_z``.
    - ``stop_z`` (opcional): encerra se o spread divergir ainda mais. Após um
      stop, nova entrada só depois que |z| voltar para baixo de ``entry_z``.
    - ``max_holding_sessions`` (opcional): encerra após N sessões com o par aberto.

    Dimensionamento: a perna A recebe ``leg_notional_brl`` e a perna B recebe
    ``leg_notional_brl * hedge_ratio`` (para ``price_ratio`` o hedge é 1). No método
    ``hedge_diff``, ``hedge_ratio`` é razão de ações: qtd_B = round(qtd_A * hedge).
    As quantidades usam o fechamento da sessão de decisão e ficam fixas até a saída.
    """

    asset_a: str
    asset_b: str
    leg_notional_brl: Decimal
    window: int = 20
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float | None = None
    max_holding_sessions: int | None = None
    method: SpreadMethod = "log_ratio"
    hedge_ratio: float = 1.0
    ddof: int = 1
    strategy: str | None = None

    def __post_init__(self) -> None:
        for name in ("asset_a", "asset_b"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} deve ser um ticker não vazio")
        if self.asset_a == self.asset_b:
            raise ValueError("asset_a e asset_b devem ser ativos diferentes")
        if (
            not isinstance(self.leg_notional_brl, Decimal)
            or not self.leg_notional_brl.is_finite()
            or self.leg_notional_brl <= 0
        ):
            raise ValueError("leg_notional_brl deve ser Decimal finito e positivo")
        if type(self.window) is not int or self.window < 2:
            raise ValueError("window deve ser inteiro >= 2")
        if self.ddof not in (0, 1) or self.window <= self.ddof:
            raise ValueError("ddof deve ser 0 ou 1 e menor que window")
        if not _finite(self.entry_z) or not _finite(self.exit_z):
            raise ValueError("entry_z e exit_z devem ser números finitos")
        if not 0 <= self.exit_z < self.entry_z:
            raise ValueError("É preciso 0 <= exit_z < entry_z")
        if self.stop_z is not None and (not _finite(self.stop_z) or self.stop_z <= self.entry_z):
            raise ValueError("stop_z deve ser finito e maior que entry_z")
        if self.max_holding_sessions is not None and (
            type(self.max_holding_sessions) is not int or self.max_holding_sessions < 1
        ):
            raise ValueError("max_holding_sessions deve ser inteiro >= 1")
        if self.method not in VALID_SPREAD_METHODS:
            raise ValueError(f"Método de spread inválido: {self.method!r}")
        if not _finite(self.hedge_ratio) or self.hedge_ratio <= 0:
            raise ValueError("hedge_ratio deve ser finito e positivo")
        if self.strategy is not None and (
            not isinstance(self.strategy, str) or not self.strategy.strip()
        ):
            raise ValueError("strategy, se informado, não pode ser vazio")

    @property
    def strategy_id(self) -> str:
        """Identificador no motor. Por padrão é único por par, para não sobrescrever
        os alvos de outro par que compartilhe um ativo."""
        return self.strategy or f"pairs:{self.asset_a}-{self.asset_b}"


@dataclass(frozen=True)
class PairDecision:
    """Registro auditável de cada sessão do calendário."""

    session: date
    z_score: float | None
    state_before: PairState
    state_after: PairState
    action: PairAction
    target_a: int
    target_b: int


@dataclass(frozen=True)
class PairsSignalReport:
    signals: tuple[TargetSignal, ...]
    decisions: tuple[PairDecision, ...]


def _leg_quantities(
    config: PairsSignalConfig, price_a: Decimal, price_b: Decimal
) -> tuple[int, int]:
    """Quantidades absolutas (inteiras) de cada perna no fechamento da decisão."""
    qty_a = int((config.leg_notional_brl / price_a).to_integral_value(rounding=ROUND_DOWN))
    hedge = Decimal(str(config.hedge_ratio))
    if config.method == "hedge_diff":
        qty_b = int((qty_a * hedge).to_integral_value(rounding=ROUND_HALF_UP))
    else:
        notional_b = config.leg_notional_brl * (hedge if config.method == "log_ratio" else 1)
        qty_b = int((notional_b / price_b).to_integral_value(rounding=ROUND_DOWN))
    if qty_a == 0 or qty_b == 0:
        raise ValueError(
            "leg_notional_brl insuficiente para comprar 1 ação de cada perna "
            f"(A={price_a}, B={price_b})"
        )
    return qty_a, qty_b


def _closes_by_session(
    bars: Iterable[MarketBar], assets: tuple[str, str]
) -> tuple[list[date], dict[date, dict[str, Decimal]]]:
    sessions: set[date] = set()
    closes: dict[date, dict[str, Decimal]] = {}
    for bar in bars:
        if not isinstance(bar, MarketBar):
            raise TypeError("bars deve conter instâncias de MarketBar")
        sessions.add(bar.session)
        if bar.asset not in assets:
            continue
        by_asset = closes.setdefault(bar.session, {})
        if bar.asset in by_asset:
            raise ValueError(f"Barra repetida: {bar.session} {bar.asset}")
        by_asset[bar.asset] = bar.close_price
    return sorted(sessions), closes


def _rolling_z_by_session(
    config: PairsSignalConfig,
    sessions: list[date],
    closes: Mapping[date, Mapping[str, Decimal]],
) -> dict[date, float | None]:
    """Aplica o z-score da #5 a cada trecho contíguo sem lacunas do calendário."""
    z_by_session: dict[date, float | None] = {}
    segment: list[date] = []

    def flush() -> None:
        if not segment:
            return
        spreads = [
            calculate_spread(
                float(closes[day][config.asset_a]),
                float(closes[day][config.asset_b]),
                method=config.method,
                hedge_ratio=config.hedge_ratio,
            )
            for day in segment
        ]
        stats = compute_rolling_zscore(spreads, window=config.window, ddof=config.ddof)
        for day, stat in zip(segment, stats, strict=True):
            z_by_session[day] = stat.z_score
        segment.clear()

    for session in sessions:
        prices = closes.get(session, {})
        if config.asset_a in prices and config.asset_b in prices:
            segment.append(session)
        else:
            flush()
    flush()
    return z_by_session


def generate_pairs_signals(
    bars: Iterable[MarketBar], config: PairsSignalConfig
) -> PairsSignalReport:
    """Gera os ``TargetSignal`` do par a partir das barras do backtest.

    Sinais só são emitidos quando o alvo muda (entrada ou saída), um por perna.
    """
    if not isinstance(config, PairsSignalConfig):
        raise TypeError("config deve ser PairsSignalConfig")
    assets = (config.asset_a, config.asset_b)
    sessions, closes = _closes_by_session(bars, assets)
    z_by_session = _rolling_z_by_session(config, sessions, closes)
    strategy = config.strategy_id

    state: PairState = "flat"
    target_a = target_b = 0
    entry_index = 0
    cooldown = False
    signals: list[TargetSignal] = []
    decisions: list[PairDecision] = []

    for index, session in enumerate(sessions):
        before = state
        if session not in z_by_session:
            if state != "flat":
                missing = sorted(set(assets) - set(closes.get(session, {})))
                raise ValueError(
                    f"Lacuna de preço em {session} para {missing} com o par aberto "
                    f"({state}); o par não pode ser marcado nem encerrado."
                )
            decisions.append(PairDecision(session, None, before, state, "gap", 0, 0))
            continue

        z = z_by_session[session]
        if index == len(sessions) - 1:
            decisions.append(
                PairDecision(session, z, before, state, "end_of_data", target_a, target_b)
            )
            continue

        action: PairAction = "none"
        if state == "flat":
            if cooldown and z is not None and abs(z) < config.entry_z:
                cooldown = False
            if z is not None and not cooldown:
                if z >= config.entry_z:
                    action = "enter_short_spread"
                elif z <= -config.entry_z:
                    action = "enter_long_spread"
        elif z is not None:
            # Sinal positivo = spread acima da média; long_spread espera o spread subir.
            signed = z if state == "long_spread" else -z
            if config.stop_z is not None and signed <= -config.stop_z:
                action = "exit_stop"
            elif signed >= -config.exit_z:
                action = "exit_mean"
        if (
            action == "none"
            and state != "flat"
            and config.max_holding_sessions is not None
            and index - entry_index >= config.max_holding_sessions
        ):
            action = "exit_time"

        if action.startswith("enter"):
            prices = closes[session]
            qty_a, qty_b = _leg_quantities(config, prices[config.asset_a], prices[config.asset_b])
            if action == "enter_long_spread":
                state, target_a, target_b = "long_spread", qty_a, -qty_b
            else:
                state, target_a, target_b = "short_spread", -qty_a, qty_b
            entry_index = index
        elif action.startswith("exit"):
            state, target_a, target_b = "flat", 0, 0
            cooldown = action == "exit_stop"

        if action != "none":
            signals.append(TargetSignal(session, session, strategy, config.asset_a, target_a))
            signals.append(TargetSignal(session, session, strategy, config.asset_b, target_b))
        decisions.append(PairDecision(session, z, before, state, action, target_a, target_b))

    return PairsSignalReport(signals=tuple(signals), decisions=tuple(decisions))


def run_pairs_backtest(
    bars: Iterable[MarketBar],
    config: PairsSignalConfig,
    *,
    starting_cash: Decimal,
    rates: CostRates,
    cash_interval_rates: Mapping[date, Decimal] | None = None,
) -> tuple[PairsSignalReport, BacktestResult]:
    """Gera os sinais e simula no motor comum, que é o único a calcular custos e NAV."""
    bars = tuple(bars)
    report = generate_pairs_signals(bars, config)
    result = run_backtest(
        bars,
        report.signals,
        starting_cash=starting_cash,
        rates=rates,
        cash_interval_rates=cash_interval_rates,
    )
    return report, result


def load_pairs_config(
    path: str | Path, *, asset_a: str, asset_b: str, **overrides: object
) -> PairsSignalConfig:
    """Lê os parâmetros de referência em ``[strategies.pairs]`` de ``config/parametros.toml``.

    ``leg_notional_brl`` é gravado como string para preservar o Decimal exato.
    ``overrides`` permite trocar qualquer campo (ex.: ``hedge_ratio`` estimado para o par).
    """
    with Path(path).open("rb") as config_file:
        raw = dict(tomllib.load(config_file)["strategies"]["pairs"])
    if "leg_notional_brl" in raw:
        raw["leg_notional_brl"] = Decimal(str(raw["leg_notional_brl"]))
    raw.update(overrides)
    return PairsSignalConfig(asset_a=asset_a, asset_b=asset_b, **raw)
