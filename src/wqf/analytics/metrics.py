"""Estatísticas financeiras reutilizáveis (issue #7).

Todas as funções recebem séries (``pandas.Series`` ou sequências) de retornos
simples por período (ex.: 0.01 = 1%) ou de patrimônio/preço, e devolvem números
(``float``) ou séries. Nenhuma função gera documentos nem acessa a rede.

Convenções
----------
* Retornos são simples (não logarítmicos): ``r_t = P_t / P_{t-1} - 1``.
* Valores ``NaN`` são descartados; ``inf`` e retornos ``<= -1`` são erro.
* Anualização e taxa livre de risco são sempre parâmetros:
  - ``periods_per_year``: 252 (diário), 52 (semanal), 12 (mensal)...
  - ``risk_free_rate``: taxa ANUAL (float) ou série de taxas POR PERÍODO
    (ex.: CDI diário), alinhada pelo índice dos retornos.
* Desvio padrão amostral (``ddof=1``), logo exige pelo menos 2 observações.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Union

import numpy as np
import pandas as pd

DEFAULT_PERIODS_PER_YEAR = 252
_ZERO_TOL = 1e-12

SeriesLike = Union[pd.Series, Sequence[float], np.ndarray]


class InsufficientDataError(ValueError):
    """Há menos observações do que a métrica exige (ou dados não alinham)."""


class ZeroVolatilityError(ValueError):
    """A métrica divide por uma volatilidade igual a zero."""


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------
def _clean(values: SeriesLike, name: str, min_obs: int = 1) -> pd.Series:
    if values is None:
        raise ValueError(f"{name} não pode ser None")
    s = pd.Series(values, dtype="float64").dropna()
    if np.isinf(s.to_numpy()).any():
        raise ValueError(f"{name} contém valores infinitos")
    if len(s) < min_obs:
        raise InsufficientDataError(
            f"{name} precisa de pelo menos {min_obs} observação(ões); recebeu {len(s)}"
        )
    return s


def _clean_returns(values: SeriesLike, name: str = "returns", min_obs: int = 1) -> pd.Series:
    s = _clean(values, name, min_obs)
    if (s <= -1).any():
        raise ValueError(f"{name} contém retorno <= -100%, o que é inválido")
    return s


def _clean_wealth(values: SeriesLike, name: str = "wealth", min_obs: int = 1) -> pd.Series:
    s = _clean(values, name, min_obs)
    if (s <= 0).any():
        raise ValueError(f"{name} deve ter apenas valores positivos")
    return s


def _check_periods(periods_per_year: float) -> float:
    if periods_per_year is None or not periods_per_year > 0:
        raise ValueError("periods_per_year deve ser um número positivo")
    return float(periods_per_year)


def _per_period_rf(
    risk_free_rate: Union[float, pd.Series], index: pd.Index, periods_per_year: float
) -> Union[float, pd.Series]:
    if risk_free_rate is None:
        raise ValueError(
            "risk_free_rate é obrigatório (taxa anual float ou série por período)"
        )
    if isinstance(risk_free_rate, pd.Series):
        aligned = risk_free_rate.astype("float64").reindex(index)
        if aligned.isna().any():
            raise InsufficientDataError(
                "a série risk_free_rate não cobre todas as datas dos retornos"
            )
        return aligned
    if risk_free_rate <= -1:
        raise ValueError("risk_free_rate anual deve ser > -100%")
    return (1.0 + float(risk_free_rate)) ** (1.0 / periods_per_year) - 1.0


# --------------------------------------------------------------------------
# Conversões
# --------------------------------------------------------------------------
def wealth_to_returns(wealth: SeriesLike) -> pd.Series:
    """Converte preços/patrimônio em retornos simples (perde a 1ª observação)."""
    s = _clean_wealth(wealth, "wealth", min_obs=2)
    return s.pct_change().dropna()


def returns_to_wealth(returns: SeriesLike, initial: float = 1.0) -> pd.Series:
    """Curva de patrimônio acumulada a partir de retornos (sem o ponto inicial)."""
    if not initial > 0:
        raise ValueError("initial deve ser positivo")
    r = _clean_returns(returns)
    return (1.0 + r).cumprod() * float(initial)


# --------------------------------------------------------------------------
# Retorno e volatilidade
# --------------------------------------------------------------------------
def cumulative_return(returns: SeriesLike) -> float:
    """Retorno acumulado: ``prod(1 + r) - 1``."""
    r = _clean_returns(returns)
    return float((1.0 + r).prod() - 1.0)


def annualized_return(
    returns: SeriesLike, periods_per_year: float = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Retorno geométrico anualizado: ``(1 + acumulado) ** (ppy / n) - 1``."""
    ppy = _check_periods(periods_per_year)
    r = _clean_returns(returns)
    return float((1.0 + cumulative_return(r)) ** (ppy / len(r)) - 1.0)


