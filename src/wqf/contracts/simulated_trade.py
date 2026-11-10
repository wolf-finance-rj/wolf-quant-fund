"""Contrato ``SimulatedTrade``: operação executada pelo motor de backtesting.

Convenções:
- ``trade_date`` é a data do pregão em que a operação é executada.
- ``quantity`` é a quantidade de ações com sinal: positiva = compra, negativa = venda.
  Zero não é operação e é rejeitado.
- ``execution_price`` é o preço unitário em BRL (> 0), antes dos custos.
- ``costs`` soma corretagem, emolumentos e impacto em BRL (>= 0), sempre como valor positivo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar

from wqf.contracts._validation import (
    check_keys,
    check_schema_version,
    normalize_ticker,
    parse_date,
    require_date,
    require_number,
)
from wqf.contracts.errors import ContractValidationError

SIMULATED_TRADE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SimulatedTrade:
    """Operação simulada validada: data, ativo, quantidade, preço de execução e custos."""

    trade_date: date
    ticker: str
    quantity: float
    execution_price: float
    costs: float
    schema_version: str = SIMULATED_TRADE_SCHEMA_VERSION

    CONTRACT: ClassVar[str] = "SimulatedTrade"
    _REQUIRED: ClassVar[frozenset[str]] = frozenset(
        {"trade_date", "ticker", "quantity", "execution_price", "costs"}
    )
    _OPTIONAL: ClassVar[frozenset[str]] = frozenset({"schema_version"})

    def __post_init__(self) -> None:
        c = self.CONTRACT
        quantity = require_number(c, "quantity", self.quantity)
        if quantity == 0:
            raise ContractValidationError(c, "quantity", "quantidade zero não é uma operação")
        values: dict[str, Any] = {
            "trade_date": require_date(c, "trade_date", self.trade_date),
            "ticker": normalize_ticker(c, "ticker", self.ticker),
            "quantity": quantity,
            "execution_price": require_number(
                c, "execution_price", self.execution_price, min_value=0.0, min_inclusive=False
            ),
            "costs": require_number(c, "costs", self.costs, min_value=0.0),
            "schema_version": check_schema_version(
                c, self.schema_version, SIMULATED_TRADE_SCHEMA_VERSION
            ),
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @property
    def is_buy(self) -> bool:
        """``True`` para compra (quantidade positiva)."""
        return self.quantity > 0

    @property
    def notional(self) -> float:
        """Valor financeiro bruto em BRL (sempre positivo, sem custos)."""
        return abs(self.quantity) * self.execution_price

    def to_dict(self) -> dict[str, Any]:
        """Serializa para tipos JSON (datas em ISO-8601)."""
        return {
            "trade_date": self.trade_date.isoformat(),
            "ticker": self.ticker,
            "quantity": self.quantity,
            "execution_price": self.execution_price,
            "costs": self.costs,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SimulatedTrade:
        """Reconstrói e valida um registro serializado por ``to_dict``."""
        check_keys(cls.CONTRACT, data, cls._REQUIRED, cls._OPTIONAL)
        fields = dict(data)
        fields["trade_date"] = parse_date(cls.CONTRACT, "trade_date", fields["trade_date"])
        return cls(**fields)
