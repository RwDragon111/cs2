from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.item_titles import split_configured_titles


class Settings(BaseSettings):
    app_env: str = "production"
    database_url: str = "sqlite:///data/cs2_arbitrage.db"

    telegram_enabled: bool = True
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    authorized_telegram_id: int = 0

    use_mock_markets: bool = False
    market_csgo_api_key: str = ""
    csgo_market_api_key: str = ""
    dmarket_api_key: str = ""
    dmarket_api_secret: str = ""
    dmarket_public_key: str = ""
    dmarket_secret_key: str = ""

    enable_market_csgo: bool = True
    enable_dmarket: bool = True
    enable_third_market: bool = False
    enable_dmarket_stats: bool = False

    trading_mode: Literal[
        "SIGNAL_ONLY",
        "PAPER_TRADING",
        "MANUAL_APPROVAL",
        "AUTO_BUY_LIMITED",
        "AUTO_BUY_AND_SELL",
    ] = "PAPER_TRADING"
    default_trading_mode: Literal["DEMO", "REAL"] = "DEMO"
    allow_real_trading: bool = False

    paper_trading_enabled: bool = True
    paper_trading_initial_balance_rub: Decimal = Decimal("10000")
    paper_trading_initial_balance_usd: Decimal = Decimal("20")
    paper_trading_allow_negative_balance: bool = False
    paper_trading_reset_on_start: bool = False
    paper_trading_trade_ban_days: int = 7
    paper_trading_sell_mode: Literal["MANUAL_SELL", "AFTER_TRADE_BAN", "TARGET_PRICE", "TIME_LIMIT"] = "MANUAL_SELL"
    paper_trading_use_real_market_price_on_sell: bool = True

    base_currency: str = "RUB"
    secondary_currency: str = "USD"
    rub_usd_rate_source: str = "manual"
    manual_rub_usd_rate: Decimal = Decimal("100")

    min_profit_rub: Decimal = Decimal("100")
    min_profit_usd: Decimal = Decimal("1.00")
    min_roi_percent: Decimal = Decimal("5.0")
    min_profit_percent: Decimal = Decimal("5")
    min_profit_absolute: Decimal = Decimal("100")
    min_item_price: Decimal = Decimal("300")
    max_item_price: Decimal = Decimal("50000")
    max_buy_price_rub: Decimal = Decimal("10000")
    max_buy_price_usd: Decimal = Decimal("100")
    max_daily_spend_rub: Decimal = Decimal("10000")
    max_open_positions: int = 10

    risk_buffer_percent: Decimal = Decimal("2.0")
    currency_spread_percent: Decimal = Decimal("1.0")
    max_allowed_currency_spread_percent: Decimal = Decimal("2.0")
    min_liquidity_score: int = 60
    max_price_spike_percent: Decimal = Decimal("25")
    price_history_days: int = 30
    trade_lock_days: int = 8
    dmarket_fee_percent: Decimal = Decimal("0")
    csgo_market_fee_percent: Decimal = Decimal("5")
    withdrawal_fee_percent: Decimal = Decimal("0")
    demo_initial_balance: Decimal = Decimal("100000")
    demo_currency: str = "RUB"

    allow_markets_with_crypto_only: bool = True
    max_payment_conversion_fee_percent: Decimal = Decimal("2.0")
    max_deposit_fee_percent: Decimal = Decimal("2.0")
    max_withdrawal_fee_percent: Decimal = Decimal("3.0")

    excluded_markets: str = "CS.MONEY,csmoney,cs.money,White.Market,white.market"
    optional_market_candidates: str = "Waxpeer,BitSkins,Skinport,CSFloat"

    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    market_poll_interval_seconds: int = 30
    opportunity_scan_interval_seconds: int = 35
    scan_interval_seconds: int = 300
    paper_position_check_interval_seconds: int = 300
    sales_history_interval_seconds: int = 900

    market_csgo_base_url: str = "https://market.csgo.com"
    dmarket_api_base_url: str = "https://api.dmarket.com"
    dmarket_items_endpoint: str = "/exchange/v1/market/items"
    csgo_market_buy_orders_endpoint: str = "/api/v2/prices/orders/RUB.json"
    csgo_market_balance_endpoint: str = "/api/v2/get-money"
    dmarket_stats_limit: int = 100
    dmarket_stats_currency: str = "USD"
    dmarket_market_pages: int = 3
    dmarket_title_query_limit: int = 3
    dmarket_search_concurrency: int = 2
    dmarket_title_search_delay_seconds: float = 0.25
    dmarket_dynamic_title_limit: int = 160
    dmarket_extra_titles: str = ""
    market_csgo_buy_order_min_price_rub: Decimal = Decimal("100")
    market_csgo_buy_order_max_price_rub: Decimal = Decimal("20000")
    market_csgo_buy_order_min_volume: int = 1
    dmarket_stats_titles: str = (
        "AWP | Asiimov (Field-Tested),"
        "AK-47 | Redline (Field-Tested),"
        "M4A1-S | Printstream (Minimal Wear),"
        "Desert Eagle | Printstream (Field-Tested),"
        "USP-S | Kill Confirmed (Field-Tested)"
    )
    enable_stats_spread_signals: bool = False
    min_stats_spread_percent: Decimal = Decimal("8.0")
    min_stats_absolute_spread_rub: Decimal = Decimal("100")
    max_stats_signals_per_scan: int = 5
    request_timeout_seconds: float = 20.0
    max_api_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("base_currency", "secondary_currency", mode="before")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return str(value).upper()

    @field_validator("dmarket_stats_currency", mode="before")
    @classmethod
    def uppercase_dmarket_currency(cls, value: str) -> str:
        return str(value).upper()

    @field_validator("trading_mode", mode="before")
    @classmethod
    def uppercase_mode(cls, value: str) -> str:
        return str(value).upper()

    @field_validator("default_trading_mode", mode="before")
    @classmethod
    def uppercase_default_mode(cls, value: str) -> str:
        return str(value).upper()

    @field_validator("authorized_telegram_id", mode="before")
    @classmethod
    def parse_authorized_telegram_id(cls, value: object) -> int:
        if value in {None, ""}:
            return 0
        return int(value)

    @field_validator("demo_currency", mode="before")
    @classmethod
    def uppercase_demo_currency(cls, value: str) -> str:
        return str(value).upper()

    @property
    def excluded_market_names(self) -> set[str]:
        return {item.strip().lower() for item in self.excluded_markets.split(",") if item.strip()}

    @property
    def optional_market_names(self) -> set[str]:
        return {item.strip() for item in self.optional_market_candidates.split(",") if item.strip()}

    @property
    def dmarket_tracked_titles(self) -> list[str]:
        return [item.strip() for item in self.dmarket_stats_titles.split(",") if item.strip()]

    @property
    def dmarket_extra_title_list(self) -> list[str]:
        return split_configured_titles(self.dmarket_extra_titles)

    @property
    def telegram_ready(self) -> bool:
        return self.telegram_enabled and bool(self.telegram_bot_token and self.authorized_telegram_id)

    @property
    def dmarket_public_or_api_key(self) -> str:
        return self.dmarket_api_key or self.dmarket_public_key

    @property
    def dmarket_secret_or_legacy_key(self) -> str:
        return self.dmarket_api_secret or self.dmarket_secret_key

    @property
    def csgo_market_key(self) -> str:
        return self.csgo_market_api_key or self.market_csgo_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
