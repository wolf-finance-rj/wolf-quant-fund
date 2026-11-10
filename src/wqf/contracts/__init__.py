"""Contratos tipados trocados entre Dados, Estratégias e Backtesting.

Cada contrato valida os próprios campos na criação e levanta
``ContractValidationError`` com o nome do contrato e do campo quando algo é inválido.
Especificação e decisões em ``docs/architecture/contracts.md``.
"""

from wqf.contracts.errors import ContractValidationError
from wqf.contracts.market_data import MARKET_DATA_SCHEMA_VERSION, MarketData
from wqf.contracts.simulated_trade import SIMULATED_TRADE_SCHEMA_VERSION, SimulatedTrade
from wqf.contracts.strategy_signal import (
    MAX_ABS_TARGET_WEIGHT,
    STRATEGY_SIGNAL_SCHEMA_VERSION,
    SignalDirection,
    StrategySignal,
)

__all__ = [
    "MARKET_DATA_SCHEMA_VERSION",
    "MAX_ABS_TARGET_WEIGHT",
    "SIMULATED_TRADE_SCHEMA_VERSION",
    "STRATEGY_SIGNAL_SCHEMA_VERSION",
    "ContractValidationError",
    "MarketData",
    "SignalDirection",
    "SimulatedTrade",
    "StrategySignal",
]
