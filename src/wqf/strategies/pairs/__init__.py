"""Subpacote da estratégia de Pairs Trading."""

from wqf.strategies.pairs.signals import (
    PairDecision,
    PairsSignalConfig,
    PairsSignalReport,
    generate_pairs_signals,
    load_pairs_config,
    run_pairs_backtest,
)
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
    "PairDecision",
    "PairSpreadPoint",
    "PairsSignalConfig",
    "PairsSignalReport",
    "PricePoint",
    "RollingZScorePoint",
    "SpreadMethod",
    "align_pair_prices",
    "analyze_pair_spread",
    "calculate_spread",
    "compute_rolling_zscore",
    "generate_pairs_signals",
    "load_pairs_config",
    "run_pairs_backtest",
]
