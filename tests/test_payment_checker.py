from decimal import Decimal

from app.markets.payment_profile import MarketPaymentProfile, check_payment_compatibility


def test_payment_checker_allows_rub_market(settings):
    profile = MarketPaymentProfile(
        market_name="Some RUB Market",
        supports_rub=True,
        supports_mir=False,
        supports_russian_cards=False,
        supports_yoomoney=False,
        supports_crypto=False,
        deposit_currency="RUB",
        withdrawal_currency="RUB",
        deposit_fee_percent=Decimal("1"),
        withdrawal_fee_percent=Decimal("1"),
        currency_conversion_required=False,
        estimated_conversion_fee_percent=Decimal("0"),
    )
    assert check_payment_compatibility(profile, settings).is_allowed is True


def test_payment_checker_blocks_cs_money(settings):
    profile = MarketPaymentProfile(
        market_name="CS.MONEY",
        supports_rub=True,
        supports_mir=True,
        supports_russian_cards=True,
        supports_yoomoney=True,
        supports_crypto=True,
        deposit_currency="RUB",
        withdrawal_currency="RUB",
        deposit_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("0"),
        currency_conversion_required=False,
        estimated_conversion_fee_percent=Decimal("0"),
    )
    assert check_payment_compatibility(profile, settings).is_allowed is False

