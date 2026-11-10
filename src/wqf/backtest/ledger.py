"""Immutable daily portfolio snapshots and auditable cash/quantity movements.

All amounts are BRL Decimal; long positions are positive and short negative.
Market value is signed, so short liabilities reduce NAV even though selling
borrowed shares previously increased cash. Do not subtract trading costs again
when calculating NAV: they have already been debited from cash by accounting.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from wqf.backtest.accounting import AccountState
from wqf.backtest.costs import brl


@dataclass(frozen=True)
class LedgerEvent:
    """One cash movement; trades also change signed units by ``quantity_delta``."""

    event_id: str
    session: date
    kind: str  # trade | borrow | cash_interest
    cash_delta: Decimal
    asset: str | None = None
    quantity_delta: int = 0
    price: Decimal | None = None
    transaction_cost: Decimal = Decimal(0)
    decision_date: date | None = None
    net_target_quantity: int | None = None
    strategy_targets: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or self.kind not in {"trade", "borrow", "cash_interest"}:
            raise ValueError("Invalid ledger event ID or kind")
        if type(self.session) is not date:
            raise TypeError("session must be a date")
        if not isinstance(self.cash_delta, Decimal) or not self.cash_delta.is_finite():
            raise ValueError("cash_delta must be finite Decimal")
        if type(self.quantity_delta) is not int:
            raise TypeError("quantity_delta must be an integer")
        object.__setattr__(self, "strategy_targets", MappingProxyType(dict(self.strategy_targets)))
        if self.kind == "trade":
            if not self.asset or self.quantity_delta == 0 or self.price is None:
                raise ValueError("Trades require an asset, nonzero delta and price")
            if self.price <= 0 or not self.price.is_finite():
                raise ValueError("Trade price must be finite and positive")
            if (
                type(self.decision_date) is not date
                or self.decision_date >= self.session
                or type(self.net_target_quantity) is not int
                or not self.strategy_targets
                or sum(self.strategy_targets.values()) != self.net_target_quantity
            ):
                raise ValueError("Trade must identify earlier signal and net strategy target")
        elif (
            self.quantity_delta != 0
            or self.transaction_cost != 0
            or self.decision_date is not None
            or self.net_target_quantity is not None
            or self.strategy_targets
        ):
            raise ValueError("Only trades can change quantities or include strategy targets")
        if self.transaction_cost < 0 or not self.transaction_cost.is_finite():
            raise ValueError("Invalid transaction cost")


@dataclass(frozen=True)
class DailySnapshot:
    """Portfolio after execution at session open and marking to session close."""

    session: date
    cash: Decimal
    positions: Mapping[str, int]
    closing_prices: Mapping[str, Decimal]
    net_market_value: Decimal
    nav: Decimal
    transaction_costs: Decimal
    borrow_costs: Decimal
    cash_interest: Decimal
    event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))
        object.__setattr__(self, "closing_prices", MappingProxyType(dict(self.closing_prices)))
        object.__setattr__(self, "event_ids", tuple(self.event_ids))


@dataclass(frozen=True)
class BacktestResult:
    """Complete deterministic output; no external storage/side-effects."""

    snapshots: tuple[DailySnapshot, ...]
    events: tuple[LedgerEvent, ...]
    final_account: AccountState
    strategy_targets: Mapping[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshots", tuple(self.snapshots))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "strategy_targets", MappingProxyType(dict(self.strategy_targets)))


def market_value(positions: Mapping[str, int], prices: Mapping[str, Decimal]) -> Decimal:
    """Sum signed mark-to-market values; refuse silently stale/missing marks."""
    missing = set(positions) - set(prices)
    if missing:
        raise ValueError(f"Missing closing price for held assets: {sorted(missing)}")
    total = Decimal(0)
    for asset, qty in positions.items():
        price = prices[asset]
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            raise ValueError(f"Invalid closing price for {asset}")
        total += qty * price
    return brl(total)


def snapshot(
    session: date,
    account: AccountState,
    closing_prices: Mapping[str, Decimal],
    *,
    transaction_costs: Decimal,
    borrow_costs: Decimal,
    cash_interest: Decimal,
    event_ids: tuple[str, ...],
) -> DailySnapshot:
    """Create a marked-to-market snapshot without subtracting costs twice."""
    value = market_value(account.positions, closing_prices)
    marks = {
        asset: closing_prices[asset] for asset in account.positions if account.positions[asset]
    }
    return DailySnapshot(
        session=session,
        cash=account.cash,
        positions=account.positions,
        closing_prices=marks,
        net_market_value=value,
        nav=brl(account.cash + value),
        transaction_costs=transaction_costs,
        borrow_costs=borrow_costs,
        cash_interest=cash_interest,
        event_ids=event_ids,
    )


def reconcile(result: BacktestResult, starting_cash: Decimal) -> None:
    """Raise on any mismatch between journal movements, positions and NAV."""
    cash = brl(starting_cash)
    positions: dict[str, int] = {}
    seen: set[str] = set()
    events_by_day: dict[date, list[LedgerEvent]] = {}
    for event in result.events:
        if event.event_id in seen:
            raise ValueError(f"Repeated event ID: {event.event_id}")
        seen.add(event.event_id)
        events_by_day.setdefault(event.session, []).append(event)
    if [snap.session for snap in result.snapshots] != sorted(
        {snap.session for snap in result.snapshots}
    ):
        raise ValueError("Snapshots must have unique sorted sessions")
    for daily in result.snapshots:
        day_events = events_by_day.pop(daily.session, [])
        if tuple(event.event_id for event in day_events) != daily.event_ids:
            raise ValueError(f"Event list differs from snapshot at {daily.session}")
        costs_on_day = sum(
            (event.transaction_cost for event in day_events if event.kind == "trade"),
            Decimal(0),
        )
        borrow_on_day = -sum(
            (event.cash_delta for event in day_events if event.kind == "borrow"),
            Decimal(0),
        )
        interest_on_day = sum(
            (event.cash_delta for event in day_events if event.kind == "cash_interest"),
            Decimal(0),
        )
        if (
            costs_on_day != daily.transaction_costs
            or borrow_on_day != daily.borrow_costs
            or interest_on_day != daily.cash_interest
        ):
            raise ValueError(f"Daily fees or interest do not reconcile at {daily.session}")
        for event in day_events:
            if event.kind == "trade":
                assert event.price is not None
                expected_cash = (
                    -brl(abs(event.quantity_delta) * event.price)
                    if event.quantity_delta > 0
                    else brl(abs(event.quantity_delta) * event.price)
                ) - event.transaction_cost
                if expected_cash != event.cash_delta:
                    raise ValueError(f"Trade cash delta does not reconcile: {event.event_id}")
            if event.kind == "borrow" and event.cash_delta > 0:
                raise ValueError("Borrow charges cannot credit cash")
            cash = brl(cash + event.cash_delta)
            if event.quantity_delta:
                if event.asset is None:
                    raise ValueError("Trade must identify its asset")
                positions[event.asset] = positions.get(event.asset, 0) + event.quantity_delta
                if positions[event.asset] == 0:
                    del positions[event.asset]
        if cash != daily.cash or positions != dict(daily.positions):
            raise ValueError(f"Cash/positions do not reconcile at {daily.session}")
        value = market_value(positions, daily.closing_prices)
        if value != daily.net_market_value or brl(cash + value) != daily.nav:
            raise ValueError(f"NAV does not reconcile at {daily.session}")
    if events_by_day:
        raise ValueError(f"Events without snapshots: {sorted(events_by_day)}")
    if result.snapshots and (
        cash != result.final_account.cash or positions != dict(result.final_account.positions)
    ):
        raise ValueError("Final account disagrees with the ledger")
