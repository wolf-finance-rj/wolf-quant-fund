"""Testes unitários para o módulo de Pairs Trading (Issue #5: alinhamento, spread e z-score)."""

import math
from datetime import date, timedelta

import pytest

from wqf.strategies.pairs import (
    PricePoint,
    align_pair_prices,
    analyze_pair_spread,
    calculate_spread,
    compute_rolling_zscore,
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


def test_calculate_spread_invalid_inputs() -> None:
    """Verifica rejeição de método desconhecido, preço não positivo ou hedge_ratio inválido."""
    with pytest.raises(ValueError, match="Método de spread inválido"):
        calculate_spread(100.0, 50.0, method="invalido")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="estritamente positivos"):
        calculate_spread(0.0, 50.0)

    with pytest.raises(ValueError, match="hedge_ratio"):
        calculate_spread(100.0, 50.0, hedge_ratio=-1.0)


def test_rolling_zscore_reproducible_fixture() -> None:
    """Verifica reprodutibilidade exata de média, desvio-padrão e z-score em janela conhecida."""
    # Janela W = 3 sobre spreads [10.0, 20.0, 30.0, 40.0]
    # Em t=2 (janela [10, 20, 30]): média = 20.0, std amostral (ddof=1) = 10.0, z = (30 - 20)/10 = +1.0
    # Em t=3 (janela [20, 30, 40]): média = 30.0, std amostral (ddof=1) = 10.0, z = (40 - 30)/10 = +1.0
    spreads = [10.0, 20.0, 30.0, 40.0]
    res = compute_rolling_zscore(spreads, window=3, ddof=1)

    assert len(res) == 4
    assert res[0].z_score is None
    assert res[1].z_score is None

    assert res[2].rolling_mean is not None and math.isclose(res[2].rolling_mean, 20.0)
    assert res[2].rolling_std is not None and math.isclose(res[2].rolling_std, 10.0)
    assert res[2].z_score is not None and math.isclose(res[2].z_score, 1.0)

    assert res[3].rolling_mean is not None and math.isclose(res[3].rolling_mean, 30.0)
    assert res[3].rolling_std is not None and math.isclose(res[3].rolling_std, 10.0)
    assert res[3].z_score is not None and math.isclose(res[3].z_score, 1.0)


def test_insufficient_window_returns_none() -> None:
    """Garante que série menor que a janela não inventa estatísticas."""
    spreads = [1.5, 1.6, 1.7]
    res = compute_rolling_zscore(spreads, window=5)

    assert len(res) == 3
    for point in res:
        assert point.rolling_mean is None
        assert point.rolling_std is None
        assert point.z_score is None

    with pytest.raises(ValueError, match="pelo menos 2"):
        compute_rolling_zscore(spreads, window=1)


def test_zero_std_returns_none_not_inf() -> None:
    """Garante que desvio-padrão zero retorna z_score=None sem gerar inf ou NaN."""
    spreads = [5.0, 5.0, 5.0, 5.0]
    res = compute_rolling_zscore(spreads, window=3)

    assert res[2].rolling_mean == 5.0
    assert res[2].rolling_std == 0.0
    assert res[2].z_score is None


def test_no_look_ahead_bias_in_analyze_pair() -> None:
    """Prova que choques futuros não alteram os resultados calculados em datas passadas."""
    base_date = date(2026, 1, 1)
    series_a_short = [PricePoint(base_date + timedelta(days=i), 100.0 + i * 2.0) for i in range(6)]
    series_b_short = [PricePoint(base_date + timedelta(days=i), 50.0 + i * 0.5) for i in range(6)]

    # Série estendida com um choque extremo no futuro (dias 6 e 7)
    series_a_with_future_shock = [
        *series_a_short,
        PricePoint(base_date + timedelta(days=6), 99999.0),
        PricePoint(base_date + timedelta(days=7), 0.01),
    ]
    series_b_with_future_shock = [
        *series_b_short,
        PricePoint(base_date + timedelta(days=6), 1.0),
        PricePoint(base_date + timedelta(days=7), 50000.0),
    ]

    res_short = analyze_pair_spread(series_a_short, series_b_short, window=3, method="log_ratio")
    res_shock = analyze_pair_spread(
        series_a_with_future_shock,
        series_b_with_future_shock,
        window=3,
        method="log_ratio",
    )

    # Todos os 6 primeiros dias devem ser idênticos bit a bit
    assert res_short == res_shock[:6]
    assert res_short[-1].z_score is not None
