from app.core.enums import PaperPositionStatus
from tests.conftest import detect_mock_opportunities


async def test_paper_buy_creates_trade_locked_position(test_app):
    opportunity = (await detect_mock_opportunities(test_app))[0]
    position = await test_app.paper_engine.paper_buy(opportunity.id)
    account = test_app.paper_repository.account()
    assert position.status == PaperPositionStatus.TRADE_LOCKED.value
    assert account.current_balance_rub < account.initial_balance_rub

