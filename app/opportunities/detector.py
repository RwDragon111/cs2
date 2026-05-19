from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from decimal import Decimal

from app.config import Settings
from app.currency.currency_engine import CurrencyEngine
from app.liquidity.liquidity_engine import LiquidityEngine
from app.markets.base import MarketFees, MarketListing, SaleRecord
from app.markets.payment_profile import MarketPaymentProfile
from app.opportunities.models import ArbitrageOpportunity
from app.pricing.pricing_engine import PricingEngine
from app.risk.risk_filters import RiskFilters
from app.utils.money import quantize_money
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class OpportunityDetector:
    def __init__(
        self,
        settings: Settings,
        currency_engine: CurrencyEngine,
        pricing_engine: PricingEngine,
        liquidity_engine: LiquidityEngine,
        risk_filters: RiskFilters,
        payment_profiles: dict[str, MarketPaymentProfile],
        fees_by_market: dict[str, MarketFees],
    ) -> None:
        self.settings = settings
        self.currency_engine = currency_engine
        self.pricing_engine = pricing_engine
        self.liquidity_engine = liquidity_engine
        self.risk_filters = risk_filters
        self.payment_profiles = payment_profiles
        self.fees_by_market = fees_by_market

    def detect(
        self,
        listings: list[MarketListing],
        sales_history_by_name: dict[str, list[SaleRecord]] | None = None,
    ) -> list[ArbitrageOpportunity]:
        sales_history_by_name = sales_history_by_name or {}
        enriched = [self._with_prices(listing) for listing in listings if listing.available]
        by_name_market: dict[str, dict[str, list[MarketListing]]] = defaultdict(lambda: defaultdict(list))
        for listing in enriched:
            by_name_market[listing.normalized_name][listing.market_name].append(listing)

        opportunities: list[ArbitrageOpportunity] = []
        for normalized_name, market_map in by_name_market.items():
            market_names = list(market_map)
            for buy_market in market_names:
                for sell_market in market_names:
                    if buy_market == sell_market:
                        continue
                    if not self._allowed_direction(buy_market, sell_market):
                        continue
                    buy_listing = min(market_map[buy_market], key=lambda item: item.price_rub or item.price)
                    sell_listing = max(market_map[sell_market], key=lambda item: item.price_rub or item.price)
                    if (buy_listing.price_rub or Decimal("0")) >= (sell_listing.price_rub or Decimal("0")):
                        continue
                    opportunity = self._build_opportunity(
                        buy_listing=buy_listing,
                        sell_listing=sell_listing,
                        all_listings=enriched,
                        sales_history=sales_history_by_name.get(normalized_name, []),
                    )
                    if opportunity:
                        opportunities.append(opportunity)
        logger.info("Detected %s arbitrage opportunities", len(opportunities))
        return opportunities

    def _build_opportunity(
        self,
        buy_listing: MarketListing,
        sell_listing: MarketListing,
        all_listings: list[MarketListing],
        sales_history: list[SaleRecord],
    ) -> ArbitrageOpportunity | None:
        buy_payment = self.payment_profiles.get(buy_listing.market_name)
        sell_payment = self.payment_profiles.get(sell_listing.market_name)
        if buy_payment is None or sell_payment is None:
            return None

        buy_fees = self.fees_by_market.get(buy_listing.market_name, MarketFees(market_name=buy_listing.market_name))
        sell_fees = self.fees_by_market.get(sell_listing.market_name, MarketFees(market_name=sell_listing.market_name))
        calculation = self.pricing_engine.calculate(
            buy_listing=buy_listing,
            sell_listing=sell_listing,
            buy_fees=buy_fees,
            sell_fees=sell_fees,
            buy_payment_profile=buy_payment,
            sell_payment_profile=sell_payment,
        )
        liquidity = self.liquidity_engine.calculate(
            item_name=buy_listing.normalized_name,
            listings=all_listings,
            sales_history=sales_history,
            buy_price_rub=calculation.buy_price_rub,
            sell_price_rub=calculation.expected_sell_price_rub,
        )
        risk = self.risk_filters.evaluate(
            buy_listing=buy_listing,
            sell_listing=sell_listing,
            calculation=calculation,
            liquidity=liquidity,
            buy_payment=buy_payment,
            sell_payment=sell_payment,
        )
        if not risk.allowed:
            logger.debug("Opportunity rejected for %s: %s", buy_listing.normalized_name, risk.reasons)
            return None

        opportunity_id = self._opportunity_id(buy_listing, sell_listing)
        expected_profit_usd = self.currency_engine.to_usd(calculation.expected_net_profit_rub, "RUB")
        return ArbitrageOpportunity(
            id=opportunity_id,
            item_name=buy_listing.item_name,
            normalized_name=buy_listing.normalized_name,
            buy_market=buy_listing.market_name,
            sell_market=sell_listing.market_name,
            buy_listing_id=buy_listing.id,
            buy_price_rub=calculation.buy_price_rub,
            buy_price_usd=self.currency_engine.to_usd(calculation.buy_price_rub, "RUB"),
            expected_sell_price_rub=calculation.expected_sell_price_rub,
            expected_sell_price_usd=self.currency_engine.to_usd(calculation.expected_sell_price_rub, "RUB"),
            total_fees_rub=calculation.total_fees_rub,
            payment_fees_rub=calculation.payment_fees_rub,
            currency_conversion_fees_rub=calculation.currency_conversion_fee_rub,
            expected_net_profit_rub=calculation.expected_net_profit_rub,
            expected_net_profit_usd=expected_profit_usd,
            roi_percent=calculation.roi_percent,
            liquidity_score=liquidity.score,
            risk_score=risk.risk_score,
            confidence_score=risk.confidence_score,
            reason=(
                f"Buy on {buy_listing.market_name}, sell on {sell_listing.market_name}; "
                f"net {calculation.expected_net_profit_rub} RUB after fees"
            ),
            detected_at=utc_now(),
            raw_data={
                "buy_listing": buy_listing.model_dump(mode="json"),
                "sell_listing": sell_listing.model_dump(mode="json"),
                "liquidity": {
                    "sales_24h": liquidity.sales_24h,
                    "sales_7d": liquidity.sales_7d,
                    "sales_30d": liquidity.sales_30d,
                    "active_listings": liquidity.active_listings,
                    "spread_percent": str(liquidity.spread_percent),
                },
                "risk_reasons": risk.reasons,
            },
        )

    def _with_prices(self, listing: MarketListing) -> MarketListing:
        price_rub = listing.price_rub
        price_usd = listing.price_usd
        if price_rub is None:
            price_rub = self.currency_engine.to_rub(listing.price, listing.currency)
        if price_usd is None:
            price_usd = self.currency_engine.to_usd(price_rub, "RUB")
        return listing.model_copy(update={"price_rub": quantize_money(price_rub), "price_usd": quantize_money(price_usd)})

    @staticmethod
    def _opportunity_id(buy_listing: MarketListing, sell_listing: MarketListing) -> str:
        raw = "|".join(
            [
                buy_listing.normalized_name,
                buy_listing.market_name,
                sell_listing.market_name,
                buy_listing.id,
                str(buy_listing.price_rub),
                str(sell_listing.price_rub),
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _allowed_direction(buy_market: str, sell_market: str) -> bool:
        buy = buy_market.replace("Mock.", "")
        sell = sell_market.replace("Mock.", "")
        allowed = {
            ("DMarket", "Market.CSGO.BuyOrder"),
        }
        return (buy, sell) in allowed
