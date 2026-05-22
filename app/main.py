from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonCommands

from app.bot.handlers import build_bot_commands, create_router
from app.bot.keyboards import deal_keyboard
from app.bot.messages import format_deal
from app.config import get_settings
from app.db.database import init_db
from app.db.repositories import (
    DealRepository,
    IgnoredItemRepository,
    InventoryRepository,
    ScanLogRepository,
    TradingStateRepository,
)
from app.logging_config import setup_logging
from app.markets.csgo_market_client import CSGOMarketClient
from app.markets.dmarket_client import DMarketClient
from app.markets.lis_skins_client import LisSkinsClient
from app.services.inventory import InventoryService
from app.services.runtime_settings import RuntimeSettingsStore
from app.services.scanner import ArbitrageScanner


async def async_main() -> None:
    settings = get_settings()
    runtime_settings = RuntimeSettingsStore(settings)
    runtime_settings.load()
    setup_logging(settings)
    logger = logging.getLogger("app.main")

    session_factory = init_db(settings.database_url)
    deals = DealRepository(session_factory)
    inventory = InventoryRepository(session_factory)
    ignored_items = IgnoredItemRepository(session_factory)
    scan_logs = ScanLogRepository(session_factory)
    trading = TradingStateRepository(session_factory)
    trading.initialize(settings.default_trading_mode, settings.demo_initial_balance, settings.demo_currency)

    buy_market = LisSkinsClient(settings) if settings.buy_market_source == "LIS_SKINS" else DMarketClient(settings)
    csgo_market = CSGOMarketClient(settings)
    bot: Bot | None = Bot(settings.telegram_bot_token) if settings.telegram_ready else None

    async def notify_text(text: str) -> None:
        if bot is None:
            logger.info("Telegram disabled notification: %s", text)
            return
        await bot.send_message(chat_id=settings.authorized_telegram_id, text=text)

    async def notify_deal(deal) -> None:
        if bot is None:
            logger.info("New deal: %s %s", deal.item_name, deal.profit)
            return
        await bot.send_message(
            chat_id=settings.authorized_telegram_id,
            text=format_deal(deal, trading.get_mode()),
            reply_markup=deal_keyboard(deal),
        )

    scanner = ArbitrageScanner(
        settings=settings,
        dmarket=buy_market,
        csgo_market=csgo_market,
        deals=deals,
        ignored_items=ignored_items,
        scan_logs=scan_logs,
        trading=trading,
        on_new_deal=notify_deal,
        on_critical_error=notify_text,
    )
    inventory_service = InventoryService(
        settings=settings,
        deals=deals,
        inventory=inventory,
        trading=trading,
        dmarket=buy_market,
        csgo_market=csgo_market,
    )

    dispatcher: Dispatcher | None = None
    polling_task: asyncio.Task | None = None
    if bot is not None:
        dispatcher = Dispatcher()
        dispatcher.include_router(
            create_router(
                settings=settings,
                scanner=scanner,
                deals=deals,
                inventory=inventory,
                trading=trading,
                scan_logs=scan_logs,
                runtime_settings=runtime_settings,
                inventory_service=inventory_service,
                dmarket=buy_market,
                csgo_market=csgo_market,
            )
        )
        await bot.set_my_commands(build_bot_commands())
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        polling_task = asyncio.create_task(dispatcher.start_polling(bot), name="telegram_polling")
        logger.info("Telegram polling started for authorized user %s", settings.authorized_telegram_id)
    else:
        logger.warning("Telegram is disabled or TELEGRAM_BOT_TOKEN/AUTHORIZED_TELEGRAM_ID is not configured")

    await scanner.start()

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

    try:
        await stop_event.wait()
    finally:
        await scanner.stop()
        if dispatcher is not None:
            with suppress(Exception):
                await dispatcher.stop_polling()
        if polling_task is not None:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task
        if bot is not None:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(async_main())
