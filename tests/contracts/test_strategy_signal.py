from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from wqf.contracts import (
    MAX_ABS_TARGET_WEIGHT,
    ContractValidationError,
    SignalDirection,
    StrategySignal,
)


def test_valid_signal_is_accepted(strategy_signal_kwargs: dict[str, Any]) -> None:
    signal = StrategySignal(**{**strategy_signal_kwargs, "ticker": "vale3"})

    assert signal.ticker == "VALE3"
    assert signal.direction is SignalDirection.LONG
    assert signal.target_weight == pytest.approx(0.05)


@pytest.mark.parametrize(
    ("direction", "weight"),
    [("long", 0.10), ("short", -0.10), ("flat", 0.0), (SignalDirection.SHORT, -1.0)],
)
def test_direction_consistent_with_weight(
    strategy_signal_kwargs: dict[str, Any], direction: str, weight: float
) -> None:
    signal = StrategySignal(
        **{**strategy_signal_kwargs, "direction": direction, "target_weight": weight}
    )
    assert signal.direction == SignalDirection(direction)


@pytest.mark.parametrize(
    ("direction", "weight"),
    [("long", -0.10), ("long", 0.0), ("short", 0.10), ("flat", 0.01)],
)
def test_rejects_direction_inconsistent_with_weight(
    strategy_signal_kwargs: dict[str, Any], direction: str, weight: float
) -> None:
    with pytest.raises(ContractValidationError, match="incoerente"):
        StrategySignal(
            **{**strategy_signal_kwargs, "direction": direction, "target_weight": weight}
        )


@pytest.mark.parametrize("weight", [MAX_ABS_TARGET_WEIGHT + 0.01, -MAX_ABS_TARGET_WEIGHT - 0.01])
def test_rejects_weight_out_of_bounds(
    strategy_signal_kwargs: dict[str, Any], weight: float
) -> None:
    direction = "long" if weight > 0 else "short"
    with pytest.raises(ContractValidationError, match="target_weight"):
        StrategySignal(
            **{**strategy_signal_kwargs, "direction": direction, "target_weight": weight}
        )


@pytest.mark.parametrize("weight", [float("nan"), "0.05", None])
def test_rejects_invalid_weight_type(
    strategy_signal_kwargs: dict[str, Any], weight: object
) -> None:
    with pytest.raises(ContractValidationError, match="target_weight"):
        StrategySignal(**{**strategy_signal_kwargs, "target_weight": weight})


def test_rejects_unknown_direction(strategy_signal_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="direção inválida"):
        StrategySignal(**{**strategy_signal_kwargs, "direction": "buy"})


def test_rejects_empty_strategy(strategy_signal_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="strategy"):
        StrategySignal(**{**strategy_signal_kwargs, "strategy": " "})


def test_rejects_datetime_decision_date(strategy_signal_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="decision_date"):
        StrategySignal(
            **{**strategy_signal_kwargs, "decision_date": datetime(2026, 10, 1, tzinfo=UTC)}
        )


def test_json_round_trip_preserves_record(strategy_signal_kwargs: dict[str, Any]) -> None:
    signal = StrategySignal(**strategy_signal_kwargs)

    payload = json.dumps(signal.to_dict())
    restored = StrategySignal.from_dict(json.loads(payload))

    assert restored == signal
    assert json.loads(payload)["direction"] == "long"


def test_from_dict_rejects_missing_and_unknown_fields(
    strategy_signal_kwargs: dict[str, Any],
) -> None:
    data = StrategySignal(**strategy_signal_kwargs).to_dict()
    with pytest.raises(ContractValidationError, match="ausentes"):
        StrategySignal.from_dict({k: v for k, v in data.items() if k != "target_weight"})
    with pytest.raises(ContractValidationError, match="desconhecidos"):
        StrategySignal.from_dict({**data, "expected_return": 0.12})


def test_schema_version_compatibility(strategy_signal_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="incompatível"):
        StrategySignal(**{**strategy_signal_kwargs, "schema_version": "0.9"})
