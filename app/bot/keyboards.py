from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.market_links import csgo_market_item_url, dmarket_item_url


def deal_keyboard(deal_id: int, item_name: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Подробнее", callback_data=f"deal_details:{deal_id}"),
            InlineKeyboardButton(text="Отметить как куплено", callback_data=f"deal_buy:{deal_id}"),
        ],
        [
            InlineKeyboardButton(text="Добавить в наблюдение", callback_data=f"deal_watch:{deal_id}"),
            InlineKeyboardButton(text="Скрыть сделку", callback_data=f"deal_hide:{deal_id}"),
        ],
    ]
    if item_name:
        rows.append(
            [
                InlineKeyboardButton(text="DMarket", url=dmarket_item_url(item_name)),
                InlineKeyboardButton(text="CSGO Market", url=csgo_market_item_url(item_name)),
            ]
        )
    rows.append([InlineKeyboardButton(text="Обновить", callback_data="refresh_deals")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inventory_keyboard(inventory_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отметить как продано", callback_data=f"inventory_sell:{inventory_id}")],
            [InlineKeyboardButton(text="Обновить", callback_data="refresh_inventory")],
        ]
    )


def real_confirmation_keyboard(action: str, entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подтвердить REAL", callback_data=f"real_confirm:{action}:{entity_id}"),
                InlineKeyboardButton(text="Отмена", callback_data="real_cancel"),
            ]
        ]
    )


def refresh_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Обновить", callback_data=f"refresh_{target}")]]
    )
