from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.keyboards import deal_keyboard, inventory_keyboard, real_confirmation_keyboard, refresh_keyboard
from app.bot.messages import (
    format_deal,
    format_deal_details,
    format_deals_list,
    format_demo_balance,
    format_demo_stats,
    format_help,
    format_inventory,
    format_real_balance,
    format_settings,
    format_status,
    mode_label,
)
from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.db.repositories import DealRepository, InventoryRepository, ScanLogRepository, TradingStateRepository
from app.markets.csgo_market_client import CSGOMarketClient
from app.services.inventory import InventoryService
from app.services.runtime_settings import RuntimeSettingsStore, format_editable_settings_help
from app.services.scanner import ArbitrageScanner, BuyMarketClient


class TelegramAuthMiddleware(BaseMiddleware):
    def __init__(self, authorized_user_id: int) -> None:
        self.authorized_user_id = authorized_user_id

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user is None and hasattr(event, "from_user"):
            user = getattr(event, "from_user")
        if user is None or int(user.id) != int(self.authorized_user_id):
            if isinstance(event, Message):
                await event.answer("Access denied")
            elif isinstance(event, CallbackQuery):
                await event.answer("Access denied", show_alert=True)
            return None
        return await handler(event, data)


def build_bot_commands():
    from aiogram.types import BotCommand

    commands = [
        ("start", "Главное меню"),
        ("status", "Статус сканера"),
        ("balance", "Баланс"),
        ("deals", "Найденные сделки"),
        ("best", "Лучшие сделки"),
        ("inventory", "Купленные скины"),
        ("locked", "Trade lock"),
        ("ready", "Готово к продаже"),
        ("settings", "Фильтры"),
        ("settings_help", "Изменяемые настройки"),
        ("set", "Изменить настройку"),
        ("rescan", "Пересканировать рынок"),
        ("pause", "Пауза сканера"),
        ("resume", "Запуск сканера"),
        ("mode", "Режим DEMO/REAL"),
        ("demo_on", "Включить DEMO"),
        ("demo_off", "Включить REAL"),
        ("demo_balance", "Демо-баланс"),
        ("demo_set_balance", "Задать демо-баланс"),
        ("demo_reset", "Сбросить DEMO"),
        ("demo_stats", "Статистика DEMO"),
        ("help", "Справка"),
    ]
    return [BotCommand(command=command, description=description) for command, description in commands]


