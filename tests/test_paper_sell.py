from app.core.enums import PaperPositionStatus
from tests.conftest import detect_mock_opportunities


async def test_paper_sell_closes_position(test_app):
    opportunity = (await detect_mock_opportunities(test_app))[0]
    position = await test_app.paper_engine.paper_buy(opportunity.id)
    ready = await test_app.paper_engine.check_trade_bans()
    assert ready
    sold = await test_app.paper_engine.paper_sell(position.id)
    assert sold.status == PaperPositionStatus.SOLD.value
    assert sold.actual_profit_rub is not None

