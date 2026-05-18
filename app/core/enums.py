from __future__ import annotations

from enum import StrEnum


class TradingMode(StrEnum):
    SIGNAL_ONLY = "SIGNAL_ONLY"
    PAPER_TRADING = "PAPER_TRADING"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    AUTO_BUY_LIMITED = "AUTO_BUY_LIMITED"
    AUTO_BUY_AND_SELL = "AUTO_BUY_AND_SELL"


class PaperSellMode(StrEnum):
    MANUAL_SELL = "MANUAL_SELL"
    AFTER_TRADE_BAN = "AFTER_TRADE_BAN"
    TARGET_PRICE = "TARGET_PRICE"
    TIME_LIMIT = "TIME_LIMIT"


class PaperPositionStatus(StrEnum):
    PENDING_BUY = "PENDING_BUY"
    BOUGHT = "BOUGHT"
    TRADE_LOCKED = "TRADE_LOCKED"
    READY_TO_SELL = "READY_TO_SELL"
    LISTED_FOR_SALE = "LISTED_FOR_SALE"
    SOLD = "SOLD"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class MarketName(StrEnum):
    MARKET_CSGO = "Market.CSGO"
    LIS_SKINS = "LIS-SKINS"
    MOCK_MARKET_A = "Mock.LIS-SKINS"
    MOCK_MARKET_B = "Mock.Market.CSGO"

