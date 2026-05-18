from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from app.config import Settings
from app.liquidity.liquidity_engine import LiquidityMetrics
from app.markets.base import MarketListing
from app.markets.payment_profile import MarketPaymentProfile, is_blacklisted_market_name
from app.pricing.pricing_engine import PriceCalculation
from app.risk.blacklist import DEFAULT_ITEM_BLACKLIST, DEFAULT_MARKET_PAIR_BLACKLIST, is_forbidden_market, normalize_pair
from app.utils.time import utc_now


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    risk_score: int
    confidence_score: int
    reasons: list[str] = field(default_factory=list)


class RiskFilters:
    def __init__(
        self,
        settings: Settings,
        item_blacklist: set[str] | None = None,
        market_pair_blacklist: set[tuple[str, str]] | None = None,
    ) -> None:
        self.settings = settings
        self.item_blacklist = item_blacklist or DEFAULT_ITEM_BLACKLIST
        self.market_pair_blacklist = market_pair_blacklist or DEFAULT_MARKET_PAIR_BLACKLIST

    def evaluate(
        self,
        buy_listing: MarketListing,
        sell_listing: MarketListing,
        calculation: PriceCalculation,
        liquidity: LiquidityMetrics,
        buy_payment: MarketPaymentProfile,
        sell_payment: MarketPaymentProfile,
    ) -> RiskDecision:
        reasons: list[str] = []
        risk_score = 20
        confidence_score = 80

        for market in (buy_listing.market_name, sell_listing.market_name):
            if is_forbidden_market(market) or is_blacklisted_market_name(market, self.settings):
                reasons.append(f"Market is forbidden: {market}")
        if not buy_payment.is_allowed:
            reasons.append(f"Buy market payment profile is not allowed: {buy_listing.market_name}")
        if not sell_payment.is_allowed:
            reasons.append(f"Sell market payment profile is not allowed: {sell_listing.market_name}")
        if buy_listing.normalized_name in self.item_blacklist:
            reasons.append("Item is blacklisted")
        if normalize_pair(buy_listing.market_name, sell_listing.market_name) in self.market_pair_blacklist:
            reasons.append("Market pair is blacklisted")
        if calculation.buy_price_rub > self.settings.max_buy_price_rub:
            reasons.append("Buy price is above configured limit")
        if calculation.roi_percent < self.settings.min_roi_percent:
            reasons.append("ROI is below minimum")
        if calculation.expected_net_profit_rub < self.settings.min_profit_rub:
            reasons.append("Net profit is below minimum")
        if liquidity.score < self.settings.min_liquidity_score:
            reasons.append("Liquidity is below minimum")
        if self.settings.currency_spread_percent > self.settings.max_allowed_currency_spread_percent:
            reasons.append("Currency spread is above maximum")
        if not buy_listing.available:
            reasons.append("Buy listing is unavailable")
        if sell_listing.tradable is False:
            reasons.append("Sell listing is not tradable")
        if buy_listing.created_at < utc_now() - timedelta(minutes=30):
            reasons.append("Buy listing data is stale")
        if sell_listing.created_at < utc_now() - timedelta(minutes=30):
            reasons.append("Sell listing data is stale")
        if not buy_listing.normalized_name:
            reasons.append("Normalized name is empty")

        if calculation.currency_conversion_fee_rub > Decimal("0"):
            risk_score += 10
        if liquidity.score < 70:
            risk_score += 10
            confidence_score -= 10
        if calculation.roi_percent < self.settings.min_roi_percent + Decimal("2"):
            risk_score += 10
            confidence_score -= 10
        if reasons:
            risk_score += 30
            confidence_score -= 30

        return RiskDecision(
            allowed=not reasons,
            risk_score=max(0, min(100, risk_score)),
            confidence_score=max(0, min(100, confidence_score)),
            reasons=reasons,
        )

