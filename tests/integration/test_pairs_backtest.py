"""Simulação sintética de ponta a ponta: sinais de Pairs (#14) no motor comum (#9)."""

import math
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest

from wqf.backtest.costs import CostRates, brl, load_cost_rates
from wqf.backtest.engine import MarketBar, run_backtest
from wqf.backtest.ledger import reconcile
from wqf.strategies.pairs import PairsSignalConfig, generate_pairs_signals, run_pairs_backtest

A, B, C = "AAAA3", "BBBB3", "CCCC3"
RATES = load_cost_rates(Path(__file__).resolve().parents[2] / "config" / "parametros.toml")
CALM = [0, 0.01, -0.01, 0.01, -0.01, 0, 0.01, -0.01]
# Entrada short_spread no índice 8 e saída pela média no índice 10.
SPREADS = [*CALM, 0.10, 0.06, 0.02, 0, 0.01, -0.01]


def sessions(n: int) -> list[date]:
    days, day = [], date(2026, 1, 5)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def fixture_bars(spreads=SPREADS, *, extra_asset=None):
    """Abertura difere do fechamento para provar a execução na abertura seguinte."""
    out = []
    for day, s in zip(sessions(len(spreads)), spreads, strict=True):
        close_a = D(str(round(10 * math.exp(s), 4)))
        out.append(MarketBar(day, A, close_a + D("0.05"), close_a))
        out.append(MarketBar(day, B, D("10.02"), D(10)))
        if extra_asset:
            out.append(MarketBar(day, extra_asset, D(20), D(20)))
    return out


def config(**kwargs):
    return PairsSignalConfig(A, B, D(1000), window=5, entry_z=1.5, exit_z=0.5, **kwargs)


def test_pairs_prototype_runs_end_to_end_and_reconciles() -> None:
    bars = fixture_bars()
    report, result = run_pairs_backtest(bars, config(), starting_cash=D(10000), rates=RATES)
    reconcile(result, D(10000))

    days = sessions(len(SPREADS))
    trades = [e for e in result.events if e.kind == "trade"]
    # Decisão no fechamento de D8 -> execução na abertura de D9; saída D10 -> D11.
    assert [(t.session, t.decision_date, t.asset) for t in trades] == [
        (days[9], days[8], A),
        (days[9], days[8], B),
        (days[11], days[10], A),
        (days[11], days[10], B),
    ]
    by_key = {(b.session, b.asset): b for b in bars}
    for trade in trades:
        assert trade.price == by_key[(trade.session, trade.asset)].open_price
        assert trade.strategy_targets.keys() == {"pairs:AAAA3-BBBB3"}
    entry_a, entry_b = trades[0], trades[1]
    assert entry_a.quantity_delta < 0 and entry_b.quantity_delta == 100
    assert trades[2].quantity_delta == -entry_a.quantity_delta
    assert trades[3].quantity_delta == -100

    # Par encerrado: sem posições, NAV = caixa ao fim.
    assert result.snapshots[-1].positions == {}
    assert result.snapshots[-1].nav == result.final_account.cash
    assert result.snapshots[9].positions == {A: entry_a.quantity_delta, B: 100}
    assert report.decisions[-1].state_after == "flat"


def test_costs_and_nav_come_only_from_common_engine() -> None:
    bars = fixture_bars()
    report, result = run_pairs_backtest(bars, config(), starting_cash=D(10000), rates=RATES)
    direct = run_backtest(bars, report.signals, starting_cash=D(10000), rates=RATES)
    assert result == direct

    trades = [e for e in result.events if e.kind == "trade"]
    for trade in trades:
        notional = brl(abs(trade.quantity_delta) * trade.price)
        assert trade.transaction_cost == brl(notional * D("0.0015"))
    # Aluguel cobrado apenas sobre a perna vendida (A) enquanto o par está aberto.
    borrow = [e for e in result.events if e.kind == "borrow"]
    assert borrow and {e.asset for e in borrow} == {A}
    total_costs = sum(s.transaction_costs + s.borrow_costs for s in result.snapshots)
    assert total_costs == sum(t.transaction_cost for t in trades) - sum(
        e.cash_delta for e in borrow
    )

    free = run_pairs_backtest(bars, config(), starting_cash=D(10000), rates=CostRates())[1]
    assert free.snapshots[-1].nav - result.snapshots[-1].nav == total_costs


def test_two_pairs_sharing_an_asset_keep_separate_targets_and_net() -> None:
    bars = fixture_bars(extra_asset=C)
    signals_ab = generate_pairs_signals(bars, config()).signals
    signals_ac = generate_pairs_signals(
        bars, PairsSignalConfig(A, C, D(1000), window=5, entry_z=1.5, exit_z=0.5)
    ).signals
    assert {s.strategy for s in signals_ab} != {s.strategy for s in signals_ac}
    result = run_backtest(bars, [*signals_ab, *signals_ac], starting_cash=D(10000), rates=RATES)
    reconcile(result, D(10000))
    entry_a = next(e for e in result.events if e.kind == "trade" and e.asset == A)
    assert len(entry_a.strategy_targets) == 2
    assert entry_a.net_target_quantity == sum(entry_a.strategy_targets.values())


def test_price_gap_on_open_leg_stops_simulation() -> None:
    bars = [b for b in fixture_bars() if not (b.session == sessions(10)[9] and b.asset == B)]
    with pytest.raises(ValueError, match="Lacuna de preço"):
        run_pairs_backtest(bars, config(), starting_cash=D(10000), rates=RATES)
