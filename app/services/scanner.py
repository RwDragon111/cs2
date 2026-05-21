from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.config import Settings
from app.db.models import DealORM
from app.db.repositories import DealRepository, IgnoredItemRepository, ScanLogRepository, TradingStateRepository
from app.markets.csgo_market_client import CSGOMarketClient
from app.markets.dmarket_client import DMarketClient
from app.markets.types import BuyOrder
from app.services.arbitrage import ArbitrageCalculator
from app.services.liquidity import LiquidityScorer
from app.services.price_analysis import PriceAnalyzer
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

DealNotifier = Callable[[DealORM], Awaitable[None]]
ErrorNotifier = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class ScannerStatus:
    is_running: bool = False
    is_paused: bool = False
    started_at: datetime = field(default_factory=utc_now)
    last_scan_started_at: datetime | None = None
    last_scan_finished_at: datetime | None = None
    last_found_deals_count: int = 0
    total_found_deals_count: int = 0
    last_error: str | None = None
    api_errors: list[str] = field(default_factory=list)


class ArbitrageScanner:
    def __init__(
        self,
        settings: Settings,
        dmarket: DMarketClient,
        csgo_market: CSGOMarketClient,
        deals: DealRepository,
        ignored_items: IgnoredItemRepository,
        scan_logs: ScanLogRepository,
        trading: TradingStateRepository,
        on_new_deal: DealNotifier | None = None,
        on_critical_error: ErrorNotifier | None = None,
    ) -> None:
        self.settings = settings
        self.dmarket = dmarket
        self.csgo_market = csgo_market
        self.deals = deals
        self.ignored_items = ignored_items
        self.scan_logs = scan_logs
        self.trading = trading
        self.on_new_deal = on_new_deal
        self.on_critical_error = on_critical_error
        self.calculator = ArbitrageCalculator(settings)
        self.liquidity = LiquidityScorer()
        self.price_analyzer = PriceAnalyzer(settings)
        self.status = ScannerStatus()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._scan_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self.status.is_running = True
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="arbitrage_scanner")
        logger.info("Arbitrage scanner started")

    async def stop(self) -> None:
        self._stop.set()
        self.status.is_running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def pause(self) -> None:
        self.status.is_paused = True

    def resume(self) -> None:
        self.status.is_paused = False

    async def scan_once(self, notify: bool = True) -> list[DealORM]:
        async with self._scan_lock:
            return await self._scan_once_locked(notify=notify)

    async def _scan_once_locked(self, notify: bool = True) -> list[DealORM]:
        scan_log = self.scan_logs.start()
        self.status.last_scan_started_at = scan_log.started_at
        found: list[DealORM] = []
        error_message: str | None = None
        try:
            source_mode = self.trading.get_mode()
            buy_orders = await self.csgo_market.fetch_buy_orders()
            targeted_titles = self._select_dmarket_titles(buy_orders)
            offers = await self.dmarket.fetch_offers(targeted_titles)
            ignored = self.ignored_items.names()
            best_orders = self._best_orders_by_name(buy_orders)
            matching_offers = 0
            price_filtered_offers = 0
            liquidity_filtered_offers = 0
            for offer in offers:
                if offer.market_hash_name.lower() in ignored or offer.item_name.lower() in ignored:
                    continue
                order = best_orders.get(offer.market_hash_name)
                if order is None:
                    continue
                matching_offers += 1
                if order.price_rub < self.settings.min_item_price or order.price_rub > self.settings.max_item_price:
                    price_filtered_offers += 1
                    continue

                history = await self.csgo_market.fetch_price_history(offer.market_hash_name, order.price_rub)
                history.buy_order_count = max(history.buy_order_count, order.count)
                liquidity = self.liquidity.score(order, history)
                price_analysis = self.price_analyzer.analyze(order.price_rub, history)
                if liquidity.score < self.settings.min_liquidity_score:
                    liquidity_filtered_offers += 1
                candidate = self.calculator.evaluate(
                    offer=offer,
                    order=order,
                    liquidity=liquidity,
                    price_analysis=price_analysis,
                    source_mode=source_mode,
                )
                if candidate is None:
                    continue
                row, created = self.deals.upsert(candidate.to_orm_payload())
                if created:
                    found.append(row)
            logger.info(
                "Scan checked %s CSGO buy orders, selected %s DMarket titles, got %s DMarket offers, "
                "matched %s offers, price-filtered %s, liquidity-filtered %s, found %s new deals",
                len(buy_orders),
                len(targeted_titles),
                len(offers),
                matching_offers,
                price_filtered_offers,
                liquidity_filtered_offers,
                len(found),
            )
            self.status.last_error = None
        except Exception as exc:
            logger.exception("Arbitrage scan failed: %s", exc)
            error_message = str(exc)
            self.status.last_error = error_message
            self.status.api_errors = [*self.status.api_errors[-9:], error_message]
            if self.on_critical_error is not None:
                await self.on_critical_error(f"Критическая ошибка сканера: {error_message}")
        finally:
            self.scan_logs.finish(scan_log.id, len(found), error_message)
            self.status.last_scan_finished_at = utc_now()
            self.status.last_found_deals_count = len(found)
            self.status.total_found_deals_count += len(found)

        for deal in found:
            if notify and self.on_new_deal is not None:
                await self.on_new_deal(deal)
        return found

    async def _loop(self) -> None:
        while not self._stop.is_set():
            if not self.status.is_paused:
                await self.scan_once()
            await asyncio.sleep(self.settings.scan_interval_seconds)

    @staticmethod
    def _best_orders_by_name(orders: list[BuyOrder]) -> dict[str, BuyOrder]:
        best: dict[str, BuyOrder] = {}
        for order in orders:
            current = best.get(order.market_hash_name)
            if current is None or Decimal(order.price_rub) > Decimal(current.price_rub):
                best[order.market_hash_name] = order
        return best

    def _select_dmarket_titles(self, orders: list[BuyOrder]) -> list[str]:
        candidates: list[tuple[Decimal, Decimal, int, str]] = []
        for order in orders:
            if order.price_rub < self.settings.min_item_price or order.price_rub > self.settings.max_item_price:
                continue
            liquidity_weight = Decimal(min(max(order.count, 1), 100))
            candidates.append((order.price_rub * liquidity_weight, order.price_rub, order.count, order.item_name))

        buckets = [
            (self.settings.min_item_price, Decimal("1000")),
            (Decimal("1000"), Decimal("3000")),
            (Decimal("3000"), Decimal("10000")),
            (Decimal("10000"), self.settings.max_item_price),
        ]
        titles: list[str] = []
        seen: set[str] = set()
        limit = max(1, min(self.settings.dmarket_dynamic_title_limit, 200))

        def add_title(title: str) -> None:
            key = title.lower()
            if key not in seen and len(titles) < limit:
                seen.add(key)
                titles.append(title)

        per_bucket = max(1, limit // len(buckets))
        for low, high in buckets:
            rows = [row for row in candidates if low <= row[1] < high]
            rows.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
            for _, _, _, title in rows[:per_bucket]:
                add_title(title)
                if len(titles) >= limit:
                    break

        candidates.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
        for _, _, _, title in candidates:
            add_title(title)
            if len(titles) >= limit:
                break
        return titles
