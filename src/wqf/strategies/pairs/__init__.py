"""Subpacote da estratégia de Pairs Trading."""

from wqf.strategies.pairs.spread import (
    AlignedPairPoint,
    PricePoint,
    SpreadMethod,
    align_pair_prices,
    calculate_spread,
)

__all__ = [
    "AlignedPairPoint",
    "PricePoint",
    "SpreadMethod",
    "align_pair_prices",
    "calculate_spread",
]
