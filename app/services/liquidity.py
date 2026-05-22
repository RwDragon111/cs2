from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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

        # When sale history is unavailable, Market.CSGO order depth becomes the
        # main liquidity signal. A deep active buy side should still pass a
        # MIN_LIQUIDITY_SCORE around 60.
        order_score = min(45, buy_order_count * 5)
        sales_score = min(30, sales_7d * 2 + sales_30d // 10)
        spread_score = max(0, 20 - int(spread_percent))
        history_score = 5 if history.is_fallback else 10
        total = max(0, min(100, order_score + sales_score + spread_score + history_score))

        notes: list[str] = []
        if history.is_fallback:
            notes.append("История цен недоступна, ликвидность оценена по глубине buy orders и spread.")
        if buy_order_count < 3:
            notes.append("Мало buy orders, ликвидность может быть тонкой.")
        if spread_percent > 15:
            notes.append("Широкий spread между продажей и buy order.")

        return LiquidityReport(
            score=int(total),
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            buy_order_count=buy_order_count,
            spread_percent=spread_percent,
            notes=notes,
        )