def create_router(
    settings: Settings,
    scanner: ArbitrageScanner,
    deals: DealRepository,
    inventory: InventoryRepository,
    trading: TradingStateRepository,
    scan_logs: ScanLogRepository,
    runtime_settings: RuntimeSettingsStore,
    inventory_service: InventoryService,
    dmarket: BuyMarketClient,
    csgo_market: CSGOMarketClient,
) -> Router:
    router = Router()
    router.message.middleware(TelegramAuthMiddleware(settings.authorized_telegram_id))
    router.callback_query.middleware(TelegramAuthMiddleware(settings.authorized_telegram_id))

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        mode = trading.get_mode()
        await message.answer(
            "CS2 Arbitrage Bot запущен.\n\n"
            f"Маршрут анализа: купить на {settings.buy_market_name} и продать в buy order на CSGO Market.\n"
            f"Текущий режим: {mode_label(mode)}\n\n"
            "Реальные операции отключены. Бот присылает сигналы и ссылки, покупку ты делаешь вручную.",
            reply_markup=refresh_keyboard("deals"),
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(format_help())

    @router.message(Command("status"))
    async def status(message: Message) -> None:
        await message.answer(format_status(scanner.status, scan_logs.latest()))

    @router.message(Command("balance", "demo_balance"))
    async def balance(message: Message) -> None:
        mode = trading.get_mode()
        if mode == "DEMO" or (message.text or "").startswith("/demo_balance"):
            await message.answer(format_demo_balance(trading.demo_account(), inventory.list(is_demo=True, limit=10000)))
            return
        buy_market_balance, csgo_balance = await asyncio.gather(dmarket.get_balance(), csgo_market.get_balance())
        await message.answer(format_real_balance(buy_market_balance, csgo_balance, inventory.list(is_demo=False, limit=10000)))

    @router.message(Command("deals"))
    async def deal_list(message: Message) -> None:
        rows = deals.latest(limit=10)
        if not rows:
            await message.answer("Подходящих сделок пока нет.", reply_markup=refresh_keyboard("deals"))
            return
        await message.answer(format_deals_list(rows, trading.get_mode()))
        for row in rows[:5]:
            await message.answer(format_deal(row, trading.get_mode()), reply_markup=deal_keyboard(row))

    @router.message(Command("best"))
    async def best(message: Message) -> None:
        await message.answer(format_deals_list(deals.best(limit=10), trading.get_mode(), title="Топ сделок"))

    @router.message(Command("rescan"))
    async def rescan(message: Message) -> None:
        await message.answer("Запускаю перескан по текущим настройкам.")
        rows = await scanner.scan_once(notify=False, include_existing=True)
        if not rows:
            await message.answer("Подходящих сделок по текущим фильтрам не найдено.", reply_markup=refresh_keyboard("deals"))
            return
        await message.answer(format_deals_list(rows[:10], trading.get_mode(), title="Результат перескана"))
        for row in rows[:5]:
            await message.answer(format_deal(row, trading.get_mode()), reply_markup=deal_keyboard(row))

    @router.message(Command("inventory"))
    async def inventory_command(message: Message) -> None:
        inventory_service.refresh_trade_locks()
        await message.answer(format_inventory(inventory.list(limit=50), "Купленные скины / текущие сделки"))

    @router.message(Command("locked"))
    async def locked(message: Message) -> None:
        await message.answer(format_inventory(inventory.list(statuses=["bought", "trade_locked"], limit=50), "Trade lock"))

    @router.message(Command("ready"))
    async def ready(message: Message) -> None:
        inventory_service.refresh_trade_locks()
        rows = inventory.list(statuses=["ready_to_sell"], limit=50)
        if not rows:
            await message.answer("Готовых к продаже предметов пока нет.")
            return
        for row in rows:
            await message.answer(format_inventory([row], "Готово к продаже"), reply_markup=inventory_keyboard(row.id))

    @router.message(Command("settings"))
    async def settings_command(message: Message) -> None:
        await message.answer(format_settings(settings, trading.get_mode(), runtime_settings.path))

    @router.message(Command("settings_help"))
    async def settings_help(message: Message) -> None:
        await message.answer(format_editable_settings_help(runtime_settings.path))

    @router.message(Command("set"))
    async def set_setting(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) != 3:
            await message.answer("Использование: /set MIN_PROFIT_PERCENT 2\nСписок настроек: /settings_help")
            return
        try:
            spec, value = runtime_settings.set(parts[1], parts[2])
        except ValueError as exc:
            await message.answer(f"Не удалось изменить настройку: {exc}\nСписок настроек: /settings_help")
            return
        await message.answer(
            f"Настройка сохранена: {spec.key}={value}\n"
            f"Файл: {runtime_settings.path}\n\n"
            "Она уже применяется в текущем процессе. Нажми /rescan, чтобы пересканировать рынок по новым фильтрам."
        )

    @router.message(Command("pause"))
    async def pause(message: Message) -> None:
        scanner.pause()
        await message.answer("Сканирование поставлено на паузу.")

    @router.message(Command("resume"))
    async def resume(message: Message) -> None:
        scanner.resume()
        await message.answer("Сканирование возобновлено.")

    @router.message(Command("mode"))
    async def mode(message: Message) -> None:
        await message.answer(f"Текущий режим: {mode_label(trading.get_mode())}")

    @router.message(Command("demo_on"))
    async def demo_on(message: Message) -> None:
        trading.set_mode("DEMO")
        await message.answer("DEMO-режим включен. Реальные операции не выполняются.")

    @router.message(Command("demo_off"))
    async def demo_off(message: Message) -> None:
        if not settings.allow_real_trading:
            await message.answer(
                "REAL-режим отключен в настройках сервера. Измени ALLOW_REAL_TRADING=true в .env, "
                "если хочешь разрешить реальные операции."
            )
            return
        trading.set_mode("REAL")
        await message.answer("REAL-режим включен. Любая покупка или продажа потребует ручного подтверждения.")

    @router.message(Command("demo_set_balance"))
    async def demo_set_balance(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /demo_set_balance 100000")
            return
        try:
            balance_value = Decimal(parts[1].replace(",", "."))
        except Exception:
            await message.answer("Не смог прочитать сумму. Пример: /demo_set_balance 100000")
            return
        account = trading.set_demo_balance(balance_value)
        await message.answer(f"Демо-баланс установлен: {account.balance} {account.currency}")

    @router.message(Command("demo_reset"))
    async def demo_reset(message: Message) -> None:
        account = trading.reset_demo(settings.demo_initial_balance, settings.demo_currency)
        await message.answer(f"Демо-счет сброшен: {account.balance} {account.currency}")

    @router.message(Command("demo_stats"))
    async def demo_stats(message: Message) -> None:
        await message.answer(format_demo_stats(inventory_service.demo_stats()))

    @router.callback_query(F.data == "refresh_deals")
    async def refresh_deals(callback: CallbackQuery) -> None:
        await callback.answer("Обновляю")
        rows = await scanner.scan_once(notify=False, include_existing=True)
        if callback.message is not None:
            if not rows:
                await callback.message.answer("Подходящих сделок по текущим фильтрам не найдено.", reply_markup=refresh_keyboard("deals"))
                return
            await callback.message.answer(format_deals_list(rows[:10], trading.get_mode(), title="Результат перескана"))
            for row in rows[:5]:
                await callback.message.answer(format_deal(row, trading.get_mode()), reply_markup=deal_keyboard(row))

    @router.callback_query(F.data == "refresh_inventory")
    async def refresh_inventory(callback: CallbackQuery) -> None:
        await callback.answer("Обновлено")
        inventory_service.refresh_trade_locks()
        if callback.message is not None:
            await callback.message.answer(format_inventory(inventory.list(limit=50), "Inventory"))

    @router.callback_query(F.data.startswith("deal_details:"))
    async def deal_details(callback: CallbackQuery) -> None:
        await callback.answer()
        deal = deals.get(_callback_id(callback.data))
        if callback.message is not None:
            await callback.message.answer(format_deal_details(deal, trading.get_mode()) if deal else "Сделка не найдена.")

    @router.callback_query(F.data.startswith("deal_hide:"))
    async def deal_hide(callback: CallbackQuery) -> None:
        deal = deals.mark_status(_callback_id(callback.data), "hidden")
        await callback.answer("Скрыто" if deal else "Не найдено")
        if deal:
            await _delete_callback_message(callback)

    @router.callback_query(F.data.startswith("deal_watch:"))
    async def deal_watch(callback: CallbackQuery) -> None:
        deal = deals.mark_status(_callback_id(callback.data), "watching")
        await callback.answer("Добавлено в наблюдение" if deal else "Не найдено")

    @router.callback_query(F.data.startswith("deal_buy:"))
    async def deal_buy(callback: CallbackQuery) -> None:
        deal_id = _callback_id(callback.data)
        mode = trading.get_mode()
        if mode == "REAL":
            await callback.answer()
            if callback.message is not None:
                await callback.message.answer(
                    "⚠️ Вы в REAL-режиме. Это действие может использовать реальные деньги. Подтвердить?",
                    reply_markup=real_confirmation_keyboard("buy", deal_id),
                )
            return
        await _buy_deal(callback, deal_id, confirmed_real=False)

    @router.callback_query(F.data.startswith("inventory_sell:"))
    async def inventory_sell(callback: CallbackQuery) -> None:
        inventory_id = _callback_id(callback.data)
        item = inventory.get(inventory_id)
        mode = trading.get_mode()
        if mode == "REAL" and item is not None and not item.is_demo:
            await callback.answer()
            if callback.message is not None:
                await callback.message.answer(
                    "⚠️ Вы в REAL-режиме. Это действие может использовать реальные деньги. Подтвердить?",
                    reply_markup=real_confirmation_keyboard("sell", inventory_id),
                )
            return
        await _sell_inventory(callback, inventory_id, confirmed_real=False)

    @router.callback_query(F.data.startswith("real_confirm:"))
    async def real_confirm(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 3:
            await callback.answer("Некорректная команда", show_alert=True)
            return
        action, raw_id = parts[1], int(parts[2])
        if action == "buy":
            await _buy_deal(callback, raw_id, confirmed_real=True)
        elif action == "sell":
            await _sell_inventory(callback, raw_id, confirmed_real=True)
        else:
            await callback.answer("Неизвестное действие", show_alert=True)

    @router.callback_query(F.data == "real_cancel")
    async def real_cancel(callback: CallbackQuery) -> None:
        await callback.answer("Отменено")
        await _delete_callback_message(callback)

    async def _buy_deal(callback: CallbackQuery, deal_id: int, confirmed_real: bool) -> None:
        try:
            await inventory_service.mark_deal_bought(deal_id, confirmed_real=confirmed_real)
        except RealTradingDisabledError as exc:
            await callback.answer("REAL операция не выполнена", show_alert=True)
            if callback.message is not None:
                await callback.message.answer(str(exc))
            return
        except Exception as exc:
            await callback.answer("Ошибка", show_alert=True)
            if callback.message is not None:
                await callback.message.answer(f"Не удалось отметить покупку: {exc}")
            return
        await callback.answer("Покупка отмечена. Смотри /inventory")
        await _delete_callback_message(callback)

    async def _sell_inventory(callback: CallbackQuery, inventory_id: int, confirmed_real: bool) -> None:
        try:
            await inventory_service.mark_sold(inventory_id, confirmed_real=confirmed_real)
        except RealTradingDisabledError as exc:
            await callback.answer("REAL операция не выполнена", show_alert=True)
            if callback.message is not None:
                await callback.message.answer(str(exc))
            return
        except Exception as exc:
            await callback.answer("Ошибка", show_alert=True)
            if callback.message is not None:
                await callback.message.answer(f"Не удалось отметить продажу: {exc}")
            return
        await callback.answer("Продано")
        await _delete_callback_message(callback)

    return router


async def _delete_callback_message(callback: CallbackQuery) -> None:
    if callback.message is not None:
        with suppress(Exception):
            await callback.message.delete()


def _callback_id(data: str | None) -> int:
    if not data or ":" not in data:
        raise ValueError("Callback id not found")
    return int(data.rsplit(":", 1)[1])
