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
from app.currency.rate_provider import CurrencyRateProvider
from app.db.repositories import DealRepository, InventoryRepository, ScanLogRepository, SettingsRepository, TradingStateRepository
from app.markets.csgo_market_client import CSGOMarketClient
from app.markets.dmarket_client import DMarketClient
from app.services.inventory import InventoryService
from app.services.runtime_settings import format_editable_settings_help, set_runtime_setting
from app.services.scanner import ArbitrageScanner
from app.utils.item_titles import extract_title_from_text, join_configured_titles, split_configured_titles


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
        ("deal", "Карточка сделки"),
        ("rate", "Курс USD/RUB ЦБР"),
        ("watch", "Точный DMarket-поиск"),
        ("watchlist", "Список точного поиска"),
        ("scan_item", "Проверить item/URL"),
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
    settings_repo: SettingsRepository,
    inventory_service: InventoryService,
    dmarket: DMarketClient,
    csgo_market: CSGOMarketClient,
) -> Router:
    router = Router()
    router.message.middleware(TelegramAuthMiddleware(settings.authorized_telegram_id))
    router.callback_query.middleware(TelegramAuthMiddleware(settings.authorized_telegram_id))

    async def send_deal_list(message: Message, rows, title: str = "Найденные сделки") -> None:
        await message.answer(format_deals_list(rows, trading.get_mode(), title=title), reply_markup=refresh_keyboard("deals"))

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        mode = trading.get_mode()
        await message.answer(
            "CS2 Arbitrage Bot запущен.\n\n"
            "Маршрут анализа: купить на DMarket и продать в существующий buy order на CSGO Market.\n"
            f"Текущий режим: {mode_label(mode)}\n\n"
            "По умолчанию реальные операции не выполняются. Используй /help, чтобы открыть список команд.",
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
        dmarket_balance, csgo_balance = await asyncio.gather(dmarket.get_balance(), csgo_market.get_balance())
        await message.answer(format_real_balance(dmarket_balance, csgo_balance, inventory.list(is_demo=False, limit=10000)))

    @router.message(Command("deals"))
    async def deal_list(message: Message) -> None:
        rows = deals.latest(limit=12)
        if not rows:
            await message.answer("Подходящих сделок пока нет.", reply_markup=refresh_keyboard("deals"))
            return
        await send_deal_list(message, rows)

    @router.message(Command("best"))
    async def best(message: Message) -> None:
        await send_deal_list(message, deals.best(limit=12), title="Топ сделок")

    @router.message(Command("deal"))
    async def deal_card(message: Message) -> None:
        raw_id = _command_argument(message.text)
        if not raw_id:
            await message.answer("Использование: /deal 123")
            return
        try:
            deal_id = int(raw_id)
        except ValueError:
            await message.answer("ID сделки должен быть числом. Пример: /deal 123")
            return
        row = deals.get(deal_id)
        if row is None:
            await message.answer("Сделка не найдена.")
            return
        await message.answer(format_deal(row, trading.get_mode()), reply_markup=deal_keyboard(row.id, row.item_name))

    @router.message(Command("rescan"))
    async def rescan(message: Message) -> None:
        await message.answer("Запускаю перескан. Старые подходящие сделки тоже попадут в результат, если снова проходят фильтры.")
        rows = await scanner.scan_once(notify=False, include_existing=True)
        if not rows:
            await message.answer("Подходящих сделок по текущим фильтрам не найдено.", reply_markup=refresh_keyboard("deals"))
            return
        await send_deal_list(message, rows[:12], title="Результат перескана")

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
        await message.answer(format_settings(settings, trading.get_mode()))

    @router.message(Command("settings_help"))
    async def settings_help(message: Message) -> None:
        await message.answer(format_editable_settings_help())

    @router.message(Command("set"))
    async def set_setting(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) != 3:
            await message.answer("Использование: /set MIN_PROFIT_PERCENT 2\nСписок настроек: /settings_help")
            return
        try:
            spec, value = set_runtime_setting(settings, settings_repo, parts[1], parts[2])
        except ValueError as exc:
            await message.answer(f"Не удалось изменить настройку: {exc}\nСписок настроек: /settings_help")
            return
        await message.answer(
            f"Настройка сохранена: {spec.key}={value}\n"
            "Она уже применяется в текущем процессе. Чтобы заново показать подходящие старые и новые сделки, нажми /rescan."
        )

    @router.message(Command("rate"))
    async def rate(message: Message) -> None:
        try:
            exchange_rate = await CurrencyRateProvider(settings).get_usd_to_rub()
        except Exception as exc:
            await message.answer(f"Не удалось получить курс ЦБР: {exc}")
            return
        lines = [
            "Курс USD/RUB",
            "",
            f"Источник: {exchange_rate.source}",
            f"Курс: {exchange_rate.value} ₽ за 1 USD",
            f"Дата курса: {exchange_rate.effective_date or 'не указана'}",
            f"Кеш: {settings.currency_rate_cache_ttl_seconds} сек.",
        ]
        if settings.currency_rate_fallback_to_manual:
            lines.extend(["", "Внимание: включен fallback на manual rate, если ЦБР недоступен."])
        await message.answer("\n".join(lines))

    @router.message(Command("watch"))
    async def watch_command(message: Message) -> None:
        title = _command_argument(message.text)
        if not title:
            await message.answer(
                "Использование: /watch Kukri Knife | Blue Steel (Battle-Scarred)\n"
                "Можно вставить ссылку DMarket или CSGO Market."
            )
            return
        clean_title = extract_title_from_text(title)
        current_titles = _watched_titles(settings_repo)
        settings_repo.set("dmarket_watch_titles", join_configured_titles([*current_titles, clean_title]))
        rows = await scanner.scan_once(notify=False, extra_titles=[clean_title], include_existing=True)
        if rows:
            await message.answer(f"Добавил в наблюдение и нашёл подходящих сделок: {len(rows)}")
            await send_deal_list(message, rows[:12], title=f"Сделки по {clean_title}")
            return
        existing = deals.search(clean_title, limit=5)
        if existing:
            await message.answer(f"Добавил в наблюдение. Уже найденные сделки по этому предмету: {len(existing)}")
            await send_deal_list(message, existing, title=f"Сделки по {clean_title}")
            return
        await message.answer(
            f"Добавил в наблюдение: {clean_title}\n"
            "Сделка появится в /deals, когда пройдёт фильтры прибыли, ликвидности и комиссий."
        )

    @router.message(Command("watchlist"))
    async def watchlist_command(message: Message) -> None:
        titles = [*settings.dmarket_extra_title_list, *_watched_titles(settings_repo)]
        if not titles:
            await message.answer("Список точного DMarket-поиска пуст. Добавь предмет командой /watch <название или URL>.")
            return
        lines = ["Точный DMarket-поиск:", "", *[f"{index}. {title}" for index, title in enumerate(titles, start=1)]]
        await message.answer("\n".join(lines))

    @router.message(Command("scan_item"))
    async def scan_item_command(message: Message) -> None:
        title = _command_argument(message.text)
        if not title:
            await message.answer(
                "Использование: /scan_item Kukri Knife | Blue Steel (Battle-Scarred)\n"
                "Можно вставить ссылку DMarket или CSGO Market."
            )
            return
        clean_title = extract_title_from_text(title)
        rows = await scanner.scan_once(notify=False, extra_titles=[clean_title], include_existing=True)
        if not rows:
            existing = deals.search(clean_title, limit=5)
            if existing:
                await message.answer(f"Новых сделок не создано, но в базе уже есть подходящие сделки: {len(existing)}")
                await send_deal_list(message, existing, title=f"Сделки по {clean_title}")
                return
            await message.answer(
                f"Проверил: {clean_title}\n"
                "Новых сделок не создано. Если предмет уже был найден раньше, посмотри /deals или /best."
            )
            return
        await send_deal_list(message, rows[:12], title=f"Проверка {clean_title}")

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
                "REAL-режим отключен в настройках сервера. Измени ALLOW_REAL_TRADING=true в .env, если хочешь разрешить реальные операции."
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
            await callback.message.answer(
                format_deals_list(rows[:12], trading.get_mode(), title="Результат перескана"),
                reply_markup=refresh_keyboard("deals"),
            )

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
            item = await inventory_service.mark_deal_bought(deal_id, confirmed_real=confirmed_real)
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
            item = await inventory_service.mark_sold(inventory_id, confirmed_real=confirmed_real)
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


def _callback_id(data: str | None) -> int:
    if not data or ":" not in data:
        raise ValueError("Callback id not found")
    return int(data.rsplit(":", 1)[1])


def _command_argument(text: str | None) -> str:
    parts = (text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def _watched_titles(settings_repo: SettingsRepository) -> list[str]:
    return split_configured_titles(settings_repo.get("dmarket_watch_titles", ""))


async def _delete_callback_message(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    with suppress(Exception):
        await callback.message.delete()
