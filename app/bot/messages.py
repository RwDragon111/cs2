from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.config import Settings
from app.db.models import DealORM, DemoAccountORM, InventoryORM, ScanLogORM
from app.markets.types import MarketBalance
from app.services.inventory import DemoStats
from app.services.scanner import ScannerStatus
from app.utils.market_links import deal_links_text
from app.utils.money import format_percent, format_rub
from app.utils.time import ensure_aware, utc_now


def mode_label(mode: str) -> str:
    return "DEMO 🧪" if mode == "DEMO" else "REAL ⚠️"


def format_deal(deal: DealORM, mode: str) -> str:
    details = deal.details or {}
    liquidity = details.get("liquidity", {})
    price = details.get("price_analysis", {})
    fees = details.get("fees", {})
    warning = price.get("warning")
    lines = [
        "🔥 Найдена потенциальная сделка",
        "",
        f"Режим: {mode_label(mode)}",
        "",
        f"Скин: {deal.item_name}",
        f"DMarket цена покупки: {format_rub(deal.dmarket_price)}",
        f"CSGO Market buy order: {format_rub(deal.csgo_buy_order_price)}",
        "",
        "Комиссии:",
        f"- покупка: {fees.get('buy_fee', '0')} ₽ / {fees.get('dmarket_fee_percent', '0')}%",
        f"- продажа: {fees.get('csgo_market_fee_percent', '0')}%",
        f"- вывод: {fees.get('withdrawal_fee_percent', '0')}%",
        "",
        f"Чистая прибыль: {format_rub(deal.profit)}",
        f"ROI: {format_percent(deal.roi)}",
        "",
        f"Ликвидность: {deal.liquidity_score}/100",
        f"Продаж за 7 дней: {liquidity.get('sales_7d', 0)}",
        f"Spread: {liquidity.get('spread_percent', '0')}%",
        "",
        "Анализ цены:",
        f"Средняя цена 7д: {_maybe_money(price.get('avg_7d_price'))}",
        f"Средняя цена 30д: {_maybe_money(price.get('avg_30d_price'))}",
        f"Отклонение: {price.get('price_spike_percent', '0')}%",
        f"Риск: {price.get('risk_label', 'неизвестно')}",
        "",
        f"Trade lock: {details.get('trade_lock_days', 8)} дней после покупки",
    ]
    if warning:
        lines.extend(["", str(warning)])
    return "\n".join(lines)


def format_deal_details(deal: DealORM, mode: str) -> str:
    details = deal.details or {}
    notes = details.get("liquidity", {}).get("notes", [])
    lines = [
        format_deal(deal, mode),
        "",
        "Технические детали:",
        f"ID сделки: {deal.id}",
        f"DMarket listing: {deal.dmarket_listing_id}",
        f"Цена с комиссиями покупки: {format_rub(deal.buy_price_with_fees)}",
        f"Цена после комиссий продажи: {format_rub(deal.sell_price_after_fees)}",
        f"Risk score: {deal.risk_score}/100",
        f"Статус: {deal.status}",
        "",
        deal_links_text(deal.item_name),
    ]
    if notes:
        lines.append("")
        lines.append("Заметки по ликвидности:")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def format_deals_list(deals: list[DealORM], mode: str, title: str = "Найденные сделки") -> str:
    if not deals:
        return "Подходящих сделок пока нет."
    lines = [title, "", f"Режим: {mode_label(mode)}", f"Всего в списке: {len(deals)}", ""]
    for index, deal in enumerate(deals, start=1):
        lines.extend(
            [
                f"{index}. {deal.item_name}",
                f"ID: {deal.id}",
                f"DMarket: {format_rub(deal.dmarket_price)}",
                f"CSGO buy order: {format_rub(deal.csgo_buy_order_price)}",
                f"Прибыль: {format_rub(deal.profit)} | ROI: {format_percent(deal.roi)}",
                f"Ликвидность: {deal.liquidity_score}/100 | Риск: {deal.risk_score}/100",
                f"Карточка с кнопками: /deal {deal.id}",
                "------------------------------",
            ]
        )
    if lines[-1] == "------------------------------":
        lines.pop()
    return "\n".join(lines)


