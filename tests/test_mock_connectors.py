from app.markets.mock_market import MockMarketConnector


async def test_mock_connectors_return_required_items():
    listings = await MockMarketConnector("Mock.LIS-SKINS", "buy").fetch_listings()
    names = {listing.item_name for listing in listings}
    assert "AWP | Asiimov (Field-Tested)" in names
    assert "AK-47 | Redline (Field-Tested)" in names
    assert all(listing.available for listing in listings)

