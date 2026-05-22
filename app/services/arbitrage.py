from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.config import Settings
from app.markets.types import BuyOrder, MarketOffer
from app.services.liquidity import LiquidityReport
from app.services.price_analysis import PriceAnalysis
from app.utils.money import percent_of, quantize_money, quantize_percent


@dataclass(slots=True)
class DealCandidate:
    dedupe_key: str
    item_name: str
    market_hash_name: str
    exterior: str | None
    is_stattrak: bool
    float_value: Decimal | None
    dmarket_listing_id: str
    dmarket_price: Decimal
    csgo_buy_order_price: Decimal
    buy_price_with_fees: Decimal
    sell_price_after_fees: Decimal
    profit: Decimal
    roi: Decimal
    liquidity_score: int
    risk_score: int
    source_mode: str
    status: str = "new"
    details: dict[str, Any] = field(default_factory=dict)

    def to_orm_payload(self) -> dict[str, Any]:
        return {
            "dedupe_key": self.dedupe_key,
            "item_name": self.item_name,
            "market_hash_name": self.market_hash_name,
            "exterior": self.exterior,
            "is_stattrak": self.is_stattrak,
            "float_value": self.float_value,
            "dmarket_listing_id": self.dmarket_listing_id,
            "dmarket_price": self.dmarket_price,
            "csgo_buy_order_price": self.csgo_buy_order_price,
            "buy_price_with_fees": self.buy_price_with_fees,
            "sell_price_after_fees": self.sell_price_after_fees,
            "profit": self.profit,
            "roi": self.roi,
            "liquidity_score": self.liquidity_score,
            "risk_score": self.risk_score,
            "source_mode": self.source_mode,
            "status": self.status,
            "details": self.details,
        }


class ArbitrageCalculator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def passes_profit_filters(self, offer: MarketOffer, order: BuyOrder) -> bool:
        if offer.price_rub < self.settings.min_item_price:
            return False
        if offer.price_rub > self.settings.max_item_price:
            return False
        _, _, _, _, profit, roi = self._estimate_prices(offer, order)
        return profit >= self.settings.min_profit_absolute and roi >= self.settings.min_profit_percent

    def evaluate(
        self,
        offer: MarketOffer,
        order: BuyOrder,
        liquidity: LiquidityReport,
        price_analysis: PriceAnalysis,
        source_mode: str,
    ) -> DealCandidate | None:
        if offer.price_rub < self.settings.min_item_price:
            return None
        if offer.price_rub > self.settings.max_item_price:
            return None
        if liquidity.score < self.settings.min_liquidity_score:
            return None

        buy_fee, buy_price_with_fees, sell_fee, sell_price_after_fees, profit, roi = self._estimate_prices(offer, order)

        if profit < self.settings.min_profit_absolute:
            return None
        if roi < self.settings.min_profit_percent:
            return None

        risk_score = self._risk_score(price_analysis)
        return DealCandidate(
            dedupe_key=self._dedupe_key(offer, order),
            item_name=offer.item_name,
            market_hash_name=offer.market_hash_name,
            exterior=offer.exterior,
            is_stattrak=offer.is_stattrak,
            float_value=offer.float_value,
            dmarket_listing_id=offer.listing_id,
            dmarket_price=offer.price_rub,
            csgo_buy_order_price=order.price_rub,
            buy_price_with_fees=buy_price_with_fees,
            sell_price_after_fees=sell_price_after_fees,
            profit=profit,
            roi=roi,
            liquidity_score=liquidity.score,
            risk_score=risk_score,
            source_mode=source_mode,
            details={
                "fees": {
                    "dmarket_fee_percent": str(self.settings.dmarket_fee_percent),
                    "csgo_market_fee_percent": str(self.settings.csgo_market_fee_percent),
                    "withdrawal_fee_percent": str(self.settings.withdrawal_fee_percent),
                    "buy_fee": str(buy_fee),
                    "sell_fee": str(sell_fee),
                },
                "liquidity": {
                    "sales_7d": liquidity.sales_7d,
                    "sales_30d": liquidity.sales_30d,
                    "buy_order_count": liquidity.buy_order_count,
                    "spread_percent": str(liquidity.spread_percent),
                    "notes": liquidity.notes,
                },
                "price_analysis": {
                    "avg_7d_price": str(price_analysis.avg_7d_price) if price_analysis.avg_7d_price is not None else None,
                    "avg_30d_price": str(price_analysis.avg_30d_price) if price_analysis.avg_30d_price is not None else None,
                    "price_spike_percent": str(price_analysis.price_spike_percent),
                    "risk_label": price_analysis.risk_label,
                    "warning": price_analysis.warning,
                    "is_history_fallback": price_analysis.is_history_fallback,
                },
                "trade_lock_days": self.settings.trade_lock_days,
                "raw": {
                    "dmarket": offer.raw_payload,
                    "csgo_market": order.raw_payload,
                },
            },
        )

    def _risk_score(self, analysis: PriceAnalysis) -> int:
        base = 20
        if analysis.risk_label == "средний":
            base = 50
        if analysis.risk_label == "высокий":
            base = 80
        if analysis.is_history_fallback:
            base = max(base, 55)
        return min(100, base)

    def _estimate_prices(
        self,
        offer: MarketOffer,
        order: BuyOrder,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        buy_fee = percent_of(offer.price_rub, self.settings.dmarket_fee_percent)
        buy_price_with_fees = quantize_money(offer.price_rub + buy_fee)
        sell_fee_percent = self.settings.csgo_market_fee_percent + self.settings.withdrawal_fee_percent
        sell_fee = percent_of(order.price_rub, sell_fee_percent)
        sell_price_after_fees = quantize_money(order.price_rub - sell_fee)
        profit = quantize_money(sell_price_after_fees - buy_price_with_fees)
        roi = (
            quantize_percent(profit / buy_price_with_fees * Decimal("100"))
            if buy_price_with_fees > 0
            else Decimal("0")
        )
        return buy_fee, buy_price_with_fees, sell_fee, sell_price_after_fees, profit, roi

    @staticmethod
    def _dedupe_key(offer: MarketOffer, order: BuyOrder) -> str:
        raw = "|".join(
            [
                "dmarket_to_csgo_buy_order",
                offer.market_hash_name,
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
