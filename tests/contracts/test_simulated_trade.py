from __future__ import annotations

import json
from typing import Any

import pytest

from wqf.contracts import ContractValidationError, SimulatedTrade


def test_valid_buy_is_accepted(simulated_trade_kwargs: dict[str, Any]) -> None:
    trade = SimulatedTrade(**simulated_trade_kwargs)

    assert trade.is_buy
    assert trade.quantity == 100.0
    assert trade.notional == pytest.approx(3_540.0)


def test_sell_has_negative_quantity_and_positive_notional(
    simulated_trade_kwargs: dict[str, Any],
) -> None:
    trade = SimulatedTrade(**{**simulated_trade_kwargs, "quantity": -100})

    assert not trade.is_buy
    assert trade.notional == pytest.approx(3_540.0)


def test_rejects_zero_quantity(simulated_trade_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="quantidade zero"):
        SimulatedTrade(**{**simulated_trade_kwargs, "quantity": 0})


@pytest.mark.parametrize("price", [0, -35.4, float("inf")])
def test_rejects_invalid_execution_price(
    simulated_trade_kwargs: dict[str, Any], price: float
) -> None:
    with pytest.raises(ContractValidationError, match="execution_price"):
        SimulatedTrade(**{**simulated_trade_kwargs, "execution_price": price})


def test_rejects_negative_costs(simulated_trade_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="costs"):
        SimulatedTrade(**{**simulated_trade_kwargs, "costs": -0.01})


def test_accepts_zero_costs(simulated_trade_kwargs: dict[str, Any]) -> None:
    assert SimulatedTrade(**{**simulated_trade_kwargs, "costs": 0}).costs == 0.0


def test_rejects_string_trade_date(simulated_trade_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="trade_date"):
        SimulatedTrade(**{**simulated_trade_kwargs, "trade_date": "2026-10-02"})


def test_json_round_trip_preserves_record(simulated_trade_kwargs: dict[str, Any]) -> None:
    trade = SimulatedTrade(**simulated_trade_kwargs)

    restored = SimulatedTrade.from_dict(json.loads(json.dumps(trade.to_dict())))

    assert restored == trade


def test_from_dict_rejects_missing_field(simulated_trade_kwargs: dict[str, Any]) -> None:
    data = SimulatedTrade(**simulated_trade_kwargs).to_dict()
    del data["costs"]
    with pytest.raises(ContractValidationError, match="costs"):
        SimulatedTrade.from_dict(data)


def test_from_dict_rejects_non_mapping() -> None:
    with pytest.raises(ContractValidationError, match="mapeamento"):
        SimulatedTrade.from_dict(["ITUB4", 100])  # type: ignore[arg-type]
