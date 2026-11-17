"""Testes unitários das regras de sinal de Pairs Trading (Issue #14)."""

import math
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest

from wqf.backtest.engine import MarketBar
from wqf.strategies.pairs import (
    PairsSignalConfig,
    compute_rolling_zscore,
    generate_pairs_signals,
    load_pairs_config,
)

A, B = "AAAA3", "BBBB3"
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "parametros.toml"

# log(A/B) oscila perto de zero; com window=5 a janela fica pronta no índice 4.
CALM = [0, 0.01, -0.01, 0.01, -0.01, 0, 0.01, -0.01]
SHORT_THEN_REVERT = [*CALM, 0.10, 0.06, 0.02, 0, 0.01, -0.01]
LONG_THEN_REVERT = [*CALM, -0.10, -0.06, -0.02, 0, 0.01]
DIVERGE = [*CALM, 0.04, 0.10, 0.30, 0.31, 0.32, 0.33, 0.40, 0.2, 0.1, 0.5, 0.5]


def sessions(n: int, start: date = date(2026, 1, 5)) -> list[date]:
    days, day = [], start
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def make_bars(spreads, *, skip=None):
    """A = 10*exp(spread), B = 10. ``skip`` = {índice: ativo ausente na sessão}."""
    skip = skip or {}
    out = []
    for i, (day, s) in enumerate(zip(sessions(len(spreads)), spreads, strict=True)):
        price_a = D(str(round(10 * math.exp(s), 4)))
        if skip.get(i) != A:
            out.append(MarketBar(day, A, price_a, price_a))
        if skip.get(i) != B:
            out.append(MarketBar(day, B, D(10), D(10)))
    return out


def cfg(**kwargs) -> PairsSignalConfig:
    params = {"window": 5, "entry_z": 1.5, "exit_z": 0.5}
    params.update(kwargs)
    return PairsSignalConfig(A, B, D(1000), **params)


def actions(report):
    return [(i, d.action) for i, d in enumerate(report.decisions) if d.action != "none"]


def test_short_spread_entry_and_mean_exit_emit_one_signal_per_leg() -> None:
    report = generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg())
    assert actions(report) == [(8, "enter_short_spread"), (10, "exit_mean"), (13, "end_of_data")]
    entry_day, exit_day = report.decisions[8].session, report.decisions[10].session
    price_a = D(str(round(10 * math.exp(0.10), 4)))
    qty_a = int(D(1000) / price_a)
    assert [(s.decision_date, s.asset, s.target_quantity) for s in report.signals] == [
        (entry_day, A, -qty_a),
        (entry_day, B, 100),
        (exit_day, A, 0),
        (exit_day, B, 0),
    ]
    assert all(s.available_at == s.decision_date for s in report.signals)
    assert {s.strategy for s in report.signals} == {"pairs:AAAA3-BBBB3"}
    assert report.decisions[9].state_after == "short_spread"
    assert report.decisions[10].state_after == "flat"


def test_long_spread_buys_a_and_sells_b() -> None:
    report = generate_pairs_signals(make_bars(LONG_THEN_REVERT), cfg())
    assert actions(report)[:2] == [(8, "enter_long_spread"), (10, "exit_mean")]
    entry = report.signals[:2]
    assert entry[0].target_quantity > 0 and entry[1].target_quantity == -100


def test_z_score_matches_issue_5_with_strictly_past_window() -> None:
    report = generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg())
    expected = compute_rolling_zscore(
        [math.log(float(round(10 * math.exp(s), 4)) / 10) for s in SHORT_THEN_REVERT], window=5
    )
    for decision, stat in zip(report.decisions, expected, strict=True):
        if stat.z_score is None:
            assert decision.z_score is None
        else:
            assert decision.z_score == pytest.approx(stat.z_score)
    assert [d.z_score for d in report.decisions[:4]] == [None] * 4


def test_future_prices_do_not_change_past_decisions() -> None:
    full = generate_pairs_signals(make_bars(SHORT_THEN_REVERT), cfg())
    altered = SHORT_THEN_REVERT[:10] + [0.9, -0.9, 0.9, -0.9]
    changed = generate_pairs_signals(make_bars(altered), cfg())
    assert full.decisions[:10] == changed.decisions[:10]
    assert [s for s in full.signals if s.decision_date <= full.decisions[9].session] == [
        s for s in changed.signals if s.decision_date <= changed.decisions[9].session
    ]


