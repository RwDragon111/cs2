from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings
from app.markets.base import MarketFees, MarketListing
from app.markets.payment_profile import MarketPaymentProfile
from app.utils.money import percent_of, quantize_money, quantize_percent, to_decimal


@dataclass(slots=True)
class PriceCalculation:
    buy_price_rub: Decimal
    expected_sell_price_rub: Decimal
    buy_market_fee_rub: Decimal
    sell_market_fee_rub: Decimal
    deposit_fee_rub: Decimal
    withdrawal_fee_rub: Decimal
    currency_conversion_fee_rub: Decimal
    expected_slippage_rub: Decimal
    risk_buffer_rub: Decimal
    total_fees_rub: Decimal
    payment_fees_rub: Decimal
    total_cost_rub: Decimal
    expected_net_profit_rub: Decimal
    roi_percent: Decimal


class PricingEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def calculate(
        self,
        buy_listing: MarketListing,
        sell_listing: MarketListing,
        buy_fees: MarketFees,
        sell_fees: MarketFees,
        buy_payment_profile: MarketPaymentProfile,
        sell_payment_profile: MarketPaymentProfile,
        expected_slippage_percent: Decimal = Decimal("1.0"),
    ) -> PriceCalculation:
        buy_price = to_decimal(buy_listing.price_rub or buy_listing.price)
        sell_price = to_decimal(sell_listing.price_rub or sell_listing.price)

        buy_market_fee = percent_of(buy_price, buy_fees.buy_fee_percent)
        sell_market_fee = percent_of(sell_price, sell_fees.sell_fee_percent)
        deposit_fee = percent_of(buy_price, buy_payment_profile.deposit_fee_percent)
        withdrawal_fee = percent_of(sell_price, sell_payment_profile.withdrawal_fee_percent)
        conversion_fee = Decimal("0.00")
        if buy_payment_profile.currency_conversion_required:
            conversion_fee += percent_of(buy_price, buy_payment_profile.estimated_conversion_fee_percent)
        if sell_payment_profile.currency_conversion_required:
            conversion_fee += percent_of(sell_price, sell_payment_profile.estimated_conversion_fee_percent)

        expected_slippage = percent_of(sell_price, expected_slippage_percent)
        risk_buffer = percent_of(buy_price, self.settings.risk_buffer_percent)
        total_fees = buy_market_fee + sell_market_fee + deposit_fee + withdrawal_fee + conversion_fee + expected_slippage + risk_buffer
        total_cost = buy_price + buy_market_fee + deposit_fee + conversion_fee + risk_buffer
        net_profit = sell_price - sell_market_fee - buy_price - buy_market_fee - deposit_fee - withdrawal_fee - conversion_fee - expected_slippage - risk_buffer
        roi = Decimal("0") if total_cost <= 0 else (net_profit / total_cost) * Decimal("100")

        return PriceCalculation(
            buy_price_rub=quantize_money(buy_price),
            expected_sell_price_rub=quantize_money(sell_price),
            buy_market_fee_rub=quantize_money(buy_market_fee),
            sell_market_fee_rub=quantize_money(sell_market_fee),
            deposit_fee_rub=quantize_money(deposit_fee),
            withdrawal_fee_rub=quantize_money(withdrawal_fee),
            currency_conversion_fee_rub=quantize_money(conversion_fee),
            expected_slippage_rub=quantize_money(expected_slippage),
            risk_buffer_rub=quantize_money(risk_buffer),
            total_fees_rub=quantize_money(total_fees),
            payment_fees_rub=quantize_money(deposit_fee + withdrawal_fee),
            total_cost_rub=quantize_money(total_cost),
            expected_net_profit_rub=quantize_money(net_profit),
            roi_percent=quantize_percent(roi),
        )