def annualized_volatility(
    returns: SeriesLike, periods_per_year: float = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Volatilidade anualizada: ``std(r, ddof=1) * sqrt(ppy)``. Mínimo 2 pontos."""
    ppy = _check_periods(periods_per_year)
    r = _clean_returns(returns, min_obs=2)
    return float(r.std(ddof=1) * math.sqrt(ppy))


# --------------------------------------------------------------------------
# Drawdown
# --------------------------------------------------------------------------
def drawdown_series(wealth: SeriesLike) -> pd.Series:
    """Série de drawdown: ``wealth / máximo_acumulado - 1`` (valores <= 0)."""
    w = _clean_wealth(wealth)
    return w / w.cummax() - 1.0


def max_drawdown(wealth: SeriesLike) -> float:
    """Máximo drawdown (número <= 0) de uma curva de patrimônio/preço."""
    return float(drawdown_series(wealth).min())


def max_drawdown_from_returns(returns: SeriesLike) -> float:
    """Máximo drawdown a partir de retornos, contando o patrimônio inicial (=1)."""
    r = _clean_returns(returns)
    wealth = np.concatenate([[1.0], (1.0 + r.to_numpy()).cumprod()])
    running_max = np.maximum.accumulate(wealth)
    return float((wealth / running_max - 1.0).min())


# --------------------------------------------------------------------------
# Sharpe e benchmark
# --------------------------------------------------------------------------
def sharpe_ratio(
    returns: SeriesLike,
    risk_free_rate: Union[float, pd.Series],
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR,
) -> float:
    """Índice de Sharpe anualizado.

    ``risk_free_rate`` é obrigatório (nada é assumido): float = taxa ANUAL
    (convertida para o período por composição) ou ``Series`` = taxa por período.

    Levanta ``InsufficientDataError`` (< 2 pontos ou rf sem cobertura) e
    ``ZeroVolatilityError`` (retornos em excesso constantes).
    """
    ppy = _check_periods(periods_per_year)
    r = _clean_returns(returns, min_obs=2)
    rf = _per_period_rf(risk_free_rate, r.index, ppy)
    excess = r - rf
    std = float(excess.std(ddof=1))
    if std < _ZERO_TOL:
        raise ZeroVolatilityError("volatilidade dos retornos em excesso é zero")
    return float(excess.mean() / std * math.sqrt(ppy))


@dataclass(frozen=True)
class BenchmarkComparison:
    n_obs: int
    cumulative_return: float
    benchmark_cumulative_return: float
    excess_cumulative_return: float
    annualized_excess_return: float
    tracking_error: float


def _align(returns: SeriesLike, benchmark: SeriesLike) -> pd.DataFrame:
    r = _clean_returns(returns, "returns")
    b = _clean_returns(benchmark, "benchmark_returns")
    df = pd.concat([r.rename("r"), b.rename("b")], axis=1, join="inner").dropna()
    if len(df) < 2:
        raise InsufficientDataError(
            f"retornos e benchmark têm {len(df)} data(s) em comum; mínimo é 2"
        )
    return df


def compare_to_benchmark(
    returns: SeriesLike,
    benchmark_returns: SeriesLike,
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR,
) -> BenchmarkComparison:
    """Compara estratégia x benchmark (CDI, Ibovespa...) nas datas em comum."""
    ppy = _check_periods(periods_per_year)
    df = _align(returns, benchmark_returns)
    cum_r = cumulative_return(df["r"])
    cum_b = cumulative_return(df["b"])
    ann_excess = annualized_return(df["r"], ppy) - annualized_return(df["b"], ppy)
    tracking_error = float((df["r"] - df["b"]).std(ddof=1) * math.sqrt(ppy))
    return BenchmarkComparison(
        n_obs=len(df),
        cumulative_return=cum_r,
        benchmark_cumulative_return=cum_b,
        excess_cumulative_return=cum_r - cum_b,
        annualized_excess_return=ann_excess,
        tracking_error=tracking_error,
    )


def information_ratio(
    returns: SeriesLike,
    benchmark_returns: SeriesLike,
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR,
) -> float:
    """Information ratio anualizado: média do retorno ativo / desvio do ativo."""
    ppy = _check_periods(periods_per_year)
    df = _align(returns, benchmark_returns)
    active = df["r"] - df["b"]
    std = float(active.std(ddof=1))
    if std < _ZERO_TOL:
        raise ZeroVolatilityError("tracking error é zero")
    return float(active.mean() / std * math.sqrt(ppy))
