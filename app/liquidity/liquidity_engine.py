from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from app.markets.base import MarketListing, SaleRecord
from app.utils.time import utc_now


@dataclass(slots=True)
class LiquidityMetrics:
    score: int
    sales_24h: int
    sales_7d: int
    sales_30d: int
    active_listings: int
    spread_percent: Decimal


class LiquidityEngine:
    popular_keywords = {"ak-47", "awp", "m4a1-s", "m4a4", "usp-s", "desert eagle", "glock-18", "case"}

    def calculate(
        self,
        item_name: str,
        listings: list[MarketListing],
        sales_history: list[SaleRecord],
        buy_price_rub: Decimal | None = None,
        sell_price_rub: Decimal | None = None,
    ) -> LiquidityMetrics:
        now = utc_now()
        sales_24h = sum(1 for sale in sales_history if sale.sold_at >= now - timedelta(hours=24))
        sales_7d = sum(1 for sale in sales_history if sale.sold_at >= now - timedelta(days=7))
        sales_30d = sum(1 for sale in sales_history if sale.sold_at >= now - timedelta(days=30))
        active_listings = sum(1 for listing in listings if listing.normalized_name == item_name and listing.available)

        spread_percent = Decimal("0")
        if buy_price_rub and sell_price_rub and sell_price_rub > 0:
            spread_percent = abs(sell_price_rub - buy_price_rub) / sell_price_rub * Decimal("100")

        score = 0
        score += min(sales_24h * 5, 25)
        score += min(sales_7d * 3, 25)
        score += min(sales_30d, 20)
        score += min(active_listings * 3, 15)
        if any(keyword in item_name.lower() for keyword in self.popular_keywords):
            score += 10
        if sales_history:
            score += 5
        if spread_percent <= Decimal("10"):
            score += 10
        elif spread_percent <= Decimal("20"):
            score += 5

        return LiquidityMetrics(
            score=max(0, min(100, int(score))),
            sales_24h=sales_24h,
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            active_listings=active_listings,
            spread_percent=spread_percent,
        )

