"""Testes unitários para o módulo de Pairs Trading — Parte 1: alinhamento e spread."""

import math
from datetime import date

import pytest

from wqf.strategies.pairs import (
    PricePoint,
    align_pair_prices,
    calculate_spread,
)


def test_align_pair_prices_common_dates() -> None:
    """Garante que apenas datas em comum permanecem e saem ordenadas cronologicamente."""
    series_a = [
        PricePoint(date(2026, 1, 5), 31.0),
        PricePoint(date(2026, 1, 2), 30.0),
        PricePoint(date(2026, 1, 6), 32.0),  # Data exclusiva de A
    ]
    series_b = [
        PricePoint(date(2026, 1, 2), 15.0),
        PricePoint(date(2026, 1, 3), 15.2),  # Data exclusiva de B
        PricePoint(date(2026, 1, 5), 15.5),
    ]

    aligned = align_pair_prices(series_a, series_b)

    assert len(aligned) == 2
    assert aligned[0].trading_date == date(2026, 1, 2)
    assert aligned[0].price_a == 30.0
    assert aligned[0].price_b == 15.0

    assert aligned[1].trading_date == date(2026, 1, 5)
    assert aligned[1].price_a == 31.0
    assert aligned[1].price_b == 15.5


def test_align_pair_rejects_duplicate_dates() -> None:
    """Garante que datas duplicadas em uma mesma série disparam ValueError."""
    series_a = [
        PricePoint(date(2026, 1, 2), 30.0),
        PricePoint(date(2026, 1, 2), 30.5),
    ]
    series_b = [PricePoint(date(2026, 1, 2), 15.0)]

    with pytest.raises(ValueError, match="Data duplicada"):
        align_pair_prices(series_a, series_b)


def test_align_pair_rejects_non_positive_prices() -> None:
    """Garante que preços <= 0 são rejeitados explicitamente."""
    series_a = [PricePoint(date(2026, 1, 2), -10.0)]
    series_b = [PricePoint(date(2026, 1, 2), 15.0)]

    with pytest.raises(ValueError, match="Preço inválido"):
        align_pair_prices(series_a, series_b)


def test_calculate_spread_methods() -> None:
    """Testa os 3 métodos parametrizáveis de cálculo de spread."""
    price_a = 100.0
    price_b = 50.0

    # 1. log_ratio: ln(100) - 1.0 * ln(50) = ln(2)
    spread_log = calculate_spread(price_a, price_b, method="log_ratio", hedge_ratio=1.0)
    assert math.isclose(spread_log, math.log(2.0), rel_tol=1e-9)

    # 2. price_ratio: 100 / 50 = 2.0
    spread_ratio = calculate_spread(price_a, price_b, method="price_ratio")
    assert math.isclose(spread_ratio, 2.0, rel_tol=1e-9)

    # 3. hedge_diff: 100 - 1.5 * 50 = 25.0
    spread_diff = calculate_spread(price_a, price_b, method="hedge_diff", hedge_ratio=1.5)
    assert math.isclose(spread_diff, 25.0, rel_tol=1e-9)