def format_status(status: ScannerStatus, latest_log: ScanLogORM | None) -> str:
    uptime = utc_now() - status.started_at
    lines = [
        "Статус скрипта",
        "",
        f"Сканер: {'пауза' if status.is_paused else 'работает' if status.is_running else 'остановлен'}",
        f"Последнее сканирование: {_fmt_dt(status.last_scan_finished_at)}",
        f"Найдено за последний скан: {status.last_found_deals_count}",
        f"Найдено за запуск: {status.total_found_deals_count}",
        f"Uptime: {str(uptime).split('.')[0]}",
    ]
    if latest_log is not None:
        lines.append(f"Последний лог: #{latest_log.id}, сделок {latest_log.found_deals_count}")
    if status.last_error:
        lines.append(f"Последняя ошибка: {status.last_error}")
    if status.api_errors:
        lines.append(f"Ошибки API: {len(status.api_errors)}")
    return "\n".join(lines)


def format_demo_balance(account: DemoAccountORM, inventory: list[InventoryORM]) -> str:
    active = [item for item in inventory if item.status != "sold"]
    in_items = sum((Decimal(item.buy_price) for item in active), Decimal("0"))
    expected_profit = sum((Decimal(item.expected_profit or 0) for item in active), Decimal("0"))
    realized_profit = sum((Decimal(item.actual_profit or 0) for item in inventory if item.status == "sold"), Decimal("0"))
    return "\n".join(
        [
            "Баланс",
            "",
            "Режим: DEMO 🧪",
            f"Текущий демо-баланс: {format_rub(account.balance)}",
            f"В виртуальных скинах: {format_rub(in_items)}",
            f"Ожидаемая прибыль: {format_rub(expected_profit)}",
            f"Активных демо-сделок: {len(active)}",
            f"Общий виртуальный PnL: {format_rub(realized_profit)}",
        ]
    )


def format_real_balance(dmarket: MarketBalance, csgo: MarketBalance, active_items: list[InventoryORM]) -> str:
    active_value = sum((Decimal(item.buy_price) for item in active_items if item.status != "sold"), Decimal("0"))
    return "\n".join(
        [
            "Баланс",
            "",
            "Режим: REAL ⚠️",
            f"DMarket: {format_rub(dmarket.available)}",
            f"CSGO Market: {format_rub(csgo.available)}",
            f"Средства в активных сделках: {format_rub(active_value)}",
            "",
            "⚠️ Используется реальный режим. Любое действие требует ручного подтверждения.",
        ]
    )


def format_inventory(items: list[InventoryORM], title: str = "Inventory") -> str:
    if not items:
        return f"{title}\n\nПусто."
    lines = [title, "", f"Всего в списке: {len(items)}", ""]
    now = utc_now()
    for index, item in enumerate(items, start=1):
        trade_lock_until = ensure_aware(item.trade_lock_until)
        left = trade_lock_until - now
        left_days = max(0, left.days)
        lock_text = "готов к продаже" if trade_lock_until <= now else f"осталось {left_days} дн."
        tag = "DEMO" if item.is_demo else "REAL"
        lines.extend(
            [
                f"{index}. {item.item_name}",
                f"ID: {item.id} | Режим: {tag} | Статус: {item.status}",
                f"Покупка: {format_rub(item.buy_price)}",
                f"Ожидаемая продажа: {format_rub(item.expected_sell_price)}",
                f"Ожидаемая прибыль: {format_rub(item.expected_profit or 0)} | ROI: {format_percent(item.expected_roi or 0)}",
                f"Trade lock: {lock_text}",
                f"Куплен: {_fmt_dt(ensure_aware(item.bought_at))}",
                "------------------------------",
            ]
        )
    if lines[-1] == "------------------------------":
        lines.pop()
    return "\n".join(lines)


