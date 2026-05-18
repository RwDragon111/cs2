from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.database import Base
from app.utils.time import utc_now


class MarketORM(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MarketPaymentProfileORM(Base):
    __tablename__ = "market_payment_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    supports_rub: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_mir: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_russian_cards: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_yoomoney: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_crypto: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_currency: Mapped[str] = mapped_column(String(10), default="RUB")
    withdrawal_currency: Mapped[str] = mapped_column(String(10), default="RUB")
    deposit_fee_percent: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    withdrawal_fee_percent: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    currency_conversion_required: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_conversion_fee_percent: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)


class MarketListingORM(Base):
    __tablename__ = "market_listings"
    __table_args__ = (UniqueConstraint("market_name", "listing_id", name="uq_market_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(200), nullable=False)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    price_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    tradable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class NormalizedItemORM(Base):
    __tablename__ = "normalized_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weapon_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PriceSnapshotORM(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SalesHistoryORM(Base):
    __tablename__ = "sales_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ArbitrageOpportunityORM(Base):
    __tablename__ = "arbitrage_opportunities"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    buy_market: Mapped[str] = mapped_column(String(100), nullable=False)
    sell_market: Mapped[str] = mapped_column(String(100), nullable=False)
    buy_listing_id: Mapped[str] = mapped_column(String(200), nullable=False)
    buy_price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    buy_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    expected_sell_price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_sell_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_fees_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    payment_fees_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_conversion_fees_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_net_profit_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_net_profit_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    roi_percent: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    liquidity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)


class TelegramEventORM(Base):
    __tablename__ = "telegram_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BlacklistORM(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SettingORM(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MarketBalanceORM(Base):
    __tablename__ = "market_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    balance_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CurrencyRateORM(Base):
    __tablename__ = "currency_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ErrorLogORM(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaperAccountORM(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, default="default")
    initial_balance_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    current_balance_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    initial_balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    current_balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PaperPositionORM(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("buy_market", "source_listing_id", name="uq_paper_source_listing"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    buy_market: Mapped[str] = mapped_column(String(100), nullable=False)
    target_sell_market: Mapped[str] = mapped_column(String(100), nullable=False)
    source_listing_id: Mapped[str] = mapped_column(String(200), nullable=False)
    buy_price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    buy_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    buy_fees_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_cost_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_sell_price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_profit_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_roi_percent: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    bought_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_ban_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    can_sell_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    virtual_sell_price_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    actual_profit_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    actual_roi_percent: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source_opportunity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_listing_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PaperTradeORM(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[str] = mapped_column(ForeignKey("paper_positions.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    price_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fees_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaperBalanceEventORM(Base):
    __tablename__ = "paper_balance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after_rub: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaperSettingORM(Base):
    __tablename__ = "paper_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
