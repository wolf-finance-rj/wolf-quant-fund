"""Fixtures sintéticas dos contratos: registros válidos que cada teste altera campo a campo."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

BRT = timezone(timedelta(hours=-3), "BRT")


@pytest.fixture
def market_data_kwargs() -> dict[str, Any]:
    """Barra diária válida de PETR4 disponível após o fechamento do pregão."""
    return {
        "ticker": "PETR4",
        "date": date(2026, 10, 1),
        "open": 37.50,
        "high": 38.20,
        "low": 37.10,
        "close": 38.00,
        "volume": 45_000_000,
        "available_at": datetime(2026, 10, 1, 18, 30, tzinfo=BRT),
        "source": "synthetic-equities-v1",
    }


@pytest.fixture
def strategy_signal_kwargs() -> dict[str, Any]:
    """Sinal comprado válido da estratégia Momentum."""
    return {
        "decision_date": date(2026, 10, 1),
        "ticker": "VALE3",
        "strategy": "momentum_12_1",
        "direction": "long",
        "target_weight": 0.05,
    }


@pytest.fixture
def simulated_trade_kwargs() -> dict[str, Any]:
    """Compra válida de 100 ações de ITUB4 com custos."""
    return {
        "trade_date": date(2026, 10, 2),
        "ticker": "ITUB4",
        "quantity": 100,
        "execution_price": 35.40,
        "costs": 1.25,
    }
