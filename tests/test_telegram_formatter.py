from tests.conftest import detect_mock_opportunities
from app.telegram_bot.formatter import format_opportunity, format_paper_status


async def test_telegram_formatter_contains_opportunity_fields(test_app):
    opportunity = (await detect_mock_opportunities(test_app))[0]
    text = format_opportunity(opportunity)
    assert "Найдена арбитражная возможность" in text
    assert opportunity.item_name in text


def test_paper_status_formatter(settings, tmp_path):
    from app.db.database import init_db
    from app.db.repositories import PaperRepository
    from app.paper_trading.account import PaperAccountService

    session_factory = init_db(f"sqlite:///{tmp_path / 'status.db'}")
    repo = PaperRepository(session_factory)
    service = PaperAccountService(settings, repo)
    service.initialize()
    assert "Paper Trading Status" in format_paper_status(service.analytics())

