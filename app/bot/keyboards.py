from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def deal_keyboard(deal: int | Any) -> InlineKeyboardMarkup:
    deal_id = int(deal if isinstance(deal, int) else getattr(deal, "id"))
    details = {} if isinstance(deal, int) else (getattr(deal, "details", {}) or {})
    links = details.get("links", {})
    buy_market = (details.get("markets", {}) or {}).get("buy_market") or "Buy market"

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
    link_row: list[InlineKeyboardButton] = []
    if links.get("buy_market"):
        link_row.append(InlineKeyboardButton(text=buy_market, url=str(links["buy_market"])))
    if links.get("csgo_market"):
        link_row.append(InlineKeyboardButton(text="CSGO Market", url=str(links["csgo_market"])))
    if link_row:
        rows.append(link_row)
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
