from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize("name", ["MarketData", "StrategySignal", "SimulatedTrade"])
def test_contracts_are_importable_from_package(name: str) -> None:
    module = importlib.import_module("wqf.contracts")

    contract = getattr(module, name)

    assert name in module.__all__
    assert contract.CONTRACT == name
    assert callable(contract.from_dict)


def test_validation_error_is_a_value_error() -> None:
    from wqf.contracts import ContractValidationError

    assert issubclass(ContractValidationError, ValueError)
