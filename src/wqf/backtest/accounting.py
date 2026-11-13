"""Single-trade cash/position accounting (not a dated execution engine).

Signed units: positive = long, negative = short. BUY increases units and
reduces cash; SELL decreases units and increases cash. Cash includes proceeds
from short sales, *not* freely available collateral. Margin, financing,
corporate actions and portfolio constraints are deliberately outside #6.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from wqf.backtest.costs import CostRates, TradeCosts, borrow_cost, brl, transaction_costs


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class Trade:
    trade_id: str
    asset: str
    side: Side
    quantity: int
    price: Decimal

    def __post_init__(self) -> None:
        if not self.trade_id.strip() or not self.asset.strip():
            raise ValueError("trade_id and asset must be nonblank")
        if not isinstance(self.side, Side):
            raise TypeError("side must be Side.BUY or Side.SELL")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price <= 0:
            raise ValueError("price must be a finite positive Decimal")


@dataclass(frozen=True)
class AccountState:
    cash: Decimal
    positions: Mapping[str, int] = field(default_factory=dict)
    applied_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.cash, Decimal) or not self.cash.is_finite():
            raise ValueError("cash must be a finite Decimal")
        if any(not k or type(v) is not int for k, v in self.positions.items()):
            raise ValueError("positions must map asset names to integer units")
        object.__setattr__(self, "cash", brl(self.cash))
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))
        object.__setattr__(self, "applied_ids", frozenset(self.applied_ids))


@dataclass(frozen=True)
class TradeResult:
    account: AccountState
    notional: Decimal
    costs: TradeCosts
    cash_delta: Decimal


def apply_trade(account: AccountState, trade: Trade, rates: CostRates) -> TradeResult:
    """Apply one execution exactly once. Reversals are a single trade/cost.

    A repeated trade_id raises instead of charging twice. Calling with the
    original immutable state creates a separate simulation branch, not a retry.
    """
    key = f"trade:{trade.trade_id}"
    if key in account.applied_ids:
        raise ValueError(f"Duplicate execution: {trade.trade_id}")
    notional = brl(trade.price * trade.quantity)
    fees = transaction_costs(notional, rates)
    signed_units = trade.quantity if trade.side is Side.BUY else -trade.quantity
    cash_delta = (-notional if trade.side is Side.BUY else notional) - fees.total
    positions = dict(account.positions)
    quantity = positions.get(trade.asset, 0) + signed_units
    if quantity:
        positions[trade.asset] = quantity
    else:
        positions.pop(trade.asset, None)
    updated = AccountState(
        cash=account.cash + cash_delta,
        positions=positions,
        applied_ids=account.applied_ids | {key},
    )
    return TradeResult(updated, notional, fees, cash_delta)


def apply_borrow_charge(
    account: AccountState,
    *,
    charge_id: str,
    asset: str,
    price: Decimal,
    days: int,
    rates: CostRates,
) -> tuple[AccountState, Decimal]:
    """Apply short-borrow cost once for an explicitly identified interval."""
    if not charge_id.strip() or not asset.strip():
        raise ValueError("charge_id and asset must be nonblank")
    key = f"borrow:{charge_id}"
    if key in account.applied_ids:
        raise ValueError(f"Duplicate borrow charge: {charge_id}")
    units = account.positions.get(asset, 0)
    charge = borrow_cost(-units if units < 0 else 0, price, days, rates)
    updated = AccountState(
        cash=account.cash - charge,
        positions=account.positions,
        applied_ids=account.applied_ids | {key},
    )
    return updated, charge
