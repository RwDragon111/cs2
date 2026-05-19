from decimal import Decimal

from app.markets.payment_profile import default_payment_profiles
from app.pricing.fees import get_default_fees
from app.pricing.pricing_engine import PricingEngine
from app.scheduler.jobs import with_prices
from app.currency.currency_engine import CurrencyEngine
from app.markets.mock_market import MockMarketConnector


async def test_pricing_engine_calculates_positive_net(settings):
    currency = CurrencyEngine(settings)
    buy = with_prices((await MockMarketConnector("Mock.DMarket", "buy").fetch_listings())[0], currency)
    sell = with_prices((await MockMarketConnector("Mock.Market.CSGO.BuyOrder", "sell").fetch_listings())[0], currency)
    profiles = default_payment_profiles(settings)
    result = PricingEngine(settings).calculate(
        buy,
        sell,
        get_default_fees(buy.market_name),
        get_default_fees(sell.market_name),
        profiles[buy.market_name],
        profiles[sell.market_name],
    )
    assert result.expected_net_profit_rub > Decimal("100")
    assert result.roi_percent > Decimal("5")
