"""Cálculo de alinhamento temporal e spread para Pairs Trading (Parte 1 da Issue #5)."""

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
