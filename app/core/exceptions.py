from __future__ import annotations


class AppError(Exception):
    """Base application error."""


class RealTradingDisabledError(AppError):
    """Raised when a real trading method is called in MVP."""


class MarketApiError(AppError):
    """Raised for non-transient market API failures."""


class PaymentCompatibilityError(AppError):
    """Raised when a market is not compatible with configured payment rules."""


class PaperTradingError(AppError):
    """Base paper trading error."""


class InsufficientPaperBalanceError(PaperTradingError):
    """Raised when paper balance is insufficient."""


class DuplicatePaperBuyError(PaperTradingError):
    """Raised when the same listing is paper-bought twice."""


class TradeBanActiveError(PaperTradingError):
    """Raised when attempting to sell before trade ban ends."""


class PositionNotFoundError(PaperTradingError):
    """Raised when a paper position does not exist."""

