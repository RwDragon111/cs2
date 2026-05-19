from tests.conftest import detect_mock_opportunities


async def test_opportunity_detector_finds_mock_opportunities(test_app):
    opportunities = await detect_mock_opportunities(test_app)
    assert opportunities
    assert {op.buy_market for op in opportunities} == {"Mock.DMarket"}
    assert {op.sell_market for op in opportunities} == {"Mock.Market.CSGO.BuyOrder"}
