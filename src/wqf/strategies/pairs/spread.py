"""Cálculo de alinhamento temporal, spread e z-score para Pairs Trading (Issue #5)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

SpreadMethod = Literal["log_ratio", "price_ratio", "hedge_diff"]
VALID_SPREAD_METHODS: set[str] = {"log_ratio", "price_ratio", "hedge_diff"}


@dataclass(frozen=True)
class PricePoint:
    """Representa uma cotação diária de um ativo."""

    trading_date: date
    price: float


@dataclass(frozen=True)
class AlignedPairPoint:
    """Representa as cotações alinhadas de dois ativos na mesma data."""

    trading_date: date
    price_a: float
    price_b: float


@dataclass(frozen=True)
class RollingZScorePoint:
    """Representa as estatísticas em janela móvel passada e o z-score de um ponto."""

    spread: float
    rolling_mean: float | None
    rolling_std: float | None
    z_score: float | None


@dataclass(frozen=True)
class PairSpreadPoint:
    """Representa a análise completa do par em uma data específica."""

    trading_date: date
    price_a: float
    price_b: float
    spread: float
    rolling_mean: float | None
    rolling_std: float | None
    z_score: float | None


def _validate_series(series: Sequence[PricePoint], label: str) -> dict[date, float]:
    """Valida uma série de preços e retorna um dicionário indexado por data."""
    seen_dates: dict[date, float] = {}
    for point in series:
        if point.trading_date in seen_dates:
            raise ValueError(f"Data duplicada detectada na série '{label}': {point.trading_date}")
        if math.isnan(point.price) or math.isinf(point.price) or point.price <= 0:
            raise ValueError(
                f"Preço inválido na série '{label}' em {point.trading_date}: {point.price}. "
                "Preços devem ser finitos e estritamente positivos (> 0)."
            )
        seen_dates[point.trading_date] = float(point.price)
    return seen_dates


def align_pair_prices(
    series_a: Sequence[PricePoint],
    series_b: Sequence[PricePoint],
) -> list[AlignedPairPoint]:
    """Alinha duas séries de preços pelas datas em comum em ordem cronológica.

    Datas presentes em apenas uma das séries são descartadas para evitar comparações
    assíncronas. Preços inválidos (<= 0, NaN, Inf) ou datas duplicadas na mesma série
    disparam ValueError explícito.
    """
    map_a = _validate_series(series_a, label="asset_a")
    map_b = _validate_series(series_b, label="asset_b")

    common_dates = sorted(map_a.keys() & map_b.keys())
    return [
        AlignedPairPoint(
            trading_date=d,
            price_a=map_a[d],
            price_b=map_b[d],
        )
        for d in common_dates
    ]


def calculate_spread(
    price_a: float,
    price_b: float,
    method: SpreadMethod = "log_ratio",
    hedge_ratio: float = 1.0,
) -> float:
    """Calcula o spread entre dois preços conforme método parametrizável.

    Métodos suportados:
    - 'log_ratio': ln(price_a) - hedge_ratio * ln(price_b)
    - 'price_ratio': price_a / price_b
    - 'hedge_diff': price_a - hedge_ratio * price_b
    """
    if method not in VALID_SPREAD_METHODS:
        raise ValueError(
            f"Método de spread inválido: '{method}'. Opções: {sorted(VALID_SPREAD_METHODS)}"
        )
    if price_a <= 0 or price_b <= 0 or math.isnan(price_a) or math.isnan(price_b):
        raise ValueError("Os preços devem ser finitos e estritamente positivos (> 0).")
    if math.isnan(hedge_ratio) or math.isinf(hedge_ratio) or hedge_ratio <= 0:
        raise ValueError("O hedge_ratio deve ser finito e estritamente positivo (> 0).")

    if method == "log_ratio":
        return math.log(price_a) - hedge_ratio * math.log(price_b)
    if method == "price_ratio":
        return price_a / price_b
    return price_a - hedge_ratio * price_b


def compute_rolling_zscore(
    spreads: Sequence[float],
    window: int,
    ddof: int = 1,
    min_std_epsilon: float = 1e-12,
) -> list[RollingZScorePoint]:
    """Calcula média móvel, desvio-padrão e z-score usando estritamente janela passada.

    Para evitar look-ahead bias, o cálculo no índice t utiliza apenas observações
    no intervalo [t - window + 1, t].
    - Enquanto não houver histórico suficiente (t < window - 1), retorna None nas estatísticas.
    - Se o desvio-padrão na janela for zero (ou <= min_std_epsilon), z_score retorna None
      para evitar divisão por zero ou sinais falsos por ruído numérico.
    """
    if window < 2:
        raise ValueError("O tamanho da janela (window) deve ser pelo menos 2.")
    if ddof not in (0, 1) or window <= ddof:
        raise ValueError("Parâmetro ddof inválido para o tamanho da janela informado.")

    results: list[RollingZScorePoint] = []
    spread_list = [float(s) for s in spreads]

    for idx, current_spread in enumerate(spread_list):
        if math.isnan(current_spread) or math.isinf(current_spread):
            raise ValueError(f"Valor de spread inválido na posição {idx}: {current_spread}")

        if idx < window - 1:
            results.append(
                RollingZScorePoint(
                    spread=current_spread,
                    rolling_mean=None,
                    rolling_std=None,
                    z_score=None,
                )
            )
            continue

        window_slice = spread_list[idx - window + 1 : idx + 1]
        mean_val = sum(window_slice) / window
        variance = sum((x - mean_val) ** 2 for x in window_slice) / (window - ddof)
        std_val = math.sqrt(variance)

        if std_val <= min_std_epsilon:
            z_val = None
            clean_std = 0.0
        else:
            z_val = (current_spread - mean_val) / std_val
            clean_std = std_val

        results.append(
            RollingZScorePoint(
                spread=current_spread,
                rolling_mean=mean_val,
                rolling_std=clean_std,
                z_score=z_val,
            )
        )

    return results


def analyze_pair_spread(
    series_a: Sequence[PricePoint],
    series_b: Sequence[PricePoint],
    window: int = 20,
    method: SpreadMethod = "log_ratio",
    hedge_ratio: float = 1.0,
    ddof: int = 1,
) -> list[PairSpreadPoint]:
    """Executa o pipeline completo de análise de spread e z-score para um par de ativos.

    1. Alinha preços pelas datas em comum e valida integridade.
    2. Calcula o spread em cada data conforme o método configurado.
    3. Calcula média móvel, desvio-padrão e z-score em janela estritamente passada.
    """
    if window < 2:
        raise ValueError("O tamanho da janela (window) deve ser pelo menos 2.")

    aligned = align_pair_prices(series_a, series_b)
    if not aligned:
        return []

    spreads = [
        calculate_spread(
            point.price_a,
            point.price_b,
            method=method,
            hedge_ratio=hedge_ratio,
        )
        for point in aligned
    ]
    rolling_stats = compute_rolling_zscore(spreads, window=window, ddof=ddof)

    return [
        PairSpreadPoint(
            trading_date=point.trading_date,
            price_a=point.price_a,
            price_b=point.price_b,
            spread=stat.spread,
            rolling_mean=stat.rolling_mean,
            rolling_std=stat.rolling_std,
            z_score=stat.z_score,
        )
        for point, stat in zip(aligned, rolling_stats, strict=True)
    ]
