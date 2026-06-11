"""
停損雙層保護
Layer 1：下單同時掛停損委託（元大 API 停損單，毫秒級）
Layer 2：後端每分鐘輪詢備援（Layer 1 失效時接手）
"""
import logging
from datetime import datetime, time

import pytz

logger = logging.getLogger(__name__)

_TW = pytz.timezone("Asia/Taipei")


class StopLossGuard:
    def __init__(self, broker):
        self.broker = broker
        # symbol → {stop_price, quantity, entry_price}
        self._polling_symbols: dict[str, dict] = {}

    async def setup(
        self,
        symbol: str,
        quantity: int,
        stop_price: float,
        entry_price: float,
    ) -> bool:
        """下單後立即呼叫，設置雙層保護。回傳 Layer 1 是否成功。"""
        from utils.telegram import send_message

        layer1_ok = False
        try:
            stop_order = await self.broker.place_order(
                symbol=symbol,
                action="sell",
                order_type="stop",
                quantity=quantity,
                stop_price=stop_price,
            )
            await _save_stop_order(symbol, stop_order["order_id"], stop_price)
            layer1_ok = True
            logger.info("StopLossGuard Layer1 OK: %s stop@%.2f", symbol, stop_price)
        except Exception as e:
            logger.warning("StopLossGuard Layer1 FAIL [%s]: %s", symbol, e)
            await send_message(
                f"⚠️ 停損委託失敗，啟用輪詢備援\n"
                f"股票：{symbol}  停損價：{stop_price}\n"
                f"原因：{e}"
            )

        # Layer 2 無論 Layer 1 成功與否都同時啟用（雙重保險）
        self._polling_symbols[symbol] = {
            "stop_price": stop_price,
            "quantity": quantity,
            "entry_price": entry_price,
        }
        return layer1_ok

    async def polling_monitor(self):
        """
        Layer 2：每分鐘輪詢，由 APScheduler 每分鐘呼叫。
        盤中時間 09:00–13:30 才執行。
        """
        from utils.telegram import send_message

        now = datetime.now(_TW).time()
        if not (time(9, 0) <= now <= time(13, 30)):
            return

        for symbol, info in list(self._polling_symbols.items()):
            try:
                current_price = await _get_realtime_price(symbol)
                if current_price is None:
                    continue

                if current_price <= info["stop_price"]:
                    await self.broker.place_order(
                        symbol=symbol,
                        action="sell",
                        order_type="market",
                        quantity=info["quantity"],
                    )
                    del self._polling_symbols[symbol]

                    loss_pct = (current_price - info["entry_price"]) / info["entry_price"] * 100
                    logger.warning(
                        "StopLossGuard Layer2 triggered: %s %.2f (%.1f%%)",
                        symbol, current_price, loss_pct,
                    )
                    await send_message(
                        f"🛑 Layer 2 停損觸發\n"
                        f"━━━━━━━━━━━━\n"
                        f"📌 {symbol} 市價賣出\n"
                        f"💰 成本：{info['entry_price']} → 停損：{info['stop_price']}\n"
                        f"📉 損失：{loss_pct:.1f}%\n"
                        f"🤖 後台輪詢自動執行"
                    )
            except Exception as e:
                logger.error("StopLossGuard polling error [%s]: %s", symbol, e)

    def remove(self, symbol: str):
        """手動移除監控（例如平倉後呼叫）"""
        self._polling_symbols.pop(symbol, None)

    @property
    def watching(self) -> list[str]:
        return list(self._polling_symbols.keys())


# ── helpers ──────────────────────────────────────────────────────────────────

async def _save_stop_order(symbol: str, order_id: str, stop_price: float):
    """記錄停損委託到 DB（非同步，失敗不影響主流程）"""
    import asyncio
    import sqlite3
    import os

    db_path = os.path.join(os.path.dirname(__file__), "..", "cache.db")

    def _write():
        con = sqlite3.connect(db_path)
        con.execute(
            "CREATE TABLE IF NOT EXISTS stop_orders "
            "(symbol TEXT, order_id TEXT, stop_price REAL, created_at TEXT)"
        )
        con.execute(
            "INSERT INTO stop_orders VALUES (?,?,?,datetime('now'))",
            (symbol, order_id, stop_price),
        )
        con.commit()
        con.close()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write)


async def _get_realtime_price(symbol: str) -> float | None:
    """取得即時報價（使用現有 stock_quote_fetcher，包在 executor 裡）"""
    import asyncio
    from services.stock_quote_fetcher import fetch_stock_quote

    loop = asyncio.get_event_loop()
    try:
        quote = await loop.run_in_executor(None, fetch_stock_quote, symbol)
        return float(quote.get("price", 0)) or None
    except Exception:
        return None
