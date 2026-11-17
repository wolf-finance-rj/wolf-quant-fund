"""Geração de sinais long/short de Pairs Trading para o backtest comum (Issue #14).

Fluxo: barras diárias (``MarketBar``, as mesmas do motor da #9) -> spread e
z-score da #5 -> regras de entrada/saída -> ``TargetSignal`` por perna.

* O z-score de uma sessão usa apenas fechamentos até ela (janela passada da #5).
  A decisão é no fechamento; o motor executa na abertura da sessão seguinte.
  Não há decisão na última sessão, pois não haveria execução.
* Sessão sem preço de uma perna: não há decisão e a janela do z-score recomeça.
  Lacuna com o par aberto gera erro explícito.
* Custos, caixa e NAV são calculados somente por ``wqf.backtest.engine.run_backtest``.

Protótipo de pesquisa: não equivale à ativação da estratégia.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from wqf.backtest.engine import MarketBar, TargetSignal
from wqf.strategies.pairs.spread import (
    VALID_SPREAD_METHODS,
    SpreadMethod,
    calculate_spread,
    compute_rolling_zscore,
)


@dataclass(frozen=True)
class PairsSignalConfig:
    """Parâmetros do par. Limiares em desvios-padrão do spread.

    - z >= ``entry_z``: vende A e compra B (short spread).
    - z <= -``entry_z``: compra A e vende B (long spread).
    - Encerra o par quando o spread volta à média: z <= ``exit_z`` no short
      spread e z >= -``exit_z`` no long spread.
    - Cada perna recebe ``leg_notional_brl``; as quantidades inteiras são
      calculadas com o fechamento da sessão de decisão.
    """

    asset_a: str
    asset_b: str
    leg_notional_brl: Decimal
    window: int = 20
    entry_z: float = 2.0
    exit_z: float = 0.5
    method: SpreadMethod = "log_ratio"
    hedge_ratio: float = 1.0
    strategy: str = "pairs"

    def __post_init__(self) -> None:
        if not self.asset_a.strip() or not self.asset_b.strip():
            raise ValueError("asset_a e asset_b devem ser tickers não vazios")
        if self.asset_a == self.asset_b:
            raise ValueError("asset_a e asset_b devem ser ativos diferentes")
        if not self.strategy.strip():
            raise ValueError("strategy não pode ser vazio")
        if (
            not isinstance(self.leg_notional_brl, Decimal)
            or not self.leg_notional_brl.is_finite()
            or self.leg_notional_brl <= 0
        ):
            raise ValueError("leg_notional_brl deve ser Decimal finito e positivo")
        if type(self.window) is not int or self.window < 2:
            raise ValueError("window deve ser inteiro >= 2")
        if not (math.isfinite(self.entry_z) and math.isfinite(self.exit_z)):
            raise ValueError("entry_z e exit_z devem ser finitos")
        if not 0 <= self.exit_z < self.entry_z:
            raise ValueError("É preciso 0 <= exit_z < entry_z")
        if self.method not in VALID_SPREAD_METHODS:
            raise ValueError(f"Método de spread inválido: {self.method!r}")


def _closes(
    bars: Iterable[MarketBar], assets: tuple[str, str]
) -> tuple[list[date], dict[date, dict[str, Decimal]]]:
    """Calendário (todas as sessões das barras) e fechamentos das duas pernas."""
    sessions: set[date] = set()
    closes: dict[date, dict[str, Decimal]] = {}
    for bar in bars:
        sessions.add(bar.session)
        if bar.asset not in assets:
            continue
        by_asset = closes.setdefault(bar.session, {})
        if bar.asset in by_asset:
            raise ValueError(f"Barra repetida: {bar.session} {bar.asset}")
        by_asset[bar.asset] = bar.close_price
    return sorted(sessions), closes


def _z_scores(
    config: PairsSignalConfig,
    sessions: list[date],
    closes: dict[date, dict[str, Decimal]],
) -> dict[date, float | None]:
    """z-score da #5 por sessão, calculado em trechos contíguos sem lacunas."""
    z_by_session: dict[date, float | None] = {}
    segment: list[date] = []

    def flush() -> None:
        spreads = [
            calculate_spread(
                float(closes[day][config.asset_a]),
                float(closes[day][config.asset_b]),
                method=config.method,
                hedge_ratio=config.hedge_ratio,
            )
            for day in segment
        ]
        for day, stat in zip(
            segment, compute_rolling_zscore(spreads, window=config.window), strict=True
        ):
            z_by_session[day] = stat.z_score
        segment.clear()

    for session in sessions:
        if {config.asset_a, config.asset_b} <= closes.get(session, {}).keys():
            segment.append(session)
        else:
            flush()
    flush()
    return z_by_session


def _quantity(notional: Decimal, price: Decimal) -> int:
    quantity = int((notional / price).to_integral_value(rounding=ROUND_DOWN))
    if quantity == 0:
        raise ValueError(f"leg_notional_brl insuficiente para 1 ação a {price}")
    return quantity


def generate_pairs_signals(
    bars: Iterable[MarketBar], config: PairsSignalConfig
) -> list[TargetSignal]:
    """Gera os ``TargetSignal`` do par; emite um por perna quando o alvo muda."""
    assets = (config.asset_a, config.asset_b)
    sessions, closes = _closes(bars, assets)
    z_by_session = _z_scores(config, sessions, closes)

    target_a = target_b = 0
    signals: list[TargetSignal] = []
    for session in sessions[:-1]:  # a última sessão não tem execução seguinte
        is_open = target_a != 0
        if session not in z_by_session:
            if is_open:
                raise ValueError(f"Lacuna de preço em {session} com o par {assets} aberto")
            continue
        z = z_by_session[session]
        if z is None:
            continue

        if not is_open and abs(z) >= config.entry_z:
            prices = closes[session]
            qty_a = _quantity(config.leg_notional_brl, prices[config.asset_a])
            qty_b = _quantity(config.leg_notional_brl, prices[config.asset_b])
            direction = -1 if z > 0 else 1  # z alto: A caro -> vende A, compra B
            target_a, target_b = direction * qty_a, -direction * qty_b
        elif is_open and (z <= config.exit_z if target_a < 0 else z >= -config.exit_z):
            target_a = target_b = 0
        else:
            continue

        signals.append(TargetSignal(session, session, config.strategy, config.asset_a, target_a))
        signals.append(TargetSignal(session, session, config.strategy, config.asset_b, target_b))
    return signals
