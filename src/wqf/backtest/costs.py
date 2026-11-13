"""Explicit, reproducible trading and short-borrow costs.

Amounts use Decimal and BRL cents. Rate components are deliberately not
estimated here: the fund manual specifies a total 0.15% transaction rate,
without an approved allocation between brokerage, exchange fees and impact.
"""

import tomllib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")


def brl(value: Decimal) -> Decimal:
    """Round a monetary amount to BRL cents (half up)."""
    if not value.is_finite():
        raise ValueError("Monetary amounts must be finite")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostRates:
    """Rates are fractions: 0.0015 = 0.15% of traded notional.

    ``other_rate`` absorbs the not-yet-approved cost breakdown. When an
    allocation is approved, move this amount into brokerage/exchange/impact;
    do not add those components on top of the manual's total.
    """

    brokerage_rate: Decimal = Decimal(0)
    exchange_rate: Decimal = Decimal(0)
    impact_rate: Decimal = Decimal(0)
    other_rate: Decimal = Decimal(0)
    annual_borrow_rate: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        for name in (
            "brokerage_rate",
            "exchange_rate",
            "impact_rate",
            "other_rate",
            "annual_borrow_rate",
        ):
            rate = getattr(self, name)
            if not isinstance(rate, Decimal) or not rate.is_finite() or rate < 0:
                raise ValueError(f"{name} must be a finite nonnegative Decimal")

    @property
    def transaction_rate(self) -> Decimal:
        return self.brokerage_rate + self.exchange_rate + self.impact_rate + self.other_rate


@dataclass(frozen=True)
class TradeCosts:
    brokerage: Decimal
    exchange: Decimal
    impact: Decimal
    other: Decimal

    @property
    def total(self) -> Decimal:
        return self.brokerage + self.exchange + self.impact + self.other


def transaction_costs(notional: Decimal, rates: CostRates) -> TradeCosts:
    """Charge each cost component once, rounded to cents.

    The remainder is assigned to ``other`` to make the rounded total equal
    to rounding the aggregate rate once, avoiding rounding drift.
    """
    if not isinstance(notional, Decimal) or not notional.is_finite() or notional < 0:
        raise ValueError("Notional must be a finite nonnegative Decimal")
    remaining = brl(notional * rates.transaction_rate)
    brokerage = min(brl(notional * rates.brokerage_rate), remaining)
    remaining -= brokerage
    exchange = min(brl(notional * rates.exchange_rate), remaining)
    remaining -= exchange
    impact = min(brl(notional * rates.impact_rate), remaining)
    other = remaining - impact
    return TradeCosts(brokerage, exchange, impact, other)


def borrow_cost(short_quantity: int, price: Decimal, days: int, rates: CostRates) -> Decimal:
    """ACT/365 simple borrow charge on a marked-to-market short position.

    ``short_quantity`` is the absolute number of borrowed shares. This is a
    stand-alone charge; date iteration and accrual scheduling belong to #9.
    """
    if type(short_quantity) is not int or short_quantity < 0:
        raise ValueError("short_quantity must be a nonnegative integer")
    if type(days) is not int or days < 0:
        raise ValueError("days must be a nonnegative integer")
    if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
        raise ValueError("Price must be a finite positive Decimal")
    return brl(Decimal(short_quantity) * price * rates.annual_borrow_rate * days / 365)


def load_cost_rates(path: str | Path) -> CostRates:
    """Read approved/illustrative rates from ``config/parametros.toml``.

    Rates are stored as decimal strings to preserve exact decimal values.
    """
    with Path(path).open("rb") as config_file:
        config = tomllib.load(config_file)
    raw = config["backtest"]["costs"]
    names = (
        "brokerage_rate",
        "exchange_rate",
        "impact_rate",
        "other_rate",
        "annual_borrow_rate",
    )
    return CostRates(**{key: Decimal(raw[key]) for key in names})
