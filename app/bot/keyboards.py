from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def deal_keyboard(deal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подробнее", callback_data=f"deal_details:{deal_id}"),
                InlineKeyboardButton(text="Отметить как куплено", callback_data=f"deal_buy:{deal_id}"),
            ],
            [
                InlineKeyboardButton(text="Добавить в наблюдение", callback_data=f"deal_watch:{deal_id}"),
                InlineKeyboardButton(text="Скрыть сделку", callback_data=f"deal_hide:{deal_id}"),
            ],
            [InlineKeyboardButton(text="Обновить", callback_data="refresh_deals")],
        ]
    )


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
