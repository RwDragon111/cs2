from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.db.models import DealORM, InventoryORM
from app.db.repositories import DealRepository, InventoryRepository, TradingStateRepository
from app.markets.csgo_market_client import CSGOMarketClient
from app.markets.dmarket_client import DMarketClient
from app.utils.money import percent_of, quantize_money, quantize_percent
from app.utils.time import ensure_aware, utc_now


@dataclass(slots=True)
class DemoStats:
    initial_balance: Decimal
    current_balance: Decimal
    virtual_buys: int
    virtual_sells: int
    active_deals: int
    total_profit: Decimal
    average_roi: Decimal
    best_deal: InventoryORM | None
    worst_deal: InventoryORM | None
    win_rate: Decimal


class InventoryService:
    def __init__(
        self,
        settings: Settings,
        deals: DealRepository,
        inventory: InventoryRepository,
        trading: TradingStateRepository,
        dmarket: DMarketClient,
        csgo_market: CSGOMarketClient,
    ) -> None:
        self.settings = settings
        self.deals = deals
        self.inventory = inventory
        self.trading = trading
        self.dmarket = dmarket
        self.csgo_market = csgo_market

    async def mark_deal_bought(self, deal_id: int, confirmed_real: bool = False) -> InventoryORM:
        deal = self.deals.get(deal_id)
        if deal is None:
            raise RuntimeError("Deal not found")

        mode = self.trading.get_mode()
        if mode == "REAL":
            if not self.settings.allow_real_trading:
                raise RealTradingDisabledError("REAL mode is disabled by ALLOW_REAL_TRADING=false")
            if not confirmed_real:
                raise RealTradingDisabledError("Real buy requires explicit Telegram confirmation")
            await self.dmarket.buy_item(deal.dmarket_listing_id)
            return self._create_inventory_from_deal(deal, is_demo=False)

        account = self.trading.demo_account()
        cost = Decimal(deal.buy_price_with_fees)
        if Decimal(account.balance) < cost:
            raise RuntimeError("Недостаточно средств на демо-счете")
        row = self._create_inventory_from_deal(deal, is_demo=True)
        self.trading.apply_demo_transaction(
            transaction_type="buy",
            amount=-cost,
            item_name=deal.item_name,
            related_inventory_id=row.id,
            comment=f"Virtual buy from deal {deal.id}",
        )
        self.deals.mark_status(deal.id, "bought")
        return row

    async def mark_sold(self, inventory_id: int, confirmed_real: bool = False) -> InventoryORM:
        item = self.inventory.get(inventory_id)
        if item is None:
            raise RuntimeError("Inventory item not found")
        if item.status not in {"ready_to_sell", "listed", "trade_locked", "bought"}:
            raise RuntimeError("Item cannot be sold from current status")
        now = utc_now()
        if ensure_aware(item.trade_lock_until) > now:
            raise RuntimeError("Trade lock еще активен")

        mode = self.trading.get_mode()
        if mode == "REAL" and not item.is_demo:
            if not self.settings.allow_real_trading:
                raise RealTradingDisabledError("REAL mode is disabled by ALLOW_REAL_TRADING=false")
            if not confirmed_real:
                raise RealTradingDisabledError("Real sell requires explicit Telegram confirmation")
            await self.csgo_market.sell_item(str(item.id), Decimal(item.expected_sell_price))

        sell_price_after_fees = self._net_sell_price(Decimal(item.expected_sell_price))
        actual_profit = quantize_money(sell_price_after_fees - Decimal(item.buy_price))
        actual_roi = quantize_percent(actual_profit / Decimal(item.buy_price) * Decimal("100")) if item.buy_price else Decimal("0")
        sold = self.inventory.mark_sold(item.id, sell_price_after_fees, actual_profit, actual_roi)
        if item.is_demo:
            self.trading.apply_demo_transaction(
                transaction_type="sell",
                amount=sell_price_after_fees,
                item_name=item.item_name,
                related_inventory_id=item.id,
                comment="Virtual sell after trade lock",
            )
        return sold

    def refresh_trade_locks(self) -> list[InventoryORM]:
        return self.inventory.mark_ready_items()

    def demo_stats(self) -> DemoStats:
        account = self.trading.demo_account()
        items = self.inventory.list(is_demo=True, limit=10000)
        sold = [item for item in items if item.status == "sold"]
        active = [item for item in items if item.status != "sold"]
        profits = [Decimal(item.actual_profit or 0) for item in sold]
        rois = [Decimal(item.actual_roi or 0) for item in sold]
        total_profit = quantize_money(sum(profits, Decimal("0")))
        average_roi = quantize_percent(sum(rois, Decimal("0")) / len(rois)) if rois else Decimal("0")
        wins = [profit for profit in profits if profit > 0]
        win_rate = quantize_percent(Decimal(len(wins)) / Decimal(len(sold)) * Decimal("100")) if sold else Decimal("0")
        best_deal = max(sold, key=lambda item: Decimal(item.actual_profit or 0), default=None)
        worst_deal = min(sold, key=lambda item: Decimal(item.actual_profit or 0), default=None)
        return DemoStats(
            initial_balance=Decimal(account.initial_balance),
            current_balance=Decimal(account.balance),
            virtual_buys=len(items),
            virtual_sells=len(sold),
            active_deals=len(active),
            total_profit=total_profit,
            average_roi=average_roi,
            best_deal=best_deal,
            worst_deal=worst_deal,
            win_rate=win_rate,
        )

    def _create_inventory_from_deal(self, deal: DealORM, is_demo: bool) -> InventoryORM:
        bought_at = utc_now()
        trade_lock_until = bought_at + timedelta(days=self.settings.trade_lock_days)
        return self.inventory.create(
            {
                "deal_id": deal.id,
                "item_name": deal.item_name,
                "market_hash_name": deal.market_hash_name,
                "buy_price": deal.buy_price_with_fees,
                "expected_sell_price": deal.csgo_buy_order_price,
                "expected_profit": deal.profit,
                "expected_roi": deal.roi,
                "bought_at": bought_at,
                "trade_lock_until": trade_lock_until,
                "status": "trade_locked",
                "is_demo": is_demo,
                "raw_payload": deal.details or {},
            }
        )

    def _net_sell_price(self, sell_price: Decimal) -> Decimal:
        fee_percent = self.settings.csgo_market_fee_percent + self.settings.withdrawal_fee_percent
        return quantize_money(sell_price - percent_of(sell_price, fee_percent))
