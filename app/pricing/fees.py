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
    "Market.CSGO.BuyOrder": MarketFees(
        market_name="Market.CSGO.BuyOrder",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("0"),
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
    "Mock.Market.CSGO.BuyOrder": MarketFees(
        market_name="Mock.Market.CSGO.BuyOrder",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("2.0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
    "DMarket.Stats": MarketFees(
        market_name="DMarket.Stats",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("0"),
        currency_conversion_fee_percent=Decimal("3"),
    ),
    "DMarket": MarketFees(
        market_name="DMarket",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
    "Mock.DMarket": MarketFees(
        market_name="Mock.DMarket",
        buy_fee_percent=Decimal("0"),
        sell_fee_percent=Decimal("5"),
        deposit_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("0"),
        currency_conversion_fee_percent=Decimal("0"),
    ),
}


def get_default_fees(market_name: str) -> MarketFees:
    return DEFAULT_FEES.get(market_name, MarketFees(market_name=market_name))
