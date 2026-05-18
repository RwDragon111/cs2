from tests.conftest import detect_mock_opportunities


async def test_paper_pnl_after_sell(test_app):
    opportunity = (await detect_mock_opportunities(test_app))[0]
    position = await test_app.paper_engine.paper_buy(opportunity.id)
    await test_app.paper_engine.check_trade_bans()
    await test_app.paper_engine.paper_sell(position.id)
    analytics = test_app.paper_account.analytics()
    assert analytics.sold_positions == 1
    assert analytics.realized_pnl_rub != 0

