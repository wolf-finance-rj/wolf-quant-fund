"""Subpacote da estratégia de Pairs Trading."""

from wqf.strategies.pairs.spread import (
    AlignedPairPoint,
    PairSpreadPoint,
    PricePoint,
    RollingZScorePoint,
    SpreadMethod,
    align_pair_prices,
    analyze_pair_spread,
    calculate_spread,
    compute_rolling_zscore,
)

__all__ = [
    "AlignedPairPoint",
    "PairSpreadPoint",
    "PricePoint",
    "RollingZScorePoint",
    "SpreadMethod",
    "align_pair_prices",
    "analyze_pair_spread",
    "calculate_spread",
    "compute_rolling_zscore",
]
