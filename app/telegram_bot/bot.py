from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings
from app.telegram_bot.commands import build_bot_commands

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot: Any | None = None
        if self.settings.telegram_ready:
            try:
                from aiogram import Bot

                self.bot = Bot(token=self.settings.telegram_bot_token)
            except Exception as exc:
                logger.warning("Telegram bot initialization failed; falling back to logs: %s", exc)

    async def send_message(self, text: str, reply_markup: Any | None = None) -> None:
        if self.bot is None or not self.settings.telegram_admin_chat_id:
            logger.info("Telegram disabled/log notification:\n%s", text)
            return
        try:
            await self.bot.send_message(
                chat_id=self.settings.telegram_admin_chat_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning("Telegram send_message failed: %s", exc)

    async def close(self) -> None:
        if self.bot is not None:
            await self.bot.session.close()


class TelegramBotRunner:
    def __init__(self, settings: Settings, notifier: TelegramNotifier, router_factory) -> None:
        self.settings = settings
        self.notifier = notifier
        self.router_factory = router_factory
        self._task: asyncio.Task | None = None
        self._dispatcher: Any | None = None

    async def start(self) -> None:
        if self.notifier.bot is None or not self.settings.telegram_ready:
            logger.info("Telegram polling is disabled")
            return
        from aiogram import Dispatcher
        from aiogram.types import MenuButtonCommands

        self._dispatcher = Dispatcher()
        self._dispatcher.include_router(self.router_factory())
        try:
            await self.notifier.bot.set_my_commands(build_bot_commands())
            await self.notifier.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as exc:
            logger.warning("Telegram command menu setup failed: %s", exc)
        self._task = asyncio.create_task(self._dispatcher.start_polling(self.notifier.bot))
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        if self._dispatcher is not None:
            await self._dispatcher.stop_polling()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
