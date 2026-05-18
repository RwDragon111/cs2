from __future__ import annotations

import asyncio
import logging
import signal

from app.config import get_settings
from app.currency.currency_engine import CurrencyEngine
from app.db.database import init_db
from app.db.repositories import ListingRepository, OpportunityRepository, PaperRepository, PaymentProfileRepository
from app.liquidity.liquidity_engine import LiquidityEngine
from app.logging_config import setup_logging
from app.markets.payment_profile import default_payment_profiles
from app.opportunities.detector import OpportunityDetector
from app.paper_trading.account import PaperAccountService
from app.paper_trading.paper_execution import PaperExecutionEngine
from app.pricing.pricing_engine import PricingEngine
from app.risk.risk_filters import RiskFilters
from app.scheduler.jobs import build_connectors, fetch_fees
from app.scheduler.runner import SchedulerRunner
from app.telegram_bot.bot import TelegramBotRunner, TelegramNotifier
from app.telegram_bot.handlers import create_router


async def async_main() -> None:
    settings = get_settings()
    setup_logging(settings)
    logger = logging.getLogger("main")
    logger.info("Starting CS2 Arbitrage Bot in %s mode", settings.trading_mode)

    session_factory = init_db(settings.database_url)
    listing_repository = ListingRepository(session_factory)
    payment_repository = PaymentProfileRepository(session_factory)
    opportunity_repository = OpportunityRepository(session_factory)
    paper_repository = PaperRepository(session_factory)

    payment_profiles = default_payment_profiles(settings)
    payment_repository.upsert_profiles(payment_profiles.values())

    connectors = build_connectors(settings)
    currency_engine = CurrencyEngine(settings)
    pricing_engine = PricingEngine(settings)
    liquidity_engine = LiquidityEngine()
    risk_filters = RiskFilters(settings)
    fees_by_market = await fetch_fees(connectors)

    paper_account_service = PaperAccountService(settings, paper_repository)
    paper_account_service.initialize()

    opportunity_detector = OpportunityDetector(
        settings=settings,
        currency_engine=currency_engine,
        pricing_engine=pricing_engine,
        liquidity_engine=liquidity_engine,
        risk_filters=risk_filters,
        payment_profiles=payment_profiles,
        fees_by_market=fees_by_market,
    )

    paper_engine = PaperExecutionEngine(
        settings=settings,
        paper_repository=paper_repository,
        opportunity_repository=opportunity_repository,
        connectors=connectors,
        pricing_engine=pricing_engine,
        currency_engine=currency_engine,
        payment_profiles=payment_profiles,
        fees_by_market=fees_by_market,
    )

    notifier = TelegramNotifier(settings)
    telegram_runner = TelegramBotRunner(
        settings=settings,
        notifier=notifier,
        router_factory=lambda: create_router(
            paper_engine=paper_engine,
            paper_account=paper_account_service,
            paper_repository=paper_repository,
            opportunity_repository=opportunity_repository,
        ),
    )
    scheduler = SchedulerRunner(
        settings=settings,
        connectors=connectors,
        fees_by_market=fees_by_market,
        listing_repository=listing_repository,
        opportunity_repository=opportunity_repository,
        opportunity_detector=opportunity_detector,
        paper_engine=paper_engine,
        notifier=notifier,
        telegram_runner=telegram_runner,
    )

    stop_event = asyncio.Event()

    def request_stop() -> None:
        logger.info("Stop requested")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: request_stop())

    await scheduler.start()
    await stop_event.wait()
    await scheduler.stop()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass

