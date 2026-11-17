"""Testes unitários dos sinais de Pairs Trading (Issue #14)."""

import math
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from wqf.backtest.engine import MarketBar
from wqf.strategies.pairs import PairsSignalConfig, generate_pairs_signals

A, B = "AAAA3", "BBBB3"

# log(A/B) oscila perto de zero; com window=5 o primeiro z-score sai no índice 4.
CALM = [0, 0.01, -0.01, 0.01, -0.01, 0, 0.01, -0.01]
SHORT_THEN_REVERT = [*CALM, 0.10, 0.06, 0.02, 0, 0.01, -0.01]  # entra em 8, sai em 10
LONG_THEN_REVERT = [*CALM, -0.10, -0.06, -0.02, 0, 0.01]  # entra em 8, sai em 10


def sessions(n: int) -> list[date]:
    days, day = [], date(2026, 1, 5)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def make_bars(spreads, *, missing=None):
    """A = 10*exp(spread), B = 10. ``missing`` = {índice da sessão: ativo sem barra}."""
    missing = missing or {}
    out = []
    for i, (day, s) in enumerate(zip(sessions(len(spreads)), spreads, strict=True)):
        price_a = D(str(round(10 * math.exp(s), 4)))
        if missing.get(i) != A:
            out.append(MarketBar(day, A, price_a, price_a))
        if missing.get(i) != B:
            out.append(MarketBar(day, B, D(10), D(10)))
    return out


def cfg(**kwargs) -> PairsSignalConfig:
    params = {"window": 5, "entry_z": 1.5, "exit_z": 0.5}
    params.update(kwargs)
    return PairsSignalConfig(A, B, D(1000), **params)


def summary(signals, spreads):
    days = sessions(len(spreads))
    return [(days.index(s.decision_date), s.asset, s.target_quantity) for s in signals]


def test_short_spread_entry_and_pair_close() -> None:
    signals = generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg())
    qty_a = int(D(1000) / D(str(round(10 * math.exp(0.10), 4))))
    assert summary(signals, SHORT_THEN_REVERT) == [
        (8, A, -qty_a),  # z alto: vende A
        (8, B, 100),  # compra B
        (10, A, 0),  # spread voltou: encerra as duas pernas
        (10, B, 0),
    ]
    assert all(s.available_at == s.decision_date for s in signals)
    assert {s.strategy for s in signals} == {"pairs"}


def test_long_spread_entry_and_pair_close() -> None:
    signals = generate_pairs_signals(make_bars(LONG_THEN_REVERT), cfg())
    assert [(i, asset, qty > 0) for i, asset, qty in summary(signals, LONG_THEN_REVERT)[:2]] == [
        (8, A, True),
        (8, B, False),
    ]
    assert summary(signals, LONG_THEN_REVERT)[2:] == [(10, A, 0), (10, B, 0)]


def test_pair_closes_when_spread_crosses_to_the_other_side() -> None:
    spreads = [*CALM, 0.10, -0.05, -0.04, -0.03]
    signals = generate_pairs_signals(make_bars(spreads), cfg())
    assert summary(signals, spreads)[2:] == [(9, A, 0), (9, B, 0)]


def test_thresholds_and_window_are_configurable() -> None:
    bars = make_bars(SHORT_THEN_REVERT)
    assert generate_pairs_signals(bars, cfg(entry_z=1.9)) == []
    assert summary(generate_pairs_signals(bars, cfg(exit_z=0.7)), SHORT_THEN_REVERT)[2][0] == 9
    assert generate_pairs_signals(bars, cfg(window=20)) == []


def test_no_signal_without_full_window_or_on_last_session() -> None:
    assert generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg(window=10)) == []
    # Sessão 8 seria entrada, mas é a última: não há abertura seguinte para executar.
    assert generate_pairs_signals(make_bars(SHORT_THEN_REVERT[:9]), cfg()) == []


def test_future_prices_do_not_change_past_signals() -> None:
    altered = SHORT_THEN_REVERT[:10] + [0.9, -0.9, 0.9, -0.9]
    original = generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg())
    changed = generate_pairs_signals(make_bars(altered), cfg())
    cutoff = sessions(10)[9]
    assert [s for s in original if s.decision_date <= cutoff] == [
        s for s in changed if s.decision_date <= cutoff
    ]


def test_gap_while_flat_restarts_zscore_window() -> None:
    # Sem lacuna, entraria na sessão 8. Com B ausente na 6, a janela recomeça na 7
    # e só volta a ter 5 sessões contíguas na 11.
    signals = generate_pairs_signals(make_bars(SHORT_THEN_REVERT, missing={6: B}), cfg())
    assert all(s.decision_date >= sessions(12)[11] for s in signals)


def test_gap_with_open_pair_is_rejected() -> None:
    with pytest.raises(ValueError, match="Lacuna de preço"):
        generate_pairs_signals(make_bars(SHORT_THEN_REVERT, missing={9: B}), cfg())


def test_duplicate_bar_is_rejected() -> None:
    bars = make_bars(CALM)
    with pytest.raises(ValueError, match="Barra repetida"):
        generate_pairs_signals([*bars, bars[0]], cfg())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"asset_b": A},
        {"leg_notional_brl": D(0)},
        {"window": 1},
        {"exit_z": 2.0},
        {"exit_z": -0.1},
        {"method": "ols"},
    ],
)
def test_invalid_config_is_rejected(kwargs) -> None:
    params = {"asset_a": A, "asset_b": B, "leg_notional_brl": D(1000), "entry_z": 1.5}
    params.update(kwargs)
    with pytest.raises(ValueError):
        PairsSignalConfig(**params)
