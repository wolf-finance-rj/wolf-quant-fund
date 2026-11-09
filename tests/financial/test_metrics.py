"""Testes com casos sintéticos cujo resultado foi calculado à mão."""

import math

import pandas as pd
import pytest

from wqf.analytics import (
    InsufficientDataError,
    ZeroVolatilityError,
    annualized_return,
    annualized_volatility,
    compare_to_benchmark,
    cumulative_return,
    drawdown_series,
    information_ratio,
    max_drawdown,
    max_drawdown_from_returns,
    returns_to_wealth,
    sharpe_ratio,
    wealth_to_returns,
)

STD_2PTS = math.sqrt(0.0002)  # desvio amostral de [0.01, 0.03] (ou [0.02, 0.04])


# ---------------- retorno acumulado / anualizado ----------------
def test_cumulative_return():
    # 1.1 * 0.9 * 1.2 = 1.188
    assert cumulative_return([0.1, -0.1, 0.2]) == pytest.approx(0.188)


def test_cumulative_return_drops_nan():
    assert cumulative_return([float("nan"), 0.1]) == pytest.approx(0.1)


def test_annualized_return():
    # 2 períodos de +10% => 1.21; ppy=1 => 1.21 ** (1/2) - 1 = 0.10
    assert annualized_return([0.1, 0.1], periods_per_year=1) == pytest.approx(0.1)


@pytest.mark.parametrize("bad", [[], [float("nan")]])
def test_cumulative_return_empty(bad):
    with pytest.raises(InsufficientDataError):
        cumulative_return(bad)


def test_return_below_minus_one_is_invalid():
    with pytest.raises(ValueError):
        cumulative_return([0.1, -1.0])


def test_infinite_is_invalid():
    with pytest.raises(ValueError):
        cumulative_return([0.1, float("inf")])


# ---------------- volatilidade ----------------
def test_annualized_volatility():
    # std=sqrt(0.0002); ppy=4 => * 2
    assert annualized_volatility([0.01, 0.03], periods_per_year=4) == pytest.approx(
        2 * STD_2PTS
    )


def test_volatility_constant_returns_is_zero():
    assert annualized_volatility([0.01] * 10) == pytest.approx(0.0, abs=1e-12)


def test_volatility_needs_two_points():
    with pytest.raises(InsufficientDataError):
        annualized_volatility([0.01])


@pytest.mark.parametrize("ppy", [0, -5, None])
def test_invalid_periods_per_year(ppy):
    with pytest.raises(ValueError):
        annualized_volatility([0.01, 0.02], periods_per_year=ppy)


# ---------------- drawdown ----------------
def test_drawdown_series_and_max():
    wealth = pd.Series([100, 120, 90, 130, 117])
    expected = [0.0, 0.0, -0.25, 0.0, -0.1]
    assert drawdown_series(wealth).tolist() == pytest.approx(expected)
    assert max_drawdown(wealth) == pytest.approx(-0.25)


def test_max_drawdown_monotonic_growth_is_zero():
    assert max_drawdown([1, 2, 3]) == 0.0


def test_max_drawdown_from_returns_counts_initial_loss():
    # 1 -> 0.9 -> 0.9 * 1.05 = 0.945 ; pico inicial = 1 ; pior = -10%
    assert max_drawdown_from_returns([-0.1, 0.05]) == pytest.approx(-0.1)


def test_drawdown_rejects_non_positive_wealth():
    with pytest.raises(ValueError):
        max_drawdown([100, 0, 50])


def test_drawdown_empty():
    with pytest.raises(InsufficientDataError):
        max_drawdown([])


# ---------------- conversões ----------------
def test_wealth_to_returns():
    assert wealth_to_returns([100, 110, 99]).tolist() == pytest.approx([0.1, -0.1])


def test_returns_to_wealth():
    assert returns_to_wealth([0.1, 0.1], initial=100).tolist() == pytest.approx(
        [110.0, 121.0]
    )


