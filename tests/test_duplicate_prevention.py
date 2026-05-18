import pytest

from app.core.exceptions import DuplicatePaperBuyError
from tests.conftest import detect_mock_opportunities


async def test_duplicate_paper_buy_is_blocked(test_app):
    opportunity = (await detect_mock_opportunities(test_app))[0]
    await test_app.paper_engine.paper_buy(opportunity.id)
    with pytest.raises(DuplicatePaperBuyError):
        await test_app.paper_engine.paper_buy(opportunity.id)

