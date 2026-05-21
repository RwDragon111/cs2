from decimal import Decimal

from app.config import Settings
from app.markets.types import BuyOrder
from app.services.scanner import ArbitrageScanner
from app.utils.item_titles import expand_dmarket_title_variants, extract_title_from_text


def test_extract_title_from_dmarket_and_csgo_market_urls():
    dmarket_url = (
        "https://dmarket.com/ru/ingame-items/item-list/csgo-skins?"
        "title=Kukri%20Knife%20%7C%20Blue%20Steel%20(Battle-Scarred)"
    )
    csgo_url = (
        "https://market.csgo.com/ru/Knife/Kukri%20Knife/"
        "%E2%98%85%20Kukri%20Knife%20%7C%20Blue%20Steel%20%28Battle-Scarred%29"
    )

    assert extract_title_from_text(dmarket_url) == "Kukri Knife | Blue Steel (Battle-Scarred)"
    assert extract_title_from_text(csgo_url) == "★ Kukri Knife | Blue Steel (Battle-Scarred)"


def test_dmarket_title_variants_cover_starred_knife_names():
    variants = expand_dmarket_title_variants("Kukri Knife | Blue Steel (Battle-Scarred)")

    assert "Kukri Knife | Blue Steel (Battle-Scarred)" in variants
    assert "Kukri Knife | Blue Steel" in variants
    assert "★ Kukri Knife | Blue Steel (Battle-Scarred)" in variants
    assert "★ Kukri Knife | Blue Steel" in variants


def test_scanner_always_includes_configured_extra_titles():
    settings = Settings(
        telegram_enabled=False,
        use_mock_markets=True,
        dmarket_stats_titles="",
        dmarket_dynamic_title_limit=3,
        dmarket_extra_titles="Kukri Knife | Blue Steel (Battle-Scarred)",
    )
    scanner = ArbitrageScanner(settings, None, None, None, None, None, None)  # type: ignore[arg-type]

    titles = scanner._select_dmarket_titles(
        [
            BuyOrder(
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("9000"),
                currency="RUB",
                price_rub=Decimal("9000"),
                count=50,
                raw_payload={},
            )
        ]
    )

    assert "★ Kukri Knife | Blue Steel (Battle-Scarred)" in titles
    assert "Kukri Knife | Blue Steel" in titles
