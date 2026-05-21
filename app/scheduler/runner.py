from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.config import Settings
from app.db.repositories import ListingRepository, OpportunityRepository
from app.markets.base import BaseMarketConnector, MarketFees, MarketListing
from app.opportunities.detector import OpportunityDetector
from app.opportunities.stats_spread import StatsSpreadDetector
from app.paper_trading.paper_execution import PaperExecutionEngine
from app.scheduler.jobs import fetch_all_listings, fetch_sales_history_sample
from app.telegram_bot.bot import TelegramBotRunner, TelegramNotifier
from app.telegram_bot.formatter import format_opportunity, format_position_ready, format_stats_spread
from app.telegram_bot.keyboards import opportunity_keyboard, paper_sell_keyboard

logger = logging.getLogger(__name__)


class SchedulerRunner:
    def __init__(
        self,
        settings: Settings,
        connectors: dict[str, BaseMarketConnector],
        fees_by_market: dict[str, MarketFees],
        listing_repository: ListingRepository,
        opportunity_repository: OpportunityRepository,
        opportunity_detector: OpportunityDetector,
        paper_engine: PaperExecutionEngine,
        notifier: TelegramNotifier,
        telegram_runner: TelegramBotRunner,
    ) -> None:
        self.settings = settings
        self.connectors = connectors
        self.fees_by_market = fees_by_market
        self.listing_repository = listing_repository
        self.opportunity_repository = opportunity_repository
        self.opportunity_detector = opportunity_detector
        self.paper_engine = paper_engine
        self.notifier = notifier
        self.telegram_runner = telegram_runner
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.current_listings: list[MarketListing] = []
        self.sent_opportunity_ids: set[str] = set()
        self.sent_stats_spread_ids: set[str] = set()
        self.sent_market_scan_summary = False
        self.sent_opportunity_scan_summary = False
        self.notified_ready_position_ids: set[str] = set()
        self.stats_spread_detector = StatsSpreadDetector(
            min_spread_percent=self.settings.min_stats_spread_percent,
            min_spread_rub=self.settings.min_stats_absolute_spread_rub,
            max_signals=self.settings.max_stats_signals_per_scan,
        )

    async def start(self) -> None:
        await self.telegram_runner.start()
        self.sent_opportunity_ids.update(row.id for row in self.opportunity_repository.active(limit=1000))
        if self.sent_opportunity_ids:
            logger.info("Loaded %s already active opportunities; they will not be re-sent", len(self.sent_opportunity_ids))
        self._tasks = [
            asyncio.create_task(self.market_poll_loop(), name="market_poll_loop"),
            asyncio.create_task(self.opportunity_detection_loop(), name="opportunity_detection_loop"),
            asyncio.create_task(self.paper_positions_loop(), name="paper_positions_loop"),
        ]
        logger.info("Scheduler started with %s connectors", len(self.connectors))

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        await self.telegram_runner.stop()
        await self.notifier.close()
        logger.info("Scheduler stopped")

    async def wait(self) -> None:
        await self._stop.wait()

    async def market_poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                listings_by_market = await fetch_all_listings(
                    self.connectors,
                    self.opportunity_detector.currency_engine,
                    self.settings,
                )
                self.current_listings = [listing for listings in listings_by_market.values() for listing in listings]
                for market_name, listings in listings_by_market.items():
                    self.listing_repository.replace_market_listings(market_name, listings)
                logger.info("Market polling updated %s listings", len(self.current_listings))
                if not self.sent_market_scan_summary:
                    self.sent_market_scan_summary = True
                    await self.notifier.send_message(
                        "Сканирование рынков запущено\n\n"
                        f"Market.CSGO buy orders: {len(listings_by_market.get('Market.CSGO.BuyOrder', []))}\n"
                        f"DMarket offers: {len(listings_by_market.get('DMarket', []))}\n\n"
                        "Бот ищет направление DMarket -> Market.CSGO.BuyOrder. "
                        "Если подходящей разницы после комиссий нет, сигнал сделки не отправляется."
                    )
            except Exception as exc:
                logger.exception("Market polling job failed: %s", exc)
            await asyncio.sleep(self.settings.market_poll_interval_seconds)

    async def opportunity_detection_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.current_listings:
                    logger.info("Opportunity scan is waiting for the first market polling result")
                    await asyncio.sleep(self.settings.opportunity_scan_interval_seconds)
                    continue
                names = {listing.normalized_name for listing in self.current_listings}
                histories = await fetch_sales_history_sample(self.connectors, names)
                opportunities = self.opportunity_detector.detect(self.current_listings, histories)
                self.opportunity_repository.save_many(opportunities)
                self.opportunity_repository.expire_missing({opportunity.id for opportunity in opportunities})
                logger.info(
                    "Opportunity scan checked %s listings and found %s opportunities",
                    len(self.current_listings),
                    len(opportunities),
                )
                if not self.sent_opportunity_scan_summary:
                    self.sent_opportunity_scan_summary = True
                    dmarket_names = {
                        listing.normalized_name
                        for listing in self.current_listings
                        if listing.market_name == "DMarket"
                    }
                    market_csgo_buy_order_names = {
                        listing.normalized_name
                        for listing in self.current_listings
                        if listing.market_name == "Market.CSGO.BuyOrder"
                    }
                    await self.notifier.send_message(
                        "Первый поиск арбитража выполнен\n\n"
                        f"Проверено листингов: {len(self.current_listings)}\n"
                        f"Совпадающих предметов DMarket/Market.CSGO buy orders: "
                        f"{len(dmarket_names & market_csgo_buy_order_names)}\n"
                        f"Сигналов после комиссий и фильтров: {len(opportunities)}\n\n"
                        "Если сигналов 0, значит по текущим реальным ценам нет сделки, "
                        "которая проходит MIN_PROFIT_RUB, MIN_ROI_PERCENT и MIN_LIQUIDITY_SCORE."
                    )
                for opportunity in opportunities:
                    if opportunity.id in self.sent_opportunity_ids:
                        continue
                    self.sent_opportunity_ids.add(opportunity.id)
                    await self.notifier.send_message(
                        format_opportunity(opportunity),
                        reply_markup=opportunity_keyboard(opportunity),
                    )
                if self.settings.enable_stats_spread_signals:
                    for signal in self.stats_spread_detector.detect(self.current_listings):
                        if signal.id in self.sent_stats_spread_ids:
                            continue
                        self.sent_stats_spread_ids.add(signal.id)
                        await self.notifier.send_message(format_stats_spread(signal))
            except Exception as exc:
                logger.exception("Opportunity detection job failed: %s", exc)
            await asyncio.sleep(self.settings.opportunity_scan_interval_seconds)

    async def paper_positions_loop(self) -> None:
        while not self._stop.is_set():
            try:
                ready_positions = await self.paper_engine.check_trade_bans()
                for position in ready_positions:
                    if position.id in self.notified_ready_position_ids:
                        continue
                    self.notified_ready_position_ids.add(position.id)
                    await self.notifier.send_message(
                        format_position_ready(position),
                        reply_markup=paper_sell_keyboard(position.id),
                    )
            except Exception as exc:
                logger.exception("Paper positions job failed: %s", exc)
            await asyncio.sleep(self.settings.paper_position_check_interval_seconds)
