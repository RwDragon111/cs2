from tests.conftest import detect_mock_opportunities
from app.opportunities.stats_spread import MarketStatsSpread
from app.telegram_bot.formatter import format_opportunity, format_paper_status, format_stats_spread
from app.utils.time import utc_now
from decimal import Decimal


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


def test_stats_spread_formatter_marks_not_a_trade():
    text = format_stats_spread(
        MarketStatsSpread(
            id="test",
            normalized_name="AWP | Asiimov (Field-Tested)",
            cheaper_market="Market.CSGO",
            expensive_market="DMarket.Stats",
            cheaper_listing_id="1",
            cheaper_price_rub=Decimal("9000"),
            expensive_price_rub=Decimal("10500"),
            cheaper_price_usd=Decimal("90"),
            expensive_price_usd=Decimal("105"),
            spread_rub=Decimal("1500"),
            spread_percent=Decimal("16.67"),
            detected_at=utc_now(),
        )
    )
    assert "НЕ сделка" in text
    assert "DMarket.Stats" in text
