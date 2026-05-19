from __future__ import annotations

import logging

from app.db.repositories import ListingRepository, OpportunityRepository, PaperRepository
from app.opportunities.stats_spread import StatsSpreadDetector
from app.paper_trading.account import PaperAccountService
from app.paper_trading.paper_execution import PaperExecutionEngine
from app.telegram_bot.commands import commands_help_text
from app.telegram_bot.formatter import (
    format_dmarket_stats,
    format_paper_buy,
    format_paper_sell,
    format_paper_status,
    format_stats_spread_list,
    orm_listing_to_market_listing,
)

logger = logging.getLogger(__name__)


def create_router(
    paper_engine: PaperExecutionEngine,
    paper_account: PaperAccountService,
    paper_repository: PaperRepository,
    opportunity_repository: OpportunityRepository,
    listing_repository: ListingRepository,
):
    from aiogram import F, Router
    from aiogram.filters import Command
    from aiogram.types import CallbackQuery, Message

    router = Router()

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(
            "CS2 Arbitrage Bot запущен.\n\n"
            "Рабочая схема: DMarket -> Market.CSGO buy orders.\n"
            "Реальные покупки и продажи в MVP отключены, доступен только Paper Trading.\n\n"
            "Нажми кнопку меню Telegram слева снизу, чтобы увидеть все команды."
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(commands_help_text())

    @router.message(Command("status", "paper_status", "pnl", "paper_pnl"))
    async def status(message: Message) -> None:
        await message.answer(format_paper_status(paper_account.analytics()))

    @router.message(Command("balance", "paper_balance"))
    async def balance(message: Message) -> None:
        account = paper_repository.account()
        await message.answer(f"Paper balance: {account.current_balance_rub} RUB")

    @router.message(Command("opportunities", "last"))
    async def opportunities(message: Message) -> None:
        rows = opportunity_repository.active(limit=10)
        if not rows:
            await message.answer("Активных opportunities пока нет.")
            return
        lines = ["Активные opportunities:"]
        for row in rows:
            lines.append(
                f"{row.id[:8]} | {row.normalized_name} | {row.expected_net_profit_rub} RUB | ROI {row.roi_percent}%"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("positions", "paper_positions", "paper_open", "paper_ready", "paper_sold"))
    async def positions(message: Message) -> None:
        rows = paper_repository.positions()
        if not rows:
            await message.answer("Paper positions пока нет.")
            return
        lines = ["Paper positions:"]
        for row in rows[:20]:
            lines.append(f"{row.id[:8]} | {row.status} | {row.normalized_name} | expected {row.expected_profit_rub} RUB")
        await message.answer("\n".join(lines))

    @router.message(Command("settings", "paper_settings"))
    async def settings(message: Message) -> None:
        await message.answer(
            "TRADING_MODE=PAPER_TRADING\n"
            "USE_MOCK_MARKETS=false\n"
            "ENABLE_DMARKET=true\n"
            "ENABLE_MARKET_CSGO=true\n"
            "Реальные покупки/продажи отключены."
        )

    @router.message(Command("blacklist"))
    async def blacklist(message: Message) -> None:
        await message.answer("Blacklist хранится в SQLite. CS.MONEY и White.Market запрещены кодом.")

    @router.message(Command("payment_status", "markets"))
    async def markets(message: Message) -> None:
        await message.answer(
            "Рабочая схема MVP: DMarket реальные офферы -> Market.CSGO лучший buy order.\n"
            "LIS-SKINS отключен из базового контура.\n"
            "Mock-данные используются только при USE_MOCK_MARKETS=true.\n"
            "Реальные покупки и продажи в MVP не выполняются."
        )

    @router.message(Command("dmarket_stats"))
    async def dmarket_stats(message: Message) -> None:
        rows = listing_repository.latest_by_market("DMarket", limit=10)
        total = listing_repository.count_by_market("DMarket")
        await message.answer(format_dmarket_stats(rows, total))

    @router.message(Command("market_spreads"))
    async def market_spreads(message: Message) -> None:
        rows = listing_repository.latest_by_markets(["Market.CSGO.BuyOrder", "DMarket"], limit_per_market=300)
        listings = [orm_listing_to_market_listing(row) for row in rows]
        detector = StatsSpreadDetector(min_spread_percent=0, min_spread_rub=0, max_signals=10)
        await message.answer(format_stats_spread_list(detector.detect(listings)))

    @router.message(Command("pause", "resume", "paper_reset"))
    async def not_implemented(message: Message) -> None:
        await message.answer("Команда зарезервирована для следующей итерации MVP.")

    @router.message(Command("paper_buy"))
    async def paper_buy_command(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /paper_buy <opportunity_id>")
            return
        await _paper_buy(message, parts[1].strip())

    @router.message(Command("paper_sell"))
    async def paper_sell_command(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /paper_sell <position_id>")
            return
        await _paper_sell(message, parts[1].strip())

    @router.callback_query(F.data.startswith("paper_buy:"))
    async def paper_buy_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        assert callback.message is not None
        await _paper_buy(callback.message, callback.data.split(":", 1)[1])

    @router.callback_query(F.data.startswith("paper_sell:"))
    async def paper_sell_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        assert callback.message is not None
        await _paper_sell(callback.message, callback.data.split(":", 1)[1])

    async def _paper_buy(message: Message, opportunity_id: str) -> None:
        try:
            position = await paper_engine.paper_buy(opportunity_id)
            account = paper_repository.account()
            await message.answer(format_paper_buy(position, account.current_balance_rub))
        except Exception as exc:
            logger.warning("Paper Buy failed from Telegram: %s", exc)
            await message.answer(f"Paper Buy не выполнен: {exc}")

    async def _paper_sell(message: Message, position_id: str) -> None:
        try:
            position = await paper_engine.paper_sell(position_id)
            account = paper_repository.account()
            await message.answer(format_paper_sell(position, account.current_balance_rub))
        except Exception as exc:
            logger.warning("Paper Sell failed from Telegram: %s", exc)
            await message.answer(f"Paper Sell не выполнен: {exc}")

    return router
