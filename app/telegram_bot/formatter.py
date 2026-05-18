from __future__ import annotations

from app.db.models import PaperPositionORM
from app.opportunities.models import ArbitrageOpportunity
from app.paper_trading.paper_pnl import PaperAnalytics
from app.utils.money import format_percent, format_rub, format_usd


def format_opportunity(opportunity: ArbitrageOpportunity) -> str:
    return (
        "Найдена арбитражная возможность\n\n"
        f"Предмет: {opportunity.item_name}\n\n"
        "Купить:\n"
        f"Маркет: {opportunity.buy_market}\n"
        f"Цена: {format_rub(opportunity.buy_price_rub)}\n"
        f"Цена в USD: {format_usd(opportunity.buy_price_usd)}\n\n"
        "Продать:\n"
        f"Маркет: {opportunity.sell_market}\n"
        f"Ожидаемая цена: {format_rub(opportunity.expected_sell_price_rub)}\n"
        f"Цена в USD: {format_usd(opportunity.expected_sell_price_usd)}\n\n"
        "Расчёт:\n"
        f"Комиссии всего: {format_rub(opportunity.total_fees_rub)}\n"
        f"Комиссии пополнения/вывода: {format_rub(opportunity.payment_fees_rub)}\n"
        f"Конвертация валют: {format_rub(opportunity.currency_conversion_fees_rub)}\n\n"
        f"Ожидаемая чистая прибыль: {format_rub(opportunity.expected_net_profit_rub)}\n"
        f"ROI: {format_percent(opportunity.roi_percent)}\n\n"
        f"Ликвидность: {opportunity.liquidity_score}/100\n"
        f"Риск: {opportunity.risk_score}/100\n"
        f"Уверенность: {opportunity.confidence_score}/100\n\n"
        "Режим: PAPER_TRADING\n"
        "Рекомендация: тестовая покупка"
    )


def format_paper_buy(position: PaperPositionORM, balance_rub) -> str:
    return (
        "Paper Buy выполнен\n\n"
        f"Предмет: {position.item_name}\n"
        f"Маркет покупки: {position.buy_market}\n"
        f"Виртуальная цена покупки: {format_rub(position.buy_price_rub)}\n"
        f"Комиссии: {format_rub(position.buy_fees_rub)}\n"
        f"Итого списано: {format_rub(position.total_cost_rub)}\n\n"
        f"Остаток paper balance: {format_rub(balance_rub)}\n\n"
        f"Trade ban до: {position.trade_ban_until:%Y-%m-%d %H:%M}\n"
        "Продажа будет доступна через: 7 дней\n\n"
        "Режим: PAPER_TRADING\n"
        "Реальная покупка НЕ выполнялась."
    )


def format_paper_sell(position: PaperPositionORM, balance_rub) -> str:
    sell_price = position.virtual_sell_price_rub or 0
    profit = position.actual_profit_rub or 0
    roi = position.actual_roi_percent or 0
    return (
        "Paper Sell выполнен\n\n"
        f"Предмет: {position.item_name}\n"
        f"Маркет продажи: {position.target_sell_market}\n\n"
        "Покупка:\n"
        f"Цена покупки: {format_rub(position.buy_price_rub)}\n"
        f"Комиссии покупки: {format_rub(position.buy_fees_rub)}\n"
        f"Итого cost basis: {format_rub(position.total_cost_rub)}\n\n"
        "Продажа:\n"
        f"Текущая цена продажи: {format_rub(sell_price)}\n\n"
        "Результат:\n"
        f"Фактическая прибыль: {format_rub(profit)}\n"
        f"ROI: {format_percent(roi)}\n\n"
        f"Paper balance: {format_rub(balance_rub)}\n\n"
        "Реальная продажа НЕ выполнялась."
    )


def format_position_ready(position: PaperPositionORM) -> str:
    return (
        "Позиция готова к Paper Sell\n\n"
        f"Предмет: {position.item_name}\n"
        f"Позиция: {position.id}\n"
        f"Целевой маркет: {position.target_sell_market}\n"
        f"Trade ban завершён: {position.trade_ban_until:%Y-%m-%d %H:%M}"
    )


def format_paper_status(analytics: PaperAnalytics) -> str:
    return (
        "Paper Trading Status\n\n"
        f"Стартовый баланс: {format_rub(analytics.initial_balance_rub)}\n"
        f"Текущий баланс: {format_rub(analytics.current_balance_rub)}\n\n"
        f"Открытые позиции: {analytics.open_positions}\n"
        f"В trade lock: {analytics.trade_locked_positions}\n"
        f"Готовы к продаже: {analytics.ready_to_sell_positions}\n"
        f"Продано: {analytics.sold_positions}\n\n"
        f"Realized PnL: {format_rub(analytics.realized_pnl_rub)}\n"
        f"Unrealized PnL: {format_rub(analytics.unrealized_pnl_rub)}\n"
        f"Total PnL: {format_rub(analytics.total_pnl_rub)}\n\n"
        f"Winrate: {format_percent(analytics.winrate_percent)}\n"
        f"Средний ROI: {format_percent(analytics.average_roi_percent)}\n"
        f"Expected vs actual: {format_rub(analytics.expected_vs_actual_rub)}"
    )

