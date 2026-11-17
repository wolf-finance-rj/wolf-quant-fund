"""Simulação sintética completa: sinais de Pairs (#14) no motor comum (#9)."""

import math
from datetime import date, timedelta
from decimal import Decimal as D

from wqf.backtest.costs import CostRates, brl
from wqf.backtest.engine import MarketBar, run_backtest
from wqf.backtest.ledger import reconcile
from wqf.strategies.pairs import PairsSignalConfig, generate_pairs_signals

A, B = "AAAA3", "BBBB3"
RATES = CostRates(other_rate=D("0.0015"), annual_borrow_rate=D("0.02"))
CONFIG = PairsSignalConfig(A, B, D(1000), window=5, entry_z=1.5, exit_z=0.5)
CASH = D(10000)
# Entrada short spread decidida na sessão 8, saída decidida na sessão 10.
SPREADS = [0, 0.01, -0.01, 0.01, -0.01, 0, 0.01, -0.01, 0.10, 0.06, 0.02, 0, 0.01, -0.01]


def sessions(n: int) -> list[date]:
    days, day = [], date(2026, 1, 5)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def fixture_bars():
    """Abertura diferente do fechamento para evidenciar a execução na abertura seguinte."""
    out = []
    for day, s in zip(sessions(len(SPREADS)), SPREADS, strict=True):
        close_a = D(str(round(10 * math.exp(s), 4)))
        out.append(MarketBar(day, A, close_a + D("0.05"), close_a))
        out.append(MarketBar(day, B, D("10.02"), D(10)))
    return out


def simulate(rates=RATES):
    bars = fixture_bars()
    signals = generate_pairs_signals(bars, CONFIG)
    return bars, run_backtest(bars, signals, starting_cash=CASH, rates=rates)


def test_pairs_prototype_runs_end_to_end_with_fixtures() -> None:
    bars, result = simulate()
    reconcile(result, CASH)
    days = sessions(len(SPREADS))
    trades = [e for e in result.events if e.kind == "trade"]
    assert [(t.decision_date, t.session, t.asset) for t in trades] == [
        (days[8], days[9], A),
        (days[8], days[9], B),
        (days[10], days[11], A),
        (days[10], days[11], B),
    ]
    opening = {(b.session, b.asset): b.open_price for b in bars}
    assert all(t.price == opening[(t.session, t.asset)] for t in trades)
    assert result.snapshots[9].positions[A] < 0 < result.snapshots[9].positions[B]
    # Par encerrado: sem posições e NAV igual ao caixa.
    assert result.snapshots[-1].positions == {}
    assert result.snapshots[-1].nav == result.final_account.cash


def test_costs_and_nav_are_computed_only_by_common_engine() -> None:
    _, result = simulate()
    trades = [e for e in result.events if e.kind == "trade"]
    borrow = [e for e in result.events if e.kind == "borrow"]
    for trade in trades:
        notional = brl(abs(trade.quantity_delta) * trade.price)
        assert trade.transaction_cost == brl(notional * RATES.other_rate)
    assert borrow and {e.asset for e in borrow} == {A}  # aluguel só na perna vendida
    total_costs = sum(t.transaction_cost for t in trades) - sum(e.cash_delta for e in borrow)

    _, free = simulate(CostRates())
    assert free.snapshots[-1].nav - result.snapshots[-1].nav == total_costs
