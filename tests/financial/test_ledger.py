"""Ledger invariants with explicit manually checked BRL results."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from wqf.backtest.accounting import AccountState
from wqf.backtest.ledger import BacktestResult, LedgerEvent, market_value, reconcile, snapshot


def test_market_value_long_short_and_nav_no_double_cost():
    state = AccountState(D("1100.00"), {"PETR4": 10, "VALE3": -5})
    snap = snapshot(
        date(2026, 11, 2),
        state,
        {"PETR4": D(12), "VALE3": D(8)},
        transaction_costs=D("1.00"),
        borrow_costs=D("0.00"),
        cash_interest=D("0.00"),
        event_ids=(),
    )
    assert snap.net_market_value == D("80.00")  # 120 - 40
    assert snap.nav == D("1180.00")  # costs already present in cash
    with pytest.raises(TypeError):
        snap.positions["PETR4"] = 0


def test_missing_mark_is_rejected():
    with pytest.raises(ValueError, match="Missing closing price"):
        market_value({"PETR4": 1}, {})


def test_reconcile_detects_tampered_nav_and_cash():
    day = date(2026, 11, 2)
    event = LedgerEvent(
        "trade:1",
        day,
        "trade",
        D("-100.15"),
        "PETR4",
        10,
        D(10),
        D("0.15"),
        date(2026, 10, 30),
        10,
        {"momentum": 10},
    )
    state = AccountState(D("899.85"), {"PETR4": 10})
    snap = snapshot(
        day,
        state,
        {"PETR4": D(11)},
        transaction_costs=D("0.15"),
        borrow_costs=D(0),
        cash_interest=D(0),
        event_ids=(event.event_id,),
    )
    output = BacktestResult((snap,), (event,), state)
    reconcile(output, D(1000))
    with pytest.raises(ValueError, match="NAV"):
        reconcile(BacktestResult((replace(snap, nav=D(2000)),), (event,), state), D(1000))
    with pytest.raises(ValueError, match="Cash/positions"):
        reconcile(BacktestResult((replace(snap, cash=D(900)),), (event,), state), D(1000))
    with pytest.raises(ValueError, match="Repeated event"):
        reconcile(BacktestResult((snap,), (event, event), state), D(1000))


def test_no_asset_or_nonfinite_price_is_invalid():
    with pytest.raises(ValueError, match="Invalid closing price"):
        market_value({"PETR4": 1}, {"PETR4": D("NaN")})
    with pytest.raises(ValueError, match="Trades require"):
        LedgerEvent("trade:x", date(2026, 11, 2), "trade", D(0))
