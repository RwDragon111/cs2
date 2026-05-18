from __future__ import annotations

from app.opportunities.models import ArbitrageOpportunity


def opportunity_keyboard(opportunity: ArbitrageOpportunity):
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Paper Buy", callback_data=f"paper_buy:{opportunity.id}"),
                InlineKeyboardButton(text="Skip", callback_data=f"skip:{opportunity.id}"),
            ],
            [
                InlineKeyboardButton(text="Show details", callback_data=f"details:{opportunity.id}"),
                InlineKeyboardButton(text="Blacklist item", callback_data=f"blacklist_item:{opportunity.normalized_name[:40]}"),
            ],
            [
                InlineKeyboardButton(
                    text="Blacklist market pair",
                    callback_data=f"blacklist_pair:{opportunity.buy_market}>{opportunity.sell_market}",
                )
            ],
        ]
    )


def paper_sell_keyboard(position_id: str):
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Paper Sell", callback_data=f"paper_sell:{position_id}")],
        ]
    )

