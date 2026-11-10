"""Contrato ``MarketData``: barra diária padronizada de um ativo.

Convenções:
- ``date`` é a data do pregão (``datetime.date``, sem horário).
- Preços em BRL por ação, sem ajuste retroativo por proventos (ajustes ficam a cargo
  do pipeline de dados para evitar look-ahead; ver ``docs/architecture/contracts.md``).
- ``volume`` é a quantidade negociada no dia (>= 0).
- ``dividend`` é o provento em BRL por ação na data ex (0.0 quando não houver).
- ``available_at`` é o instante, com fuso horário, em que o dado passa a ser conhecido.
  Estratégias só podem usar a barra em decisões tomadas a partir desse instante.
  Ele não pode ser anterior ao fechamento do pregão (``MARKET_CLOSE_TIME`` no fuso
  ``MARKET_TIMEZONE``, o da B3): antes disso o fechamento do dia ainda não é conhecido.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from wqf.contracts._validation import (
    check_keys,
    check_schema_version,
    normalize_ticker,
    parse_date,
    parse_datetime,
    require_aware_datetime,
    require_date,
    require_number,
    require_text,
)
from wqf.contracts.errors import ContractValidationError

MARKET_DATA_SCHEMA_VERSION = "1.0"

# Fuso da B3. Usar a base de fusos (e não um UTC-3 fixo) trata corretamente os dados
# históricos dos anos em que o Brasil tinha horário de verão (até 2019).
MARKET_TIMEZONE = ZoneInfo("America/Sao_Paulo")
# Horário (local) a partir do qual a barra do dia é considerada conhecida. 18:00 é o
# fechamento mais tardio do pregão regular da B3; por isso a regra é conservadora.
MARKET_CLOSE_TIME = time(18, 0)


def market_close(trading_date: date) -> datetime:
    """Instante de fechamento do pregão de ``trading_date`` no fuso da B3."""
    return datetime.combine(trading_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)


@dataclass(frozen=True, slots=True)
class MarketData:
    """Barra diária OHLCV validada de um ativo, com disponibilidade e procedência."""

    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    available_at: datetime
    source: str
    dividend: float = 0.0
    schema_version: str = MARKET_DATA_SCHEMA_VERSION

    CONTRACT: ClassVar[str] = "MarketData"
    _REQUIRED: ClassVar[frozenset[str]] = frozenset(
        {"ticker", "date", "open", "high", "low", "close", "volume", "available_at", "source"}
    )
    _OPTIONAL: ClassVar[frozenset[str]] = frozenset({"dividend", "schema_version"})

    def __post_init__(self) -> None:
        c = self.CONTRACT
        values: dict[str, Any] = {
            "ticker": normalize_ticker(c, "ticker", self.ticker),
            "date": require_date(c, "date", self.date),
            "available_at": require_aware_datetime(c, "available_at", self.available_at),
            "source": require_text(c, "source", self.source),
            "schema_version": check_schema_version(
                c, self.schema_version, MARKET_DATA_SCHEMA_VERSION
            ),
        }
        for name in ("open", "high", "low", "close"):
            values[name] = require_number(
                c, name, getattr(self, name), min_value=0.0, min_inclusive=False
            )
        values["volume"] = require_number(c, "volume", self.volume, min_value=0.0)
        values["dividend"] = require_number(c, "dividend", self.dividend, min_value=0.0)

        if values["high"] < values["low"]:
            raise ContractValidationError(
                c, "high", f"high ({values['high']}) menor que low ({values['low']})"
            )
        for name in ("open", "close"):
            if not values["low"] <= values[name] <= values["high"]:
                raise ContractValidationError(
                    c, name, f"{name} ({values[name]}) fora do intervalo [low, high]"
                )
        close_at = market_close(values["date"])
        if values["available_at"] < close_at:
            raise ContractValidationError(
                c,
                "available_at",
                f"dado marcado como disponível ({values['available_at'].isoformat()}) antes "
                f"do fechamento do pregão ({close_at.isoformat()})",
            )

        # Grava os valores normalizados (ticker maiúsculo, números como float).
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        """Serializa para tipos JSON (datas em ISO-8601)."""
        return {
            "ticker": self.ticker,
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "available_at": self.available_at.isoformat(),
            "source": self.source,
            "dividend": self.dividend,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MarketData:
        """Reconstrói e valida um registro serializado por ``to_dict``."""
        check_keys(cls.CONTRACT, data, cls._REQUIRED, cls._OPTIONAL)
        fields = dict(data)
        fields["date"] = parse_date(cls.CONTRACT, "date", fields["date"])
        fields["available_at"] = parse_datetime(
            cls.CONTRACT, "available_at", fields["available_at"]
        )
        return cls(**fields)
