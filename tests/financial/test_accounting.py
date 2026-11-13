"""Explicit hand-calculated synthetic trades (BRL)."""

from decimal import Decimal as D

import pytest

from wqf.backtest.accounting import (
    AccountState,
    Side,
    Trade,
    apply_borrow_charge,
    apply_trade,
)
from wqf.backtest.costs import CostRates, borrow_cost, load_cost_rates, transaction_costs

RATES = CostRates(other_rate=D("0.0015"), annual_borrow_rate=D("0.02"))


def execute(account, trade_id, side, qty, price="10", asset="PETR4"):
    return apply_trade(account, Trade(trade_id, asset, side, qty, D(price)), RATES)


def test_buy_charges_cost_once_and_does_not_mutate_prior_account():
    before = AccountState(D(1000))
    result = execute(before, "1", Side.BUY, 10)
    # Notional 100.00; fee 0.15; cash = 1000 - 100 - 0.15.
    assert result.notional == D("100.00")
    assert result.costs.total == D("0.15")
    assert result.cash_delta == D("-100.15")
    assert result.account.cash == D("899.85")
    assert dict(result.account.positions) == {"PETR4": 10}
    assert before.cash == D("1000.00")
    assert dict(before.positions) == {}
    with pytest.raises(ValueError, match="Duplicate"):
        execute(result.account, "1", Side.BUY, 10)


def test_sell_closes_long():
    first = execute(AccountState(D(1000)), "buy", Side.BUY, 10).account
    second = execute(first, "sell", Side.SELL, 10, "12")
    # 899.85 + 120.00 - 0.18 = 1019.67
    assert second.account.cash == D("1019.67")
    assert dict(second.account.positions) == {}


def test_short_sale_and_cover():
    sold = execute(AccountState(D(1000)), "short", Side.SELL, 10)
    # 1000 + 100 - 0.15 = 1099.85, position -10.
    assert sold.account.cash == D("1099.85")
    assert sold.account.positions["PETR4"] == -10
    covered = execute(sold.account, "cover", Side.BUY, 10, "9")
    # 1099.85 - 90 - 0.14 = 1009.71 (round-half-up 0.135).
    assert covered.account.cash == D("1009.71")
    assert not covered.account.positions


def test_reversal_long_to_short_charges_once():
    long = execute(AccountState(D(1000)), "b", Side.BUY, 5).account
    reversed_trade = execute(long, "s", Side.SELL, 8)
    assert reversed_trade.account.positions["PETR4"] == -3
    # 1000 - 50 - 0.08 + 80 - 0.12 = 1029.80
    assert reversed_trade.account.cash == D("1029.80")
    assert reversed_trade.costs.total == D("0.12")


def test_reversal_short_to_long_charges_once():
    short = execute(AccountState(D(1000)), "s", Side.SELL, 5).account
    reversed_trade = execute(short, "b", Side.BUY, 8)
    assert reversed_trade.account.positions["PETR4"] == 3
    # 1000 + 50 - 0.08 - 80 - 0.12 = 969.80
    assert reversed_trade.account.cash == D("969.80")


def test_borrow_charge_idempotency_and_long_exclusion():
    short = execute(AccountState(D(1000)), "s", Side.SELL, 100).account
    account, fee = apply_borrow_charge(
        short,
        charge_id="PETR4-day-1",
        asset="PETR4",
        price=D(10),
        days=1,
        rates=RATES,
    )
    # 100 shares * 10 BRL * 2% / 365 = BRL 0.05
    assert fee == D("0.05")
    assert account.cash == D("1998.45")
    with pytest.raises(ValueError, match="Duplicate"):
        apply_borrow_charge(
            account,
            charge_id="PETR4-day-1",
            asset="PETR4",
            price=D(10),
            days=1,
            rates=RATES,
        )
    long = execute(AccountState(D(2000)), "b", Side.BUY, 10).account
    _, fee = apply_borrow_charge(
        long,
        charge_id="no-short",
        asset="PETR4",
        price=D(10),
        days=1,
        rates=RATES,
    )
    assert fee == D("0.00")


def test_cost_breakdown_is_not_added_twice():
    split = CostRates(
        brokerage_rate=D("0.0010"),
        exchange_rate=D("0.0003"),
        impact_rate=D("0.0002"),
        other_rate=D(0),
        annual_borrow_rate=D("0.02"),
    )
    result = transaction_costs(D(1000), split)
    assert (result.brokerage, result.exchange, result.impact, result.other) == (
        D("1.00"),
        D("0.30"),
        D("0.20"),
        D("0.00"),
    )
    assert result.total == D("1.50")
    assert RATES.transaction_rate == D("0.0015")


@pytest.mark.parametrize("price,quantity", [(D(0), 1), (D(-1), 1), (D(10), 0)])
def test_invalid_trade_inputs(price, quantity):
    with pytest.raises(ValueError):
        Trade("x", "PETR4", Side.BUY, quantity, price)


def test_negative_rates_and_borrow_inputs_rejected():
    with pytest.raises(ValueError):
        CostRates(other_rate=D("-0.01"))
    with pytest.raises(ValueError):
        borrow_cost(1, D(10), -1, RATES)


def test_different_assets_stay_independent():
    first = execute(AccountState(D(1000)), "a", Side.BUY, 2).account
    second = execute(first, "b", Side.SELL, 1, asset="VALE3").account
    assert dict(second.positions) == {"PETR4": 2, "VALE3": -1}


def test_load_rates_from_toml(tmp_path):
    config = tmp_path / "parametros.toml"
    config.write_text(
        "[backtest.costs]\n"
        'brokerage_rate = "0"\nexchange_rate = "0"\n'
        'impact_rate = "0"\nother_rate = "0.0015"\n'
        'annual_borrow_rate = "0.02"\n',
        encoding="utf-8",
    )
    loaded = load_cost_rates(config)
    assert loaded == RATES


def test_small_notional_cost_breakdown_never_negative():
    split = CostRates(
        brokerage_rate=D("0.0005"),
        exchange_rate=D("0.0005"),
        impact_rate=D("0.0005"),
    )
    costs = transaction_costs(D(10), split)
    assert costs.total == D("0.02")
    assert all(x >= 0 for x in (costs.brokerage, costs.exchange, costs.impact, costs.other))
