import pytest

from app.config import Settings
from app.core.exceptions import PaperTradingError
from tests.conftest import detect_mock_opportunities


async def test_signal_only_blocks_paper_buy(test_app):
    test_app.settings.trading_mode = "SIGNAL_ONLY"
    opportunity = (await detect_mock_opportunities(test_app))[0]
    with pytest.raises(PaperTradingError):
        await test_app.paper_engine.paper_buy(opportunity.id)


def test_future_real_modes_are_not_default(settings: Settings):
    assert settings.trading_mode == "PAPER_TRADING"