def format_settings(settings: Settings, mode: str) -> str:
    return "\n".join(
        [
            "Настройки фильтров",
            "",
            f"Режим: {mode_label(mode)}",
            f"MIN_PROFIT_ABSOLUTE={settings.min_profit_absolute}",
            f"MIN_PROFIT_PERCENT={settings.min_profit_percent}",
            f"MIN_ITEM_PRICE={settings.min_item_price}",
            f"MAX_ITEM_PRICE={settings.max_item_price}",
            f"MIN_LIQUIDITY_SCORE={settings.min_liquidity_score}",
            f"MAX_PRICE_SPIKE_PERCENT={settings.max_price_spike_percent}",
            f"PRICE_HISTORY_DAYS={settings.price_history_days}",
            f"SCAN_INTERVAL_SECONDS={settings.scan_interval_seconds}",
            f"RUB_USD_RATE_SOURCE={settings.rub_usd_rate_source}",
            f"DMARKET_DYNAMIC_TITLE_LIMIT={settings.dmarket_dynamic_title_limit}",
            f"DMARKET_EXTRA_TITLES={len(settings.dmarket_extra_title_list)}",
            f"DMARKET_FEE_PERCENT={settings.dmarket_fee_percent}",
            f"CSGO_MARKET_FEE_PERCENT={settings.csgo_market_fee_percent}",
            f"WITHDRAWAL_FEE_PERCENT={settings.withdrawal_fee_percent}",
            f"ALLOW_REAL_TRADING={settings.allow_real_trading}",
            "",
            "Изменить настройку: /set MIN_PROFIT_PERCENT 2",
            "Список изменяемых настроек: /settings_help",
            "Пересканировать заново: /rescan",
            "Проверить курс: /rate",
        ]
    )


def format_help() -> str:
    return "\n".join(
        [
            "Команды бота:",
            "/start - главное меню",
            "/status - статус сканера",
            "/balance - баланс по текущему режиму",
            "/deals - найденные сделки",
            "/best - топ по ROI и прибыли",
            "/inventory - купленные скины",
            "/locked - предметы в trade lock",
            "/ready - готовые к продаже",
            "/settings - текущие фильтры",
            "/settings_help - список настроек, которые можно менять из бота",
            "/set MIN_PROFIT_PERCENT 2 - изменить настройку",
            "/rescan - пересканировать рынок и показать подходящие сделки заново",
            "/deal 123 - открыть карточку сделки с кнопками",
            "/rate - текущий курс USD/RUB от ЦБР",
            "/watch <название или URL> - добавить item в точный DMarket-поиск",
            "/watchlist - список предметов в точном DMarket-поиске",
            "/scan_item <название или URL> - проверить item сразу",
            "/pause - остановить сканирование",
            "/resume - возобновить сканирование",
            "/mode - текущий режим",
            "/demo_on - включить DEMO",
            "/demo_off - включить REAL, если разрешено",
            "/demo_balance - демо-баланс",
            "/demo_set_balance 100000 - установить демо-баланс",
            "/demo_reset - сбросить демо-счет",
            "/demo_stats - статистика DEMO",
            "/help - эта справка",
        ]
    )


def format_demo_stats(stats: DemoStats) -> str:
    best = f"#{stats.best_deal.id} {stats.best_deal.item_name}: {format_rub(stats.best_deal.actual_profit)}" if stats.best_deal else "нет"
    worst = f"#{stats.worst_deal.id} {stats.worst_deal.item_name}: {format_rub(stats.worst_deal.actual_profit)}" if stats.worst_deal else "нет"
    return "\n".join(
        [
            "DEMO статистика",
            "",
            f"Стартовый баланс: {format_rub(stats.initial_balance)}",
            f"Текущий баланс: {format_rub(stats.current_balance)}",
            f"Виртуальных покупок: {stats.virtual_buys}",
            f"Виртуальных продаж: {stats.virtual_sells}",
            f"Активных сделок: {stats.active_deals}",
            f"Суммарная прибыль: {format_rub(stats.total_profit)}",
            f"Средний ROI: {format_percent(stats.average_roi)}",
            f"Лучшая сделка: {best}",
            f"Худшая сделка: {worst}",
            f"Win rate: {format_percent(stats.win_rate)}",
        ]
    )


def _maybe_money(value: object) -> str:
    if value in {None, ""}:
        return "нет данных"
    return format_rub(Decimal(str(value)))


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "еще не было"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")
