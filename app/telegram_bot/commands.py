from __future__ import annotations


BOT_COMMANDS: list[tuple[str, str]] = [
    ("start", "Запуск и краткое описание режима MVP"),
    ("status", "Общий статус бота и Paper Trading"),
    ("balance", "Текущий paper-баланс"),
    ("opportunities", "Активные сигналы DMarket -> Market.CSGO buy orders"),
    ("last", "Последние найденные возможности"),
    ("settings", "Ключевые настройки режима работы"),
    ("blacklist", "Статус blacklist и запрещенных рынков"),
    ("pnl", "Сводка прибыли и убытка"),
    ("positions", "Все paper-позиции"),
    ("pause", "Пауза фоновых задач, зарезервировано"),
    ("resume", "Возобновление задач, зарезервировано"),
    ("payment_status", "Подключенные рынки и платежные профили"),
    ("markets", "Текущая рабочая рыночная схема"),
    ("dmarket_stats", "Последние реальные офферы DMarket"),
    ("market_spreads", "Диагностика spread DMarket vs Market.CSGO buy orders"),
    ("paper_status", "Полный статус Paper Trading"),
    ("paper_balance", "Баланс виртуального счета"),
    ("paper_positions", "Список виртуальных позиций"),
    ("paper_open", "Открытые paper-позиции"),
    ("paper_ready", "Позиции, готовые к Paper Sell"),
    ("paper_sold", "Проданные paper-позиции"),
    ("paper_pnl", "Paper Trading PnL аналитика"),
    ("paper_reset", "Сброс paper-счета, зарезервировано"),
    ("paper_settings", "Настройки Paper Trading"),
    ("paper_buy", "Paper Buy по ID opportunity"),
    ("paper_sell", "Paper Sell по ID позиции"),
    ("help", "Показать список команд"),
]


def commands_help_text() -> str:
    lines = ["Команды бота:"]
    for command, description in BOT_COMMANDS:
        lines.append(f"/{command} - {description}")
    return "\n".join(lines)


def build_bot_commands():
    from aiogram.types import BotCommand

    return [BotCommand(command=command, description=description) for command, description in BOT_COMMANDS]
