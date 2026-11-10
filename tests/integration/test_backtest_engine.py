"""End-to-end synthetic scenarios (no network, no proprietary data)."""

from datetime import date
from decimal import Decimal as D

import pytest

from wqf.backtest.costs import CostRates
from wqf.backtest.engine import MarketBar, TargetSignal, run_backtest
from wqf.backtest.ledger import reconcile

RATES = CostRates(other_rate=D("0.0015"), annual_borrow_rate=D("0.02"))
D1, D2, D3 = date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)


def bar(day, asset="PETR4", opening="10", closing="10"):
    return MarketBar(day, asset, D(opening), D(closing))


def target(day, qty, *, strategy="momentum", asset="PETR4", available=None):
    return TargetSignal(day, available or day, strategy, asset, qty)


def run(bars, signals, cash="1000", **kwargs):
    return run_backtest(bars, signals, starting_cash=D(cash), rates=RATES, **kwargs)


def test_signal_decided_at_close_executes_next_open_not_same_day():
    result = run(
        [
            bar(D1, closing="100"),
            bar(D2, opening="10", closing="11"),
            bar(D3, opening="12", closing="13"),
        ],
        [target(D1, 10), target(D2, 0)],
    )
    assert [snap.nav for snap in result.snapshots] == [D("1000.00"), D("1009.85"), D("1019.67")]
    assert [len(snap.event_ids) for snap in result.snapshots] == [0, 1, 1]
    assert result.snapshots[1].cash == D("899.85")
    assert result.snapshots[1].positions == {"PETR4": 10}
    assert result.snapshots[2].positions == {}
    assert result.final_account.cash == D("1019.67")
    assert [e.transaction_cost for e in result.events] == [D("0.15"), D("0.18")]
    reconcile(result, D(1000))


def test_short_sale_cover_borrow_and_nav_reconcile():
    result = run(
        [bar(D1), bar(D2), bar(D3, opening="9", closing="9")],
        [target(D1, -100, strategy="pairs"), target(D2, 0, strategy="pairs")],
    )
    d2 = result.snapshots[1]
    d3 = result.snapshots[2]
    assert d2.cash == D("1998.50")
    assert d2.net_market_value == D("-1000.00")
    assert d2.nav == D("998.50")
    assert d3.borrow_costs == D("0.05")
    # 1998.50 - 0.05 (borrow) - 900.00 (cover) - 1.35 (fee)
    assert d3.cash == d3.nav == D("1097.10")
    assert d3.positions == {}
    assert [e.kind for e in result.events] == ["trade", "borrow", "trade"]
    reconcile(result, D(1000))


def test_strategies_are_netted_into_single_trade():
    result = run(
        [bar(D1), bar(D2), bar(D3)],
        [target(D1, 10), target(D1, -4, strategy="pairs")],
    )
    trades = [event for event in result.events if event.kind == "trade"]
    assert len(trades) == 1
    assert trades[0].quantity_delta == 6
    assert trades[0].transaction_cost == D("0.09")
    assert trades[0].decision_date == D1
    assert trades[0].strategy_targets == {"momentum": 10, "pairs": -4}
    assert trades[0].net_target_quantity == 6
    assert result.snapshots[1].nav == D("999.91")
    assert result.snapshots[2].positions == {"PETR4": 6}
    assert result.strategy_targets == {("momentum", "PETR4"): 10, ("pairs", "PETR4"): -4}


def test_single_strategy_updates_without_overwriting_other_strategy():
    result = run(
        [bar(D1), bar(D2), bar(D3)],
        [target(D1, 10), target(D1, -4, strategy="pairs"), target(D2, 5)],
    )
    assert [event.quantity_delta for event in result.events if event.kind == "trade"] == [6, -5]
    assert result.snapshots[-1].positions == {"PETR4": 1}


def test_two_assets_in_same_session_and_mark_to_market():
    result = run(
        [
            bar(D1),
            bar(D1, "VALE3", "20", "20"),
            bar(D2, "VALE3", "20", "18"),
            bar(D2, closing="12"),
        ],
        [target(D1, 5), target(D1, -2, asset="VALE3", strategy="pairs")],
    )
    assert set(result.snapshots[1].positions) == {"PETR4", "VALE3"}
    # Gross cash: 1000 - 50 - .08 + 40 - .06 = 989.86; marked: 60 - 36 = 24
    assert result.snapshots[1].nav == D("1013.86")


