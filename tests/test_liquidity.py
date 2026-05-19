from app.liquidity.liquidity_engine import LiquidityEngine
from app.markets.mock_market import MockMarketConnector


async def test_liquidity_score_is_high_for_mock_history():
    connector = MockMarketConnector("Mock.Market.CSGO.BuyOrder", "sell")
    listings = await connector.fetch_listings()
    history = await connector.fetch_sales_history(listings[0].normalized_name)
    score = LiquidityEngine().calculate(listings[0].normalized_name, listings, history, listings[0].price_rub, listings[0].price_rub)
    assert score.score >= 60
