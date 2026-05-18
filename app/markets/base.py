from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import RealTradingDisabledError


class Sticker(BaseModel):
    name: str
    wear: float | None = None
    price_rub: Decimal | None = None


class MarketListing(BaseModel):
    id: str
    market_name: str
    item_name: str
    normalized_name: str
    exterior: str | None = None
    weapon_type: str | None = None
    category: str | None = None
    is_stattrak: bool = False
    is_souvenir: bool = False
    float_value: float | None = None
    paint_seed: int | None = None
    stickers: list[Sticker] | None = None
    price: Decimal
    currency: str
    price_rub: Decimal | None = None
    price_usd: Decimal | None = None
    available: bool = True
    tradable: bool | None = None
    inspect_link: str | None = None
    created_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SaleRecord(BaseModel):
    market_name: str
    normalized_name: str
    price: Decimal
    currency: str
    price_rub: Decimal | None = None
    sold_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class Balance(BaseModel):
    market_name: str
    rub: Decimal = Decimal("0")
    usd: Decimal = Decimal("0")
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MarketFees(BaseModel):
    market_name: str
    buy_fee_percent: Decimal = Decimal("0")
    sell_fee_percent: Decimal = Decimal("5")
    deposit_fee_percent: Decimal = Decimal("0")
    withdrawal_fee_percent: Decimal = Decimal("0")
    currency_conversion_fee_percent: Decimal = Decimal("0")


class BuyResult(BaseModel):
    market_name: str
    listing_id: str
    success: bool
    asset_id: str | None = None
    paid_amount: Decimal | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SellResult(BaseModel):
    market_name: str
    asset_id: str
    success: bool
    sold_amount: Decimal | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class BaseMarketConnector(ABC):
    market_name: str

    def __init__(self, api_key: str = "", timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def fetch_listings(self) -> list[MarketListing]:
        raise NotImplementedError

    async def fetch_item(self, listing_id: str) -> MarketListing | None:
        listings = await self.fetch_listings()
        return next((listing for listing in listings if listing.id == listing_id), None)

    async def fetch_sales_history(self, normalized_name: str) -> list[SaleRecord]:
        return []

    async def get_balance(self) -> Balance:
        return Balance(market_name=self.market_name)

    async def get_fees(self) -> MarketFees:
        return MarketFees(market_name=self.market_name)

    async def buy_item(self, listing_id: str) -> BuyResult:
        raise RealTradingDisabledError("Real buy_item is disabled in MVP")

    async def sell_item(self, asset_id: str, price: Decimal) -> SellResult:
        raise RealTradingDisabledError("Real sell_item is disabled in MVP")