def test_no_decision_on_last_session_because_there_is_no_execution() -> None:
    report = generate_pairs_signals(make_bars(SHORT_THEN_REVERT[:9]), cfg())
    assert report.decisions[-1].action == "end_of_data"
    assert report.signals == ()


def test_gap_while_flat_skips_session_and_restarts_window() -> None:
    report = generate_pairs_signals(make_bars(SHORT_THEN_REVERT, skip={6: B}), cfg())
    assert report.decisions[6].action == "gap"
    # Depois da lacuna o z-score só volta com 5 sessões contíguas (índice 11).
    assert [d.z_score for d in report.decisions[7:11]] == [None] * 4
    assert report.decisions[11].z_score is not None
    assert all(not d.action.startswith("enter") for d in report.decisions[:11])


def test_gap_with_open_pair_is_rejected_not_ignored() -> None:
    with pytest.raises(ValueError, match="Lacuna de preço .*BBBB3.*par aberto"):
        generate_pairs_signals(make_bars(SHORT_THEN_REVERT, skip={9: B}), cfg())


def test_stop_exit_and_cooldown_before_reentry() -> None:
    report = generate_pairs_signals(make_bars(DIVERGE), cfg(entry_z=1.2, exit_z=0.3, stop_z=1.7))
    assert actions(report) == [(8, "enter_short_spread"), (14, "exit_stop"), (18, "end_of_data")]
    # Em 15 e 17 |z| >= entry_z, mas o cooldown impede reentrar logo após o stop.
    assert abs(report.decisions[15].z_score) >= 1.2
    assert abs(report.decisions[17].z_score) >= 1.2


def test_max_holding_sessions_closes_pair() -> None:
    report = generate_pairs_signals(
        make_bars(DIVERGE), cfg(entry_z=1.2, exit_z=0.3, max_holding_sessions=3)
    )
    assert actions(report)[:2] == [(8, "enter_short_spread"), (11, "exit_time")]


def test_sizing_by_method() -> None:
    bars = make_bars(SHORT_THEN_REVERT)
    log_hedged = generate_pairs_signals(bars, cfg(hedge_ratio=0.5)).signals
    assert log_hedged[1].target_quantity == 50  # 1000 * 0.5 / 10
    diff = generate_pairs_signals(bars, cfg(method="hedge_diff", hedge_ratio=0.5)).signals
    assert diff[1].target_quantity == round(abs(diff[0].target_quantity) * 0.5)
    with pytest.raises(ValueError, match="insuficiente"):
        generate_pairs_signals(bars, replace(cfg(), leg_notional_brl=D(5)))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"asset_b": A},
        {"asset_a": " "},
        {"leg_notional_brl": D(0)},
        {"leg_notional_brl": 1000},
        {"window": 1},
        {"exit_z": 2.0, "entry_z": 1.5},
        {"exit_z": -0.1},
        {"entry_z": math.inf},
        {"stop_z": 1.0},
        {"max_holding_sessions": 0},
        {"method": "ols"},
        {"hedge_ratio": 0},
        {"strategy": ""},
    ],
)
def test_invalid_config_is_rejected(kwargs) -> None:
    params = {"asset_a": A, "asset_b": B, "leg_notional_brl": D(1000)}
    params.update(kwargs)
    with pytest.raises(ValueError):
        PairsSignalConfig(**params)


def test_duplicate_bar_is_rejected() -> None:
    bars = make_bars(CALM)
    with pytest.raises(ValueError, match="Barra repetida"):
        generate_pairs_signals([*bars, bars[0]], cfg())


def test_load_reference_config_from_repository() -> None:
    config = load_pairs_config(CONFIG_PATH, asset_a="PETR3", asset_b="PETR4", hedge_ratio=0.9)
    assert (config.window, config.entry_z, config.exit_z) == (20, 2.0, 0.5)
    assert config.leg_notional_brl == D(1000000)
    assert config.hedge_ratio == 0.9
    assert config.strategy_id == "pairs:PETR3-PETR4"
