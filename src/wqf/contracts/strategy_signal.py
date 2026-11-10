"""Contrato ``StrategySignal``: posição-alvo emitida por uma estratégia.

Estratégias (Momentum, Pairs) emitem sinais; quem executa, cobra custos e contabiliza
caixa é o motor de backtesting. Convenções:
- ``decision_date`` é a data em que a decisão é tomada com dados disponíveis até ela.
- ``target_weight`` é a fração do patrimônio desejada no ativo, entre -1 e 1.
  Positivo = comprado, negativo = vendido, zero = zerado.
- ``direction`` precisa ser coerente com o sinal de ``target_weight``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, ClassVar

from wqf.contracts._validation import (
    check_keys,
    check_schema_version,
    normalize_ticker,
    parse_date,
    require_date,
    require_number,
    require_text,
)
from wqf.contracts.errors import ContractValidationError

STRATEGY_SIGNAL_SCHEMA_VERSION = "1.0"

#: Limite absoluto do peso-alvo por ativo (fração do patrimônio).
MAX_ABS_TARGET_WEIGHT = 1.0


class SignalDirection(StrEnum):
    """Direção da posição-alvo."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """Posição-alvo validada de uma estratégia para um ativo em uma data de decisão."""

    decision_date: date
    ticker: str
    strategy: str
    direction: SignalDirection
    target_weight: float
    schema_version: str = STRATEGY_SIGNAL_SCHEMA_VERSION

    CONTRACT: ClassVar[str] = "StrategySignal"
    _REQUIRED: ClassVar[frozenset[str]] = frozenset(
        {"decision_date", "ticker", "strategy", "direction", "target_weight"}
    )
    _OPTIONAL: ClassVar[frozenset[str]] = frozenset({"schema_version"})

    def __post_init__(self) -> None:
        c = self.CONTRACT
        try:
            direction = SignalDirection(self.direction)
        except ValueError as exc:
            allowed = [d.value for d in SignalDirection]
            raise ContractValidationError(
                c, "direction", f"direção inválida {self.direction!r}; use {allowed}"
            ) from exc
        weight = require_number(
            c,
            "target_weight",
            self.target_weight,
            min_value=-MAX_ABS_TARGET_WEIGHT,
            max_value=MAX_ABS_TARGET_WEIGHT,
        )
        consistent = {
            SignalDirection.LONG: weight > 0,
            SignalDirection.SHORT: weight < 0,
            SignalDirection.FLAT: weight == 0,
        }[direction]
        if not consistent:
            raise ContractValidationError(
                c,
                "target_weight",
                f"peso {weight} incoerente com direção {direction.value!r} "
                "(long > 0, short < 0, flat = 0)",
            )

        values: dict[str, Any] = {
            "decision_date": require_date(c, "decision_date", self.decision_date),
            "ticker": normalize_ticker(c, "ticker", self.ticker),
            "strategy": require_text(c, "strategy", self.strategy),
            "direction": direction,
            "target_weight": weight,
            "schema_version": check_schema_version(
                c, self.schema_version, STRATEGY_SIGNAL_SCHEMA_VERSION
            ),
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        """Serializa para tipos JSON (datas em ISO-8601, direção como texto)."""
        return {
            "decision_date": self.decision_date.isoformat(),
            "ticker": self.ticker,
            "strategy": self.strategy,
            "direction": self.direction.value,
            "target_weight": self.target_weight,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StrategySignal:
        """Reconstrói e valida um registro serializado por ``to_dict``."""
        check_keys(cls.CONTRACT, data, cls._REQUIRED, cls._OPTIONAL)
        fields = dict(data)
        fields["decision_date"] = parse_date(cls.CONTRACT, "decision_date", fields["decision_date"])
        return cls(**fields)
