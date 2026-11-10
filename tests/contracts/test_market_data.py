from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from wqf.contracts import MARKET_DATA_SCHEMA_VERSION, ContractValidationError, MarketData


def test_valid_bar_is_accepted_and_normalized(market_data_kwargs: dict[str, Any]) -> None:
    bar = MarketData(**{**market_data_kwargs, "ticker": "  petr4 "})

    assert bar.ticker == "PETR4"
    assert isinstance(bar.volume, float)
    assert bar.dividend == 0.0
    assert bar.schema_version == MARKET_DATA_SCHEMA_VERSION


def test_bar_is_immutable(market_data_kwargs: dict[str, Any]) -> None:
    bar = MarketData(**market_data_kwargs)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bar.close = 1.0  # type: ignore[misc]


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
@pytest.mark.parametrize("price", [0, -1.0])
def test_rejects_non_positive_prices(
    market_data_kwargs: dict[str, Any], field: str, price: float
) -> None:
    with pytest.raises(ContractValidationError) as exc:
        MarketData(**{**market_data_kwargs, field: price})
    assert exc.value.field == field


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "38.0", None, True])
def test_rejects_non_numeric_or_non_finite_close(
    market_data_kwargs: dict[str, Any], value: object
) -> None:
    with pytest.raises(ContractValidationError, match=r"MarketData\.close"):
        MarketData(**{**market_data_kwargs, "close": value})


def test_rejects_negative_volume_and_dividend(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="volume"):
        MarketData(**{**market_data_kwargs, "volume": -1})
    with pytest.raises(ContractValidationError, match="dividend"):
        MarketData(**{**market_data_kwargs, "dividend": -0.5})


def test_rejects_high_below_low(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError) as exc:
        MarketData(**{**market_data_kwargs, "high": 37.0, "low": 37.10})
    assert exc.value.field == "high"


def test_rejects_close_outside_high_low(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError) as exc:
        MarketData(**{**market_data_kwargs, "close": 39.0})
    assert exc.value.field == "close"


def test_rejects_datetime_as_trading_date(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match=r"MarketData\.date"):
        MarketData(**{**market_data_kwargs, "date": datetime(2026, 10, 1, 10, 0, tzinfo=UTC)})


def test_rejects_naive_available_at(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError, match="fuso horário"):
        MarketData(**{**market_data_kwargs, "available_at": datetime(2026, 10, 1, 18, 30)})


def test_rejects_availability_before_trading_date(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError) as exc:
        MarketData(
            **{**market_data_kwargs, "available_at": datetime(2026, 9, 30, 20, 0, tzinfo=UTC)}
        )
    assert exc.value.field == "available_at"


@pytest.mark.parametrize("ticker", ["", "   ", "PETR 4", 4])
def test_rejects_invalid_ticker(market_data_kwargs: dict[str, Any], ticker: object) -> None:
    with pytest.raises(ContractValidationError, match="ticker"):
        MarketData(**{**market_data_kwargs, "ticker": ticker})


def test_rejects_missing_required_field(market_data_kwargs: dict[str, Any]) -> None:
    data = MarketData(**market_data_kwargs).to_dict()
    del data["source"]
    with pytest.raises(ContractValidationError, match="source"):
        MarketData.from_dict(data)


def test_json_round_trip_preserves_record(market_data_kwargs: dict[str, Any]) -> None:
    bar = MarketData(**{**market_data_kwargs, "dividend": 0.42})

    restored = MarketData.from_dict(json.loads(json.dumps(bar.to_dict())))

    assert restored == bar
    assert restored.available_at.utcoffset() == bar.available_at.utcoffset()


def test_from_dict_accepts_record_without_optional_fields(
    market_data_kwargs: dict[str, Any],
) -> None:
    data = MarketData(**market_data_kwargs).to_dict()
    del data["dividend"]
    del data["schema_version"]

    assert MarketData.from_dict(data).dividend == 0.0


def test_from_dict_rejects_unknown_fields(market_data_kwargs: dict[str, Any]) -> None:
    data = {**MarketData(**market_data_kwargs).to_dict(), "adj_close": 37.9}
    with pytest.raises(ContractValidationError, match="desconhecidos"):
        MarketData.from_dict(data)


def test_from_dict_rejects_invalid_iso_date(market_data_kwargs: dict[str, Any]) -> None:
    data = {**MarketData(**market_data_kwargs).to_dict(), "date": "01/10/2026"}
    with pytest.raises(ContractValidationError, match="data ISO inválida"):
        MarketData.from_dict(data)


def test_schema_version_compatibility(market_data_kwargs: dict[str, Any]) -> None:
    assert MarketData(**{**market_data_kwargs, "schema_version": "1.3"}).schema_version == "1.3"
    with pytest.raises(ContractValidationError, match="incompatível"):
        MarketData(**{**market_data_kwargs, "schema_version": "2.0"})


def test_error_exposes_contract_and_field(market_data_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ContractValidationError) as exc:
        MarketData(**{**market_data_kwargs, "date": "2026-10-01"})
    assert exc.value.contract == "MarketData"
    assert exc.value.field == "date"
    assert isinstance(exc.value, ValueError)
