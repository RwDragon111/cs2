from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.bot.messages import format_deals_list, format_settings
from app.config import Settings


def _deal(deal_id: int, name: str):
    return SimpleNamespace(
        id=deal_id,
        item_name=name,
        dmarket_price=Decimal("1000"),
        csgo_buy_order_price=Decimal("1200"),
        profit=Decimal("140"),
        roi=Decimal("14"),
        liquidity_score=82,
        risk_score=12,
    )


def test_deals_list_is_numbered_top_to_bottom_and_readable():
    text = format_deals_list(
        [
            _deal(10, "First Skin (Field-Tested)"),
            _deal(11, "Second Skin (Minimal Wear)"),
        ],
        "DEMO",
    )

    assert text.index("1. First Skin") < text.index("2. Second Skin")
    assert "------------------------------" in text
    assert "Карточка с кнопками: /deal 10" in text
    assert "#10 |" not in text


def test_settings_message_does_not_show_manual_usd_rate():
    text = format_settings(Settings(telegram_enabled=False), "DEMO")

    assert "RUB_USD_RATE_SOURCE=cbr" in text
    assert "MANUAL_RUB_USD_RATE" not in text
