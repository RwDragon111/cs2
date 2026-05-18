from __future__ import annotations

from decimal import Decimal

from app.markets.base import MarketFees


DEFAULT_FEES: dict[str, MarketFees] = {
    "Market.CSGO": MarketFees(
        market_name="Market.CSGO",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("1.5"),
        withdrawal_fee_percent=Decimal("2.0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
    "LIS-SKINS": MarketFees(
        market_name="LIS-SKINS",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("1.0"),
        withdrawal_fee_percent=Decimal("2.0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
    "Mock.LIS-SKINS": MarketFees(
        market_name="Mock.LIS-SKINS",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("1.0"),
        withdrawal_fee_percent=Decimal("2.0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
    "Mock.Market.CSGO": MarketFees(
        market_name="Mock.Market.CSGO",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("1.5"),
        withdrawal_fee_percent=Decimal("2.0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
}


def get_default_fees(market_name: str) -> MarketFees:
    return DEFAULT_FEES.get(market_name, MarketFees(market_name=market_name))

