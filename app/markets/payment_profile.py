from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.config import Settings


class MarketPaymentProfile(BaseModel):
    market_name: str
    supports_rub: bool
    supports_mir: bool
    supports_russian_cards: bool
    supports_yoomoney: bool
    supports_crypto: bool
    deposit_currency: str
    withdrawal_currency: str
    deposit_fee_percent: Decimal
    withdrawal_fee_percent: Decimal
    currency_conversion_required: bool
    estimated_conversion_fee_percent: Decimal
    notes: str = ""
    is_allowed: bool = False


def is_blacklisted_market_name(market_name: str, settings: Settings) -> bool:
    normalized = market_name.strip().lower()
    if normalized in {"cs.money", "csmoney", "cs money"}:
        return True
    return normalized in settings.excluded_market_names


def check_payment_compatibility(profile: MarketPaymentProfile, settings: Settings) -> MarketPaymentProfile:
    name = profile.market_name.strip()
    lower_name = name.lower()

    has_allowed_payment = (
        profile.supports_rub
        or profile.supports_mir
        or profile.supports_russian_cards
        or profile.supports_yoomoney
        or (settings.allow_markets_with_crypto_only and profile.supports_crypto)
    )

    allowed = (
        has_allowed_payment
        and profile.estimated_conversion_fee_percent <= settings.max_payment_conversion_fee_percent
        and profile.deposit_fee_percent <= settings.max_deposit_fee_percent
        and profile.withdrawal_fee_percent <= settings.max_withdrawal_fee_percent
        and not is_blacklisted_market_name(name, settings)
    )

    if lower_name in {"white.market", "white market"}:
        allowed = False
    if lower_name == "waxpeer" and profile.currency_conversion_required:
        allowed = False
    if lower_name in {"cs.money", "csmoney", "cs money"}:
        allowed = False

    return profile.model_copy(update={"is_allowed": allowed})


def default_payment_profiles(settings: Settings) -> dict[str, MarketPaymentProfile]:
    profiles = [
        MarketPaymentProfile(
            market_name="Market.CSGO",
            supports_rub=True,
            supports_mir=False,
            supports_russian_cards=True,
            supports_yoomoney=False,
            supports_crypto=True,
            deposit_currency="RUB",
            withdrawal_currency="RUB",
            deposit_fee_percent=Decimal("1.5"),
            withdrawal_fee_percent=Decimal("2.0"),
            currency_conversion_required=False,
            estimated_conversion_fee_percent=Decimal("0"),
            notes="Allowed in MVP: RUB-oriented market profile.",
        ),
        MarketPaymentProfile(
            market_name="Mock.Market.CSGO",
            supports_rub=True,
            supports_mir=False,
            supports_russian_cards=True,
            supports_yoomoney=False,
            supports_crypto=True,
            deposit_currency="RUB",
            withdrawal_currency="RUB",
            deposit_fee_percent=Decimal("1.5"),
            withdrawal_fee_percent=Decimal("2.0"),
            currency_conversion_required=False,
            estimated_conversion_fee_percent=Decimal("0"),
            notes="Mock profile mirroring Market.CSGO.",
        ),
        MarketPaymentProfile(
            market_name="LIS-SKINS",
            supports_rub=True,
            supports_mir=False,
            supports_russian_cards=True,
            supports_yoomoney=True,
            supports_crypto=True,
            deposit_currency="RUB",
            withdrawal_currency="RUB",
            deposit_fee_percent=Decimal("1.0"),
            withdrawal_fee_percent=Decimal("2.0"),
            currency_conversion_required=False,
            estimated_conversion_fee_percent=Decimal("0"),
            notes="Allowed in MVP: RUB and YooMoney profile.",
        ),
        MarketPaymentProfile(
            market_name="Mock.LIS-SKINS",
            supports_rub=True,
            supports_mir=False,
            supports_russian_cards=True,
            supports_yoomoney=True,
            supports_crypto=True,
            deposit_currency="RUB",
            withdrawal_currency="RUB",
            deposit_fee_percent=Decimal("1.0"),
            withdrawal_fee_percent=Decimal("2.0"),
            currency_conversion_required=False,
            estimated_conversion_fee_percent=Decimal("0"),
            notes="Mock profile mirroring LIS-SKINS.",
        ),
        MarketPaymentProfile(
            market_name="White.Market",
            supports_rub=False,
            supports_mir=False,
            supports_russian_cards=False,
            supports_yoomoney=False,
            supports_crypto=True,
            deposit_currency="USD",
            withdrawal_currency="USD",
            deposit_fee_percent=Decimal("0"),
            withdrawal_fee_percent=Decimal("0"),
            currency_conversion_required=True,
            estimated_conversion_fee_percent=Decimal("3"),
            notes="Excluded from base version by product requirement.",
        ),
        MarketPaymentProfile(
            market_name="Waxpeer",
            supports_rub=False,
            supports_mir=False,
            supports_russian_cards=False,
            supports_yoomoney=False,
            supports_crypto=True,
            deposit_currency="USD",
            withdrawal_currency="USD",
            deposit_fee_percent=Decimal("0"),
            withdrawal_fee_percent=Decimal("0"),
            currency_conversion_required=True,
            estimated_conversion_fee_percent=Decimal("3"),
            notes="Optional candidate only after payment audit.",
        ),
        MarketPaymentProfile(
            market_name="DMarket.Stats",
            supports_rub=False,
            supports_mir=False,
            supports_russian_cards=False,
            supports_yoomoney=False,
            supports_crypto=True,
            deposit_currency="USD",
            withdrawal_currency="USD",
            deposit_fee_percent=Decimal("0"),
            withdrawal_fee_percent=Decimal("0"),
            currency_conversion_required=True,
            estimated_conversion_fee_percent=Decimal("3"),
            notes="Stats-only connector. DMarket is not executable for Russia/Belarus users.",
        ),
    ]
    return {profile.market_name: check_payment_compatibility(profile, settings) for profile in profiles}
