from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from app.config import Settings
from app.core.enums import PaperPositionStatus, TradingMode
from app.core.exceptions import (
    DuplicatePaperBuyError,
    InsufficientPaperBalanceError,
    PaperTradingError,
    PositionNotFoundError,
    TradeBanActiveError,
)
from app.currency.currency_engine import CurrencyEngine
from app.db.models import ArbitrageOpportunityORM, PaperPositionORM
from app.db.repositories import OpportunityRepository, PaperRepository
from app.markets.base import BaseMarketConnector, MarketFees, MarketListing
from app.markets.payment_profile import MarketPaymentProfile
from app.paper_trading.trade_ban import can_sell, trade_ban_until
from app.pricing.pricing_engine import PricingEngine
from app.utils.money import percent_of, quantize_money, quantize_percent
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    def __init__(
        self,
        settings: Settings,
        paper_repository: PaperRepository,
        opportunity_repository: OpportunityRepository,
        connectors: dict[str, BaseMarketConnector],
        pricing_engine: PricingEngine,
        currency_engine: CurrencyEngine,
        payment_profiles: dict[str, MarketPaymentProfile],
        fees_by_market: dict[str, MarketFees],
    ) -> None:
        self.settings = settings
        self.paper_repository = paper_repository
        self.opportunity_repository = opportunity_repository
        self.connectors = connectors
        self.pricing_engine = pricing_engine
        self.currency_engine = currency_engine
        self.payment_profiles = payment_profiles
        self.fees_by_market = fees_by_market

    async def paper_buy(self, opportunity_id: str) -> PaperPositionORM:
        self._ensure_paper_mode()
        opportunity = self.opportunity_repository.get(opportunity_id)
        if opportunity is None or not opportunity.is_active:
            raise PaperTradingError("Opportunity is not active or not found")
        if self.paper_repository.has_open_position_for_listing(opportunity.buy_market, opportunity.buy_listing_id):
            raise DuplicatePaperBuyError("This listing already has an open paper position")

        buy_connector = self.connectors.get(opportunity.buy_market)
        sell_connector = self.connectors.get(opportunity.sell_market)
        if buy_connector is None or sell_connector is None:
            raise PaperTradingError("Connector is not available for opportunity markets")

        current_buy = await buy_connector.fetch_item(opportunity.buy_listing_id)
        if current_buy is None or not current_buy.available:
            raise PaperTradingError("Listing disappeared before Paper Buy")
        current_buy = self._with_prices(current_buy)
        current_sell = await self._best_listing_for_item(sell_connector, opportunity.normalized_name)
        if current_sell is None:
            raise PaperTradingError("Target sell market no longer has comparable listing")
        current_sell = self._with_prices(current_sell)

        calculation = self.pricing_engine.calculate(
            buy_listing=current_buy,
            sell_listing=current_sell,
            buy_fees=self.fees_by_market[current_buy.market_name],
            sell_fees=self.fees_by_market[current_sell.market_name],
            buy_payment_profile=self.payment_profiles[current_buy.market_name],
            sell_payment_profile=self.payment_profiles[current_sell.market_name],
        )
        if calculation.expected_net_profit_rub < self.settings.min_profit_rub or calculation.roi_percent < self.settings.min_roi_percent:
            raise PaperTradingError("Opportunity became too weak after price refresh")

        account = self.paper_repository.account()
        if (
            not self.settings.paper_trading_allow_negative_balance
            and account.current_balance_rub < calculation.total_cost_rub
        ):
            raise InsufficientPaperBalanceError("Not enough paper balance")

        bought_at = utc_now()
        ban_until = trade_ban_until(bought_at, self.settings.paper_trading_trade_ban_days)
        position = PaperPositionORM(
            id=str(uuid.uuid4()),
            account_id=account.id,
            item_name=current_buy.item_name,
            normalized_name=current_buy.normalized_name,
            buy_market=current_buy.market_name,
            target_sell_market=current_sell.market_name,
            source_listing_id=current_buy.id,
            buy_price_rub=calculation.buy_price_rub,
            buy_price_usd=self.currency_engine.to_usd(calculation.buy_price_rub, "RUB"),
            buy_fees_rub=quantize_money(
                calculation.buy_market_fee_rub
                + calculation.deposit_fee_rub
                + calculation.currency_conversion_fee_rub
                + calculation.risk_buffer_rub
            ),
            total_cost_rub=calculation.total_cost_rub,
            expected_sell_price_rub=calculation.expected_sell_price_rub,
            expected_profit_rub=calculation.expected_net_profit_rub,
            expected_roi_percent=calculation.roi_percent,
            status=PaperPositionStatus.TRADE_LOCKED.value,
            bought_at=bought_at,
            trade_ban_until=ban_until,
            can_sell_at=ban_until,
            source_opportunity_id=opportunity.id,
            raw_listing_payload=current_buy.model_dump(mode="json"),
        )
        saved = self.paper_repository.create_position(position, calculation.total_cost_rub)
        logger.info("Paper Buy created position %s for %s", saved.id, saved.normalized_name)
        return saved

    async def paper_sell(self, position_id: str) -> PaperPositionORM:
        self._ensure_paper_mode()
        position = self.paper_repository.get_position(position_id)
        if position is None:
            raise PositionNotFoundError("Paper position not found")
        now = utc_now()
        if not can_sell(now, position.trade_ban_until):
            raise TradeBanActiveError("Trade ban is still active")
        if position.status not in {PaperPositionStatus.READY_TO_SELL.value, PaperPositionStatus.TRADE_LOCKED.value}:
            raise PaperTradingError(f"Position status does not allow Paper Sell: {position.status}")

        connector = self.connectors.get(position.target_sell_market)
        if connector is None:
            raise PaperTradingError("Target sell connector is not available")
        listing = await self._best_listing_for_item(connector, position.normalized_name)
        if listing is None:
            raise PaperTradingError("No current sell listing is available")
        listing = self._with_prices(listing)

        fees = self.fees_by_market[position.target_sell_market]
        payment = self.payment_profiles[position.target_sell_market]
        sell_price = listing.price_rub or listing.price
        sell_fee = percent_of(sell_price, fees.sell_fee_percent)
        withdrawal_fee = percent_of(sell_price, payment.withdrawal_fee_percent)
        conversion_fee = percent_of(sell_price, payment.estimated_conversion_fee_percent) if payment.currency_conversion_required else Decimal("0")
        total_sell_fee = quantize_money(sell_fee + withdrawal_fee + conversion_fee)
        net_revenue = quantize_money(sell_price - total_sell_fee)
        actual_profit = quantize_money(net_revenue - position.total_cost_rub)
        actual_roi = Decimal("0") if position.total_cost_rub <= 0 else quantize_percent(actual_profit / position.total_cost_rub * Decimal("100"))

        sold = self.paper_repository.mark_sold(
            position_id=position.id,
            sell_price_rub=quantize_money(sell_price),
            sell_fee_rub=total_sell_fee,
            net_revenue_rub=net_revenue,
            actual_profit_rub=actual_profit,
            actual_roi_percent=actual_roi,
        )
        logger.info("Paper Sell completed position %s with PnL %s RUB", sold.id, actual_profit)
        return sold

    async def check_trade_bans(self) -> list[PaperPositionORM]:
        ready = self.paper_repository.update_trade_locked_to_ready(utc_now())
        if ready:
            logger.info("%s paper positions became READY_TO_SELL", len(ready))
        if self.settings.paper_trading_sell_mode == "AFTER_TRADE_BAN":
            for position in list(ready):
                try:
                    await self.paper_sell(position.id)
                except Exception as exc:
                    logger.warning("Auto Paper Sell failed for %s: %s", position.id, exc)
        return ready

    async def _best_listing_for_item(
        self,
        connector: BaseMarketConnector,
        normalized_name: str,
    ) -> MarketListing | None:
        listings = await connector.fetch_listings()
        matches = [self._with_prices(listing) for listing in listings if listing.normalized_name == normalized_name and listing.available]
        if not matches:
            return None
        return max(matches, key=lambda item: item.price_rub or item.price)

    def _with_prices(self, listing: MarketListing) -> MarketListing:
        price_rub = listing.price_rub
        price_usd = listing.price_usd
        if price_rub is None:
            price_rub = self.currency_engine.to_rub(listing.price, listing.currency)
        if price_usd is None:
            price_usd = self.currency_engine.to_usd(price_rub, "RUB")
        return listing.model_copy(update={"price_rub": quantize_money(price_rub), "price_usd": quantize_money(price_usd)})

    def _ensure_paper_mode(self) -> None:
        if self.settings.trading_mode != TradingMode.PAPER_TRADING.value or not self.settings.paper_trading_enabled:
            raise PaperTradingError("Paper Trading is disabled")

