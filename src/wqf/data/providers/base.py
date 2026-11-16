"""Interfaces e adaptadores de provedores de dados históricos (Ações, Benchmark e CDI).

Limites reais de disponibilidade temporal dos dados (governança contra look-ahead bias):
1. Ações B3 (OHLCV): o preço de fechamento oficial do pregão D só está disponível após
   o encerramento do call de fechamento (~18h15 BRT). Estratégias diárias devem assumir
   disponibilidade no fim do dia D ou abertura de D+1.
2. Proventos (Dividendos/JCP): séries históricas pré-ajustadas retroativamente ("adjusted close"
   de provedores gratuitos) embutem informação futura sobre dividendos e desdobramentos.
   Para evitar look-ahead bias, o pipeline armazena o preço bruto ('close') e o provento
   na data ex ('dividend'), acumulando o fator de retorno apenas a partir da data ex.
3. CDI Diário (BCB SGS Série 12): divulgado pela B3/CETIP e consolidado no SGS tipicamente
   na manhã de D+1 útil.
4. Ibovespa (Benchmark): pontuação de fechamento consolidada após o término do pregão D.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import polars as pl

EQUITIES_RAW_COLUMNS: list[str] = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "dividend",
]
BENCHMARK_RAW_COLUMNS: list[str] = ["date", "symbol", "close"]
CDI_RAW_COLUMNS: list[str] = ["date", "daily_rate"]


@dataclass(frozen=True)
class EquityBar:
    """Registro diário bruto de uma ação com provento na data ex."""

    date: date
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    dividend: float = 0.0


@dataclass(frozen=True)
class BenchmarkBar:
    """Registro diário de um índice de referência (ex.: IBOV)."""

    date: date
    symbol: str
    close: float


@dataclass(frozen=True)
class CdiRatePoint:
    """Registro diário da taxa CDI (em decimal diário, ex.: 0.0004 para 0,04% ao dia)."""

    date: date
    daily_rate: float


@runtime_checkable
class EquitiesProvider(Protocol):
    """Contrato para provedores de dados históricos de ações."""

    @property
    def source_name(self) -> str:
        """Identificador da fonte de dados."""

    def fetch_equities(self, start_date: date, end_date: date) -> pl.DataFrame:
        """Retorna DataFrame de ações no intervalo [start_date, end_date]."""


@runtime_checkable
class BenchmarkProvider(Protocol):
    """Contrato para provedores de índices de mercado (ex.: Ibovespa)."""

    @property
    def source_name(self) -> str:
        """Identificador da fonte de dados."""

    def fetch_benchmark(self, start_date: date, end_date: date) -> pl.DataFrame:
        """Retorna DataFrame do benchmark no intervalo [start_date, end_date]."""


@runtime_checkable
class CdiProvider(Protocol):
    """Contrato para provedores da série histórica do CDI."""

    @property
    def source_name(self) -> str:
        """Identificador da fonte de dados."""

    def fetch_cdi(self, start_date: date, end_date: date) -> pl.DataFrame:
        """Retorna DataFrame da taxa diária do CDI no intervalo [start_date, end_date]."""


class InMemoryEquitiesProvider:
    """Adapter em memória de ações para execução reproduzível sem rede ou credenciais."""

    def __init__(
        self,
        records: Sequence[EquityBar],
        source_name: str = "synthetic-equities-v1",
    ) -> None:
        self._records = list(records)
        self._source_name = source_name

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_equities(self, start_date: date, end_date: date) -> pl.DataFrame:
        filtered = [r for r in self._records if start_date <= r.date <= end_date]
        if not filtered:
            return pl.DataFrame(
                schema={
                    "date": pl.Date,
                    "ticker": pl.String,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Float64,
                    "dividend": pl.Float64,
                }
            )
        return pl.DataFrame(
            [
                {
                    "date": r.date,
                    "ticker": r.ticker,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": float(r.volume),
                    "dividend": float(r.dividend),
                }
                for r in filtered
            ]
        )


class InMemoryBenchmarkProvider:
    """Adapter em memória de benchmark (Ibovespa) sem dependência de rede."""

    def __init__(
        self,
        records: Sequence[BenchmarkBar],
        source_name: str = "synthetic-ibov-v1",
    ) -> None:
        self._records = list(records)
        self._source_name = source_name

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_benchmark(self, start_date: date, end_date: date) -> pl.DataFrame:
        filtered = [r for r in self._records if start_date <= r.date <= end_date]
        if not filtered:
            return pl.DataFrame(schema={"date": pl.Date, "symbol": pl.String, "close": pl.Float64})
        return pl.DataFrame(
            [
                {
                    "date": r.date,
                    "symbol": r.symbol,
                    "close": float(r.close),
                }
                for r in filtered
            ]
        )


class InMemoryCdiProvider:
    """Adapter em memória da taxa CDI diária sem dependência de rede."""

    def __init__(
        self,
        records: Sequence[CdiRatePoint],
        source_name: str = "synthetic-bcb-sgs-v1",
    ) -> None:
        self._records = list(records)
        self._source_name = source_name

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_cdi(self, start_date: date, end_date: date) -> pl.DataFrame:
        filtered = [r for r in self._records if start_date <= r.date <= end_date]
        if not filtered:
            return pl.DataFrame(schema={"date": pl.Date, "daily_rate": pl.Float64})
        return pl.DataFrame(
            [
                {
                    "date": r.date,
                    "daily_rate": float(r.daily_rate),
                }
                for r in filtered
            ]
        )
