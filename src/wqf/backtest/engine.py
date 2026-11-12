"""Deterministic date-by-date backtest using Issue #6 accounting and costs.

Contract: decision at session close -> execute at NEXT session open; mark
positions at the same session close. One net trade per asset and execution
session. Never execute at a close already used to compute a signal.

Provisional conventions pending fund governance approval. Signal provenance,
corporate actions, short collateral, leverage, market impact and financing
are not implemented; see docs/ISSUE_9_IMPLEMENTACAO.md.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from wqf.backtest.accounting import (
    AccountState,
    Side,
    Trade,
    apply_borrow_charge,
    apply_trade,
)
from wqf.backtest.costs import CostRates, brl
from wqf.backtest.ledger import BacktestResult, LedgerEvent, reconcile, snapshot


@dataclass(frozen=True)
class MarketBar:
    """One tradable session, one asset, BRL prices without corporate adjustments."""

    session: date
    asset: str
    open_price: Decimal
    close_price: Decimal

    def __post_init__(self) -> None:
        if type(self.session) is not date:
            raise TypeError("MarketBar session must be a date")
        if not self.asset.strip():
            raise ValueError("MarketBar asset must be nonblank")
        for name in ("open_price", "close_price"):
            price = getattr(self, name)
            if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
                raise ValueError(f"{name} must be finite positive Decimal")


@dataclass(frozen=True)
class TargetSignal:
    """Target is an integer number of shares for a strategy/asset.

    ``available_at`` is the declared date the input data became available,
    not proof of actual data lineage. It must not be later than decision_date.
    A signal decided after session close is first tradable at NEXT session open.
    """

    decision_date: date
    available_at: date
    strategy: str
    asset: str
    target_quantity: int

    def __post_init__(self) -> None:
        if type(self.decision_date) is not date or type(self.available_at) is not date:
            raise TypeError("decision_date and available_at must be dates")
        if self.available_at > self.decision_date:
            raise ValueError("Signal uses information not yet available at decision date")
        if not self.strategy.strip() or not self.asset.strip():
            raise ValueError("strategy and asset must be nonblank")
        if type(self.target_quantity) is not int:
            raise TypeError("target_quantity must be an integer")


def run_backtest(
    bars: Iterable[MarketBar],
    signals: Iterable[TargetSignal],
    *,
    starting_cash: Decimal,
    rates: CostRates,
    cash_interval_rates: Mapping[date, Decimal] | None = None,
    monthly_first_session_only: bool = False,
) -> BacktestResult:
    """Run one portfolio across an ordered calendar, returning immutable audit trail.

    Cash interest (CDI proxy) is an *effective rate for each preceding interval*,
    provided for every session after the first. ``None`` explicitly disables
    cash remuneration for synthetic/offline tests, not official fund runs.

    Signals for the same strategy and asset overwrite earlier targets at each
    decision. Portfolio target per asset = sum of latest strategy targets.
    Distinct strategy targets are NETTED for one order, avoiding double costs.

    ``monthly_first_session_only`` restricts *executions* to the first observed
    market session of the month; it does not generate signals or rebalance by
    itself. Signals are always executed at next available market session open.
    """
    if not isinstance(starting_cash, Decimal) or not starting_cash.is_finite():
        raise ValueError("starting_cash must be a finite Decimal")
    if starting_cash < 0:
        raise ValueError("starting_cash cannot be negative")
    if not isinstance(rates, CostRates):
        raise TypeError("rates must be CostRates")

    bars_by_session: dict[date, dict[str, MarketBar]] = {}
    for bar in bars:
        if not isinstance(bar, MarketBar):
            raise TypeError("bars must contain MarketBar instances")
        by_asset = bars_by_session.setdefault(bar.session, {})
        if bar.asset in by_asset:
            raise ValueError(f"Repeated market bar: {bar.session} {bar.asset}")
        by_asset[bar.asset] = bar
    sessions = sorted(bars_by_session)
    if not sessions:
        raise ValueError("At least one market session is required")
    index_by_date = {session: i for i, session in enumerate(sessions)}
    first_in_month = {
        next(session for session in sessions if (session.year, session.month) == month)
        for month in {(day.year, day.month) for day in sessions}
    }

    rates_by_date: dict[date, Decimal] = {}
    expected_rate_dates = set(sessions[1:])
    if cash_interval_rates is not None:
        if set(cash_interval_rates) != expected_rate_dates:
            raise ValueError("cash_interval_rates must cover exactly every interval end date")
        for session, rate in cash_interval_rates.items():
            if not isinstance(rate, Decimal) or not rate.is_finite() or rate <= -1:
                raise ValueError(f"Invalid effective cash rate for {session}")
            rates_by_date[session] = rate

    decisions: dict[date, list[TargetSignal]] = {}
    keys: set[tuple[date, str, str]] = set()
    for signal in signals:
        if not isinstance(signal, TargetSignal):
            raise TypeError("signals must contain TargetSignal instances")
        if signal.decision_date not in index_by_date:
            raise ValueError(
                f"Signal decision must occur on a market session: {signal.decision_date}"
            )
        decision_index = index_by_date[signal.decision_date]
        if decision_index == len(sessions) - 1:
            raise ValueError("Signal on final session has no future execution session")
        execution_date = sessions[decision_index + 1]
        if monthly_first_session_only and execution_date not in first_in_month:
            raise ValueError(f"Execution {execution_date} is outside the rebalance calendar")
        key = (signal.decision_date, signal.strategy, signal.asset)
        if key in keys:
            raise ValueError(f"Duplicate target signal: {key}")
        keys.add(key)
        decisions.setdefault(signal.decision_date, []).append(signal)

    account = AccountState(starting_cash)
    target_by_strategy: dict[tuple[str, str], int] = {}
    pending: list[TargetSignal] = []
    journal: list[LedgerEvent] = []
    snapshots = []
    previous_date: date | None = None
    previous_closing: dict[str, Decimal] = {}

    for session in sessions:
        daily_events: list[LedgerEvent] = []
        trading_fees = Decimal(0)
        borrow_fees = Decimal(0)
        earned_interest = Decimal(0)
        bars_today = bars_by_session[session]

        if previous_date is not None:
            opening_cash = account.cash
            days = (session - previous_date).days
            # Charge previously held shorts for the interval using known prior close.
            for asset, quantity in sorted(account.positions.items()):
                if quantity >= 0:
                    continue
                updated, fee = apply_borrow_charge(
                    account,
                    charge_id=f"{previous_date}:{session}:{asset}",
                    asset=asset,
                    price=previous_closing[asset],
                    days=days,
                    rates=rates,
                )
                account = updated
                event = LedgerEvent(
                    event_id=f"borrow:{previous_date}:{session}:{asset}",
                    session=session,
                    kind="borrow",
                    asset=asset,
                    cash_delta=-fee,
                )
                daily_events.append(event)
                borrow_fees += fee
            if cash_interval_rates is not None:
                # Negative cash is not remunerated; financing is out of scope.
                earned_interest = brl(max(opening_cash, Decimal(0)) * rates_by_date[session])
                key = f"interest:{previous_date}:{session}"
                account = AccountState(
                    cash=account.cash + earned_interest,
                    positions=account.positions,
                    applied_ids=account.applied_ids | {key},
                )
                daily_events.append(
                    LedgerEvent(
                        event_id=key,
                        session=session,
                        kind="cash_interest",
                        cash_delta=earned_interest,
                    )
                )

        # Apply previous close's decisions at this session's opening prices.
        affected_assets = {signal.asset for signal in pending}
        for signal in pending:
            target_by_strategy[(signal.strategy, signal.asset)] = signal.target_quantity
        for asset in sorted(affected_assets):
            components = {
                strategy: qty
                for (strategy, target_asset), qty in target_by_strategy.items()
                if target_asset == asset
            }
            target = sum(components.values())
            delta = target - account.positions.get(asset, 0)
            if delta == 0:
                continue
            if asset not in bars_today:
                raise ValueError(f"Missing execution price for {asset} at {session}")
            trade = Trade(
                trade_id=f"{session}:{asset}",
                asset=asset,
                side=Side.BUY if delta > 0 else Side.SELL,
                quantity=abs(delta),
                price=bars_today[asset].open_price,
            )
            result = apply_trade(account, trade, rates)
            account = result.account
            trading_fees += result.costs.total
            daily_events.append(
                LedgerEvent(
                    event_id=f"trade:{trade.trade_id}",
                    session=session,
                    kind="trade",
                    asset=asset,
                    price=trade.price,
                    quantity_delta=delta,
                    cash_delta=result.cash_delta,
                    transaction_cost=result.costs.total,
                    decision_date=previous_date,
                    net_target_quantity=target,
                    strategy_targets=components,
                )
            )

        closing = {asset: bar.close_price for asset, bar in bars_today.items()}
        # market_value in snapshot refuses missing held-asset marks.
        daily = snapshot(
            session,
            account,
            closing,
            transaction_costs=brl(trading_fees),
            borrow_costs=brl(borrow_fees),
            cash_interest=earned_interest,
            event_ids=tuple(event.event_id for event in daily_events),
        )
        snapshots.append(daily)
        journal.extend(daily_events)
        previous_date = session
        previous_closing = closing
        pending = decisions.get(session, [])

    output = BacktestResult(
        snapshots=tuple(snapshots),
        events=tuple(journal),
        final_account=account,
        strategy_targets=target_by_strategy,
    )
    reconcile(output, starting_cash)
    return output
