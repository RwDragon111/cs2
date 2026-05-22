from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import log10

from app.markets.types import BuyOrder, PriceHistory
from app.utils.money import quantize_percent


@dataclass(slots=True)
class LiquidityReport:
    score: int
    sales_7d: int
    sales_30d: int
    buy_order_count: int
    spread_percent: Decimal
    notes: list[str]


class LiquidityScorer:
    def score(self, order: BuyOrder, history: PriceHistory) -> LiquidityReport:
        buy_order_count = max(order.count, history.buy_order_count)
        sales_7d = history.sales_7d
        sales_30d = history.sales_30d
        min_sell_price = history.min_sell_price or order.price_rub

        if min_sell_price > 0:
            spread_percent = quantize_percent((min_sell_price - order.price_rub) / min_sell_price * Decimal("100"))
        else:
            spread_percent = Decimal("100")

        order_score = min(25, int(log10(max(buy_order_count, 1) + 1) * 12))
        sales_score = min(35, int(sales_7d * 0.45 + sales_30d * 0.06))
        spread_score = self._spread_score(spread_percent)
        history_score = 15 if not history.is_fallback else 3
        stability_score = self._stability_score(history)
        total = max(0, min(100, order_score + sales_score + spread_score + history_score + stability_score))

        notes: list[str] = []
        if history.is_fallback:
            notes.append("История цен недоступна, использован осторожный fallback.")
        if buy_order_count < 3:
            notes.append("Мало buy orders, ликвидность может быть тонкой.")
        if spread_percent > 15:
            notes.append("Широкий spread между продажей и buy order.")
        if history.avg_7d_price and history.avg_30d_price and history.avg_30d_price > 0:
            drift = abs((history.avg_7d_price - history.avg_30d_price) / history.avg_30d_price * Decimal("100"))
            if drift > 12:
                notes.append("7d average сильно отличается от 30d average, ликвидность оценена осторожнее.")

        return LiquidityReport(
            score=int(total),
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            buy_order_count=buy_order_count,
            spread_percent=spread_percent,
            notes=notes,
        )

    @staticmethod
    def _spread_score(spread_percent: Decimal) -> int:
        if spread_percent <= 0:
            return 20
        if spread_percent <= 2:
            return 19
        if spread_percent <= 5:
            return 16
        if spread_percent <= 10:
            return 12
        if spread_percent <= 15:
            return 8
        if spread_percent <= 25:
            return 4
        return 0

    @staticmethod
    def _stability_score(history: PriceHistory) -> int:
        if history.is_fallback or not history.avg_7d_price or not history.avg_30d_price or history.avg_30d_price <= 0:
            return 0
        drift = abs((history.avg_7d_price - history.avg_30d_price) / history.avg_30d_price * Decimal("100"))
        if drift <= 3:
            return 5
        if drift <= 8:
            return 3
        if drift <= 15:
            return 1
        return 0
