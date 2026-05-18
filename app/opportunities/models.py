from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ArbitrageOpportunity(BaseModel):
    id: str
    item_name: str
    normalized_name: str
    buy_market: str
    sell_market: str
    buy_listing_id: str
    buy_price_rub: Decimal
    buy_price_usd: Decimal | None = None
    expected_sell_price_rub: Decimal
    expected_sell_price_usd: Decimal | None = None
    total_fees_rub: Decimal
    payment_fees_rub: Decimal
    currency_conversion_fees_rub: Decimal
    expected_net_profit_rub: Decimal
    expected_net_profit_usd: Decimal | None = None
    roi_percent: Decimal
    liquidity_score: int
    risk_score: int
    confidence_score: int
    reason: str
    detected_at: datetime
    expires_at: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)