def test_cash_remuneration_effective_rate_is_injected_not_assumed():
    result = run(
        [bar(D1), bar(D2), bar(D3)],
        [],
        cash_interval_rates={D2: D("0.01"), D3: D("0.01")},
    )
    assert [snap.nav for snap in result.snapshots] == [D("1000.00"), D("1010.00"), D("1020.10")]
    assert [e.kind for e in result.events] == ["cash_interest", "cash_interest"]
    assert run([bar(D1), bar(D2)], []).snapshots[-1].cash == D("1000.00")


def test_negative_cash_does_not_earn_cdi_and_is_not_margin_validated():
    result = run(
        [bar(D1), bar(D2, opening="1000", closing="1000"), bar(D3, opening="1000", closing="1000")],
        [target(D1, 2)],
        cash_interval_rates={D2: D(0), D3: D("0.01")},
    )
    assert result.snapshots[1].cash == D("-1003.00")
    assert result.snapshots[2].cash_interest == D(0)
    assert result.snapshots[2].nav == result.snapshots[1].nav


def test_missing_bars_for_execution_or_held_assets_are_rejected():
    with pytest.raises(ValueError, match="Missing execution price"):
        run([bar(D1, "PETR4"), bar(D2, "VALE3")], [target(D1, 1)])
    with pytest.raises(ValueError, match="Missing closing price"):
        run([bar(D1), bar(D2), bar(D3, "VALE3")], [target(D1, 1)])


def test_duplicate_data_or_signals_are_rejected():
    with pytest.raises(ValueError, match="Repeated market bar"):
        run([bar(D1), bar(D1)], [])
    with pytest.raises(ValueError, match="Duplicate target"):
        run([bar(D1), bar(D2)], [target(D1, 1), target(D1, 2)])


def test_prevents_future_inputs_and_unexecutable_signals():
    with pytest.raises(ValueError, match="not yet available"):
        target(D1, 1, available=D2)
    with pytest.raises(ValueError, match="no future execution session"):
        run([bar(D1), bar(D2)], [target(D2, 1)])
    with pytest.raises(ValueError, match="market session"):
        run([bar(D1), bar(D2)], [target(D3, 1)])


def test_strict_monthly_first_session_execution():
    october_last = date(2026, 10, 30)
    november_first = date(2026, 11, 2)
    november_second = date(2026, 11, 3)
    bars = [bar(october_last), bar(november_first), bar(november_second)]
    result = run(bars, [target(october_last, 3)], monthly_first_session_only=True)
    assert result.snapshots[1].positions == {"PETR4": 3}
    with pytest.raises(ValueError, match="rebalance calendar"):
        run(bars, [target(november_first, 3)], monthly_first_session_only=True)


def test_cash_rate_dates_must_cover_intervals():
    with pytest.raises(ValueError, match="cover exactly"):
        run([bar(D1), bar(D2)], [], cash_interval_rates={})
    with pytest.raises(ValueError, match="Invalid effective"):
        run([bar(D1), bar(D2)], [], cash_interval_rates={D2: D("NaN")})


def test_borrow_accrues_elapsed_calendar_days_including_weekend():
    fri = date(2026, 11, 6)
    mon = date(2026, 11, 9)
    tue = date(2026, 11, 10)
    result = run(
        [bar(fri), bar(mon), bar(tue)],
        [target(fri, -100), target(mon, 0)],
    )
    # Monday->Tuesday = 1 day, prior close not open.
    assert result.snapshots[-1].borrow_costs == D("0.05")
    # For weekend hold, open short Friday instead: one earlier trading day.
    thurs = date(2026, 11, 5)
    result2 = run([bar(thurs), bar(fri), bar(mon), bar(tue)], [target(thurs, -100)])
    assert result2.snapshots[2].borrow_costs == D("0.16")  # 3 elapsed days


def test_single_bar_empty_signals_is_valid():
    result = run([bar(D1)], [])
    assert len(result.snapshots) == 1
    assert result.snapshots[0].nav == D("1000.00")
    assert result.events == ()