# ---------------- Sharpe ----------------
def test_sharpe_zero_rf():
    # média 0.03 / std sqrt(0.0002), ppy=1
    assert sharpe_ratio([0.02, 0.04], risk_free_rate=0.0, periods_per_year=1) == (
        pytest.approx(0.03 / STD_2PTS)
    )


def test_sharpe_converts_annual_rf_to_period():
    # rf anual 21% com ppy=2 => 1.21 ** 0.5 - 1 = 10% por período
    # excessos = [0.02, 0.04] => média 0.03 ; anualiza por sqrt(2)
    result = sharpe_ratio([0.12, 0.14], risk_free_rate=0.21, periods_per_year=2)
    assert result == pytest.approx(0.03 / STD_2PTS * math.sqrt(2))


def test_sharpe_with_rf_series():
    idx = pd.date_range("2024-01-01", periods=2)
    r = pd.Series([0.12, 0.14], index=idx)
    rf = pd.Series([0.10, 0.10], index=idx)
    assert sharpe_ratio(r, rf, periods_per_year=2) == pytest.approx(
        0.03 / STD_2PTS * math.sqrt(2)
    )


def test_sharpe_rf_series_missing_dates():
    idx = pd.date_range("2024-01-01", periods=3)
    r = pd.Series([0.01, 0.02, 0.03], index=idx)
    rf = pd.Series([0.001], index=idx[:1])
    with pytest.raises(InsufficientDataError):
        sharpe_ratio(r, rf)


def test_sharpe_requires_rf():
    with pytest.raises(ValueError):
        sharpe_ratio([0.01, 0.02], risk_free_rate=None)


def test_sharpe_insufficient_sample():
    with pytest.raises(InsufficientDataError):
        sharpe_ratio([0.01], risk_free_rate=0.0)


def test_sharpe_constant_returns_zero_vol():
    with pytest.raises(ZeroVolatilityError):
        sharpe_ratio([0.01] * 10, risk_free_rate=0.0)


# ---------------- benchmark ----------------
def test_compare_to_benchmark():
    idx = pd.date_range("2024-01-01", periods=2)
    r = pd.Series([0.02, 0.04], index=idx)
    b = pd.Series([0.01, 0.01], index=idx)
    res = compare_to_benchmark(r, b, periods_per_year=1)
    assert res.n_obs == 2
    assert res.cumulative_return == pytest.approx(1.02 * 1.04 - 1)  # 0.0608
    assert res.benchmark_cumulative_return == pytest.approx(1.01**2 - 1)  # 0.0201
    assert res.excess_cumulative_return == pytest.approx(0.0608 - 0.0201)
    assert res.tracking_error == pytest.approx(STD_2PTS)  # ativo = [0.01, 0.03]


def test_compare_uses_only_common_dates():
    r = pd.Series([0.01, 0.02, 0.03], index=pd.date_range("2024-01-01", periods=3))
    b = pd.Series([0.01, 0.02, 0.03], index=pd.date_range("2024-01-02", periods=3))
    assert compare_to_benchmark(r, b).n_obs == 2


def test_compare_without_overlap():
    r = pd.Series([0.01, 0.02], index=pd.date_range("2024-01-01", periods=2))
    b = pd.Series([0.01, 0.02], index=pd.date_range("2025-01-01", periods=2))
    with pytest.raises(InsufficientDataError):
        compare_to_benchmark(r, b)


def test_information_ratio():
    # ativo = [0.01, 0.03] => média 0.02 / std sqrt(0.0002); ppy=1
    assert information_ratio([0.02, 0.04], [0.01, 0.01], periods_per_year=1) == (
        pytest.approx(0.02 / STD_2PTS)
    )


def test_information_ratio_zero_tracking_error():
    with pytest.raises(ZeroVolatilityError):
        information_ratio([0.01, 0.02], [0.01, 0.02])
