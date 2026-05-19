from app.currency.currency_engine import CurrencyEngine
from app.liquidity.liquidity_engine import LiquidityEngine
from app.markets.mock_market import MockMarketConnector
from app.markets.payment_profile import default_payment_profiles
from app.pricing.fees import get_default_fees
from app.pricing.pricing_engine import PricingEngine
from app.risk.risk_filters import RiskFilters
from app.scheduler.jobs import with_prices


async def test_risk_filters_allow_mock_opportunity(settings):
    currency = CurrencyEngine(settings)
    buy = with_prices((await MockMarketConnector("Mock.DMarket", "buy").fetch_listings())[0], currency)
    sell = with_prices((await MockMarketConnector("Mock.Market.CSGO.BuyOrder", "sell").fetch_listings())[0], currency)
    profiles = default_payment_profiles(settings)
    calculation = PricingEngine(settings).calculate(
        buy,
        sell,
        get_default_fees(buy.market_name),
        get_default_fees(sell.market_name),
        profiles[buy.market_name],
        profiles[sell.market_name],
    )
    history = await MockMarketConnector("Mock.Market.CSGO.BuyOrder", "sell").fetch_sales_history(buy.normalized_name)
    liquidity = LiquidityEngine().calculate(buy.normalized_name, [buy, sell], history, buy.price_rub, sell.price_rub)
    decision = RiskFilters(settings).evaluate(buy, sell, calculation, liquidity, profiles[buy.market_name], profiles[sell.market_name])
    assert decision.allowed is True
