import logging
import os
from collections.abc import Callable

from brokers.base import BrokerBase

logger = logging.getLogger(__name__)


class SinopacBroker(BrokerBase):
    """永豐金證券 Shioaji SDK 實作。

    登入失敗時拋出 RuntimeError，由 broker 工廠捕捉後 fallback 至 YuantaBroker。
    """

    def __init__(self) -> None:
        try:
            import shioaji as sj  # type: ignore[import]
        except ImportError as e:
            raise RuntimeError("shioaji 未安裝，請執行 pip install shioaji>=1.1.0") from e

        account = os.getenv("SINOPAC_ACCOUNT", "")
        password = os.getenv("SINOPAC_PASSWORD", "")
        if not account or not password:
            raise RuntimeError("SINOPAC_ACCOUNT / SINOPAC_PASSWORD 未設定")

        self._api = sj.Shioaji()
        accounts = self._api.login(account, password)
        logger.info("SinopacBroker 登入成功，帳號數: %d", len(accounts))

    # ── read-only ──────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        contract = self._api.Contracts.Stocks[symbol]
        snapshot = self._api.snapshots([contract])
        if not snapshot:
            return {}
        s = snapshot[0]
        return {
            "symbol": symbol,
            "price": s.close,
            "volume": s.volume,
            "open": s.open,
            "high": s.high,
            "low": s.low,
        }

    async def get_positions(self) -> list:
        positions = self._api.list_positions(self._api.stock_account)
        return [
            {
                "symbol": p.code,
                "quantity": p.quantity,
                "price": p.price,
                "pnl": p.pnl,
            }
            for p in positions
        ]

    async def get_balance(self) -> dict:
        margin = self._api.account_balance()
        return {
            "available": getattr(margin, "available_margin", 0),
            "total": getattr(margin, "total_margin", 0),
        }

    async def get_orders(self) -> list:
        trades = self._api.list_trades()
        return [
            {
                "order_id": t.order.id,
                "symbol": t.contract.code,
                "action": "buy" if t.order.action == "Buy" else "sell",
                "quantity": t.order.quantity,
                "price": t.order.price,
                "status": str(t.status.status),
            }
            for t in trades
        ]

    # ── order ──────────────────────────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        action: str,
        order_type: str,
        quantity: int,
        price: float | None = None,
        stop_price: float | None = None,
    ) -> dict:
        import shioaji as sj  # type: ignore[import]

        contract = self._api.Contracts.Stocks[symbol]
        sj_action = sj.constant.Action.Buy if action == "buy" else sj.constant.Action.Sell
        sj_price_type = (
            sj.constant.StockPriceType.MKT if order_type == "market"
            else sj.constant.StockPriceType.LMT
        )
        order = self._api.Order(
            price=price or 0,
            quantity=quantity,
            action=sj_action,
            price_type=sj_price_type,
            order_type=sj.constant.TFTOrderType.ROD,
            account=self._api.stock_account,
        )
        trade = self._api.place_order(contract, order)
        return {
            "order_id": trade.order.id,
            "symbol": symbol,
            "status": str(trade.status.status),
        }

    async def cancel_order(self, order_id: str) -> bool:
        trades = self._api.list_trades()
        for t in trades:
            if t.order.id == order_id:
                self._api.cancel_order(t)
                return True
        return False

    # ── streaming ──────────────────────────────────────────────────────────

    def subscribe_tick(self, symbol: str, callback: Callable[[dict], None]) -> None:
        contract = self._api.Contracts.Stocks[symbol]

        @self._api.on_tick_stk_v1()
        def _on_tick(exchange, tick):  # type: ignore[misc]
            if tick.code != symbol:
                return
            callback({
                "price": tick.close,
                "volume": tick.volume,
                "timestamp": int(tick.datetime.timestamp() * 1000),
            })

        self._api.subscribe(contract, quote_type="tick")
        logger.info("SinopacBroker: 已訂閱 %s Tick", symbol)
