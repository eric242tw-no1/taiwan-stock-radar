"""
元大 YuantaSparkAPI broker — pythonnet DLL wrapper

環境需求：
  - Python 3.8+、.NET 8 Runtime（不需 SDK）
  - pip install pythonnet
  - 環境變數 YUANTA_DLL_DIR 指向 YuantaSparkAPI.dll 所在資料夾

YUANTA_SIMULATION=true（預設）時不需要 DLL，所有操作回傳假資料。

架構說明：
  - intMark=1（查詢/下單）→ 一次性回應，用 asyncio.Future 橋接
  - intMark=2（訂閱推送）→ 持續推送，用 callback registry
"""
import asyncio
import logging
import os
import platform
import sys
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from brokers.base import BrokerBase, BrokerConnectionError, BrokerOrderError

logger = logging.getLogger(__name__)

# ── DLL lazy-load state ────────────────────────────────────────────────────────
_dll_loaded = False
_dll_load_error: str | None = None

_Trader = None
_EnvMode = None
_LogType = None
_MarketType = None
_StockOrder = None
_OnResponseHandler = None
_NetList = None


def _load_dll(dll_dir: str) -> bool:
    global _dll_loaded, _dll_load_error
    global _Trader, _EnvMode, _LogType, _MarketType
    global _StockOrder, _OnResponseHandler, _NetList

    if _dll_loaded:
        return True
    if _dll_load_error:
        return False

    try:
        from pythonnet import load as _pnet_load
        _pnet_load("coreclr")

        import clr  # noqa: PLC0415
        clr.AddReference("System.Collections")
        from System.Collections.Generic import List  # type: ignore[import]

        path = str(Path(dll_dir).resolve())
        if path not in sys.path:
            sys.path.append(path)
        if platform.system() == "Windows":
            os.add_dll_directory(path)

        clr.AddReference("YuantaSparkAPI")
        from YuantaOneAPI import (  # type: ignore[import]
            YuantaSparkAPITrader,
            enumEnvironmentMode,
            enumLogType,
            enumMarketType,
            StockOrder,
            OnResponseEventHandler,
        )

        _Trader = YuantaSparkAPITrader
        _EnvMode = enumEnvironmentMode
        _LogType = enumLogType
        _MarketType = enumMarketType
        _StockOrder = StockOrder
        _OnResponseHandler = OnResponseEventHandler
        _NetList = List
        _dll_loaded = True
        logger.info("YuantaSparkAPI DLL 載入成功 (path=%s)", path)
        return True

    except Exception as exc:
        _dll_load_error = str(exc)
        logger.error("YuantaSparkAPI DLL 載入失敗: %s", exc)
        return False


# ── Login status codes ────────────────────────────────────────────────────────

_LOGIN_CODES: dict[str, str] = {
    "0001": "成功",
    "00001": "成功",
    "0000": "執行失敗",
    "0102": "密碼凍結或未啟用",
    "0112": "無此權限",
}


# ── Broker ─────────────────────────────────────────────────────────────────────

class YuantaBroker(BrokerBase):
    """元大證券 YuantaSparkAPI broker（pythonnet DLL 版本）。

    simulation=true（預設）：不載入 DLL，回傳模擬資料。
    simulation=false：載入 DLL，透過 OnResponse 事件取得結果。

    回應架構：
      intMark=1（查詢/下單）→ asyncio.Future，await 等待單次回應
      intMark=2（訂閱推送）→ callback registry，每次推送呼叫所有已註冊 handler
    """

    def __init__(self) -> None:
        self.simulation: bool = os.getenv("YUANTA_SIMULATION", "true").lower() == "true"
        self.account: str = os.getenv("YUANTA_ACCOUNT", "")
        self.password: str = os.getenv("YUANTA_PASSWORD", "")
        self.dll_dir: str = os.getenv("YUANTA_DLL_DIR", "")
        self.env_mode: str = os.getenv("YUANTA_ENV", "UAT")
        self.pfx_path: str = os.getenv("YUANTA_PFX_PATH", "")
        self.pfx_pass: str = os.getenv("YUANTA_PFX_PASS", "")

        self._api: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._logged_in: bool = False

        # intMark=1：一次性查詢/下單 Future
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_lock = Lock()

        # intMark=2：持續訂閱 callback registry
        # key = strIndex（如 "SubscribeWatchlistAll", "RR_RealReport"）
        self._sub_handlers: dict[str, list[Callable[[Any], None]]] = {}
        self._sub_lock = Lock()

    # ── 初始化 ──────────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """建立 API 連線並登入。simulation=true 時為 no-op。"""
        if self.simulation:
            logger.info("YuantaBroker [SIM] connect (no-op)")
            return

        if not self.dll_dir:
            raise BrokerConnectionError("YUANTA_DLL_DIR 未設定")
        if not _load_dll(self.dll_dir):
            raise BrokerConnectionError(f"DLL 載入失敗: {_dll_load_error}")

        self._loop = asyncio.get_running_loop()
        self._api = _Trader()
        self._api.OnResponse += _OnResponseHandler(self._on_response)
        self._api.SetLogType(_LogType.COMMON)

        env = _EnvMode.PROD if self.env_mode == "PROD" else _EnvMode.UAT
        self._api.Open(env)
        await asyncio.sleep(1)

        fut = self._make_future("Login")
        if self.pfx_path:
            self._api.Login(self.pfx_path, self.pfx_pass, self.account, self.password)
        else:
            self._api.Login(self.account, self.password)

        try:
            await asyncio.wait_for(fut, timeout=15)
        except asyncio.TimeoutError:
            raise BrokerConnectionError(
                "Login 逾時（請確認 IP 已加入元大白名單，並向營業員申請 API 權限）"
            )

        if not self._logged_in:
            raise BrokerConnectionError("登入失敗，請確認帳號密碼與 API 權限")

        logger.info("YuantaBroker 登入成功 (account=%s, env=%s)", self.account, self.env_mode)

    async def disconnect(self) -> None:
        if self.simulation or self._api is None:
            return
        try:
            self._api.LogOut()
            await asyncio.sleep(0.5)
            self._api.Close()
            self._api.Dispose()
        except Exception as exc:
            logger.warning("disconnect 例外: %s", exc)
        finally:
            self._api = None
            self._logged_in = False

    # ── OnResponse 事件橋接 ──────────────────────────────────────────────────────

    def _on_response(
        self,
        int_mark: int,
        dw_index: int,
        str_index: str,
        obj_handle: Any,
        obj_value: Any,
    ) -> None:
        """從 .NET 執行緒呼叫；橋接回 asyncio event loop。"""
        if self._loop is None:
            return

        try:
            if int_mark == 0:
                logger.debug("YuantaSparkAPI 系統回應: %s", obj_value)
                return

            if int_mark == 1:
                # 一次性查詢/下單回應
                if str_index == "Login":
                    self._handle_login_response(obj_value)

                with self._pending_lock:
                    fut = self._pending.pop(str_index, None)
                if fut and not fut.done():
                    self._loop.call_soon_threadsafe(fut.set_result, obj_value)

            elif int_mark == 2:
                # 持續訂閱推送 — 呼叫所有已註冊 callback
                with self._sub_lock:
                    handlers = list(self._sub_handlers.get(str_index, []))
                for handler in handlers:
                    try:
                        self._loop.call_soon_threadsafe(
                            self._loop.create_task,
                            self._safe_call(handler, obj_value),
                        )
                    except Exception as exc:
                        logger.warning("訂閱 handler 例外 [%s]: %s", str_index, exc)

        except Exception as exc:
            logger.exception("OnResponse 處理例外: %s", exc)

    async def _safe_call(self, fn: Callable, value: Any) -> None:
        try:
            result = fn(value)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.warning("訂閱 callback 例外: %s", exc)

    def _handle_login_response(self, obj_value: Any) -> None:
        try:
            status = obj_value.LoginStatus
            code = str(status.MsgCode)
            msg = str(status.MsgContent)
            count = int(status.Count)
            desc = _LOGIN_CODES.get(code, "未知代碼")
            self._logged_in = code in ("0001", "00001") or count > 0
            if self._logged_in:
                logger.info("Login 成功 code=%s (%s) 帳號數=%d", code, desc, count)
            else:
                logger.warning("Login 失敗 code=%s (%s) msg=%s", code, desc, msg)
        except Exception as exc:
            logger.warning("Login 回應解析失敗: %s", exc)
            self._logged_in = False

    # ── 內部工具 ─────────────────────────────────────────────────────────────────

    def _make_future(self, key: str) -> "asyncio.Future":
        loop = self._loop or asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        with self._pending_lock:
            self._pending[key] = fut
        return fut

    async def _query(
        self,
        key: str,
        fn: Callable,
        timeout: float = 10.0,
    ) -> Any:
        """執行一次性查詢，等待 intMark=1 回應。"""
        fut = self._make_future(key)
        fn()
        return await asyncio.wait_for(fut, timeout=timeout)

    def _subscribe(
        self,
        str_index: str,
        handler: Callable[[Any], None],
        subscribe_fn: Callable,
    ) -> None:
        """註冊持續訂閱 handler 並送出訂閱請求。"""
        with self._sub_lock:
            self._sub_handlers.setdefault(str_index, []).append(handler)
        subscribe_fn()

    def _unsubscribe(self, str_index: str, handler: Callable | None = None) -> None:
        """移除訂閱 handler（handler=None 則移除全部）。"""
        with self._sub_lock:
            if handler is None:
                self._sub_handlers.pop(str_index, None)
            else:
                handlers = self._sub_handlers.get(str_index, [])
                if handler in handlers:
                    handlers.remove(handler)

    def _require_connection(self) -> None:
        if self._api is None or not self._logged_in:
            raise BrokerConnectionError("尚未連線，請先呼叫 connect()")

    # ── 報價查詢 ─────────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        if self.simulation:
            return {"symbol": symbol, "price": 0.0, "simulated": True}
        self._require_connection()
        from YuantaOneAPI import WatchlistAll  # type: ignore[import]
        lst = _NetList[WatchlistAll]()
        item = WatchlistAll()
        item.MarketNo = _MarketType.TWSE
        item.StkCode = symbol
        lst.Add(item)
        result = await self._query(
            "GetWatchListAll",
            lambda: self._api.GetWatchListAll(self.account, lst),
        )
        return self._parse_quote(result, symbol)

    def _parse_quote(self, result: Any, symbol: str) -> dict:
        try:
            items = result.QueryWatchList
            for i in range(items.Count):
                item = items[i]
                if str(item.StkCode) == symbol:
                    return {
                        "symbol": symbol,
                        "price": float(item.DealPrice),
                        "open": float(item.OpenPrice),
                        "high": float(item.HighPrice),
                        "low": float(item.LowPrice),
                        "volume": int(item.TotalVol),
                        "prev_close": float(item.YstPrice),
                        "change": float(item.DealPrice) - float(item.YstPrice),
                    }
        except Exception as exc:
            logger.warning("報價解析失敗: %s", exc)
        return {"symbol": symbol, "price": 0.0}

    # ── 庫存查詢 ─────────────────────────────────────────────────────────────────

    async def get_positions(self) -> list:
        if self.simulation:
            return []
        self._require_connection()
        result = await self._query(
            "GetStoreSummary",
            lambda: self._api.GetStoreSummary(self.account),
        )
        return self._parse_positions(result)

    def _parse_positions(self, result: Any) -> list:
        positions = []
        try:
            stk_list = result.StkStoreList
            for i in range(stk_list.Count):
                s = stk_list[i]
                qty_shares = int(s.StockQty) if hasattr(s, "StockQty") else 0
                positions.append({
                    "symbol": str(s.StkCode),
                    "name": str(s.StkName),
                    "qty_shares": qty_shares,
                    "qty_lots": qty_shares // 1000,
                    "cost": float(s.Price) if hasattr(s, "Price") else 0.0,
                    "market_value": float(s.MarketAmt) if hasattr(s, "MarketAmt") else 0.0,
                    "unrealized_pnl": float(s.ReturnAmt) if hasattr(s, "ReturnAmt") else 0.0,
                })
        except Exception as exc:
            logger.warning("庫存解析失敗: %s", exc)
        return positions

    async def get_position(self, symbol: str) -> int:
        for p in await self.get_positions():
            if p["symbol"] == symbol:
                return p["qty_lots"]
        return 0

    async def get_balance(self) -> dict:
        if self.simulation:
            return {"available": 0.0, "simulated": True}
        self._require_connection()
        result = await self._query(
            "GetBankBalance",
            lambda: self._api.GetBankBalance(self.account),
        )
        try:
            return {"available": float(result.Balance)}
        except Exception:
            return {"available": 0.0}

    async def get_orders(self) -> list:
        if self.simulation:
            return []
        self._require_connection()
        result = await self._query(
            "GetRealReport",
            lambda: self._api.GetRealReport(self.account),
        )
        orders = []
        try:
            items = result.RealReportList
            for i in range(items.Count):
                r = items[i]
                orders.append({
                    "order_no": str(r.OrderNo),
                    "symbol": str(r.CompanyNo),
                    "side": "buy" if str(r.BS) == "B" else "sell",
                    "qty": int(r.OrderQty),
                    "price": float(r.Price),
                    "status": int(r.OrderStatus),
                })
        except Exception as exc:
            logger.warning("委託查詢解析失敗: %s", exc)
        return orders

    # ── 下單 ─────────────────────────────────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        action: str,
        order_type: str,
        quantity: int,         # 單位：張
        price: float | None = None,
        stop_price: float | None = None,
    ) -> dict:
        if self.simulation:
            sim_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"
            logger.info("YuantaBroker [SIM] %s %s %d張 @ %s → %s",
                        action, symbol, quantity, price, sim_id)
            return {
                "order_id": sim_id, "status": "simulated",
                "symbol": symbol, "quantity": quantity, "price": price,
            }

        self._require_connection()
        order = _StockOrder()
        order.Identify = 1
        order.Account = self.account
        order.APCode = 0
        order.TradeKind = 0             # 00:委託單
        order.OrderType = "0"           # 0:ROD
        order.StkCode = symbol
        order.BuySell = "B" if action == "buy" else "S"
        order.OrderQty = int(quantity * 1000)  # 張 → 股

        if order_type == "market" or price is None:
            order.PriceFlag = "M"
            order.Price = 0.0
        else:
            order.PriceFlag = "L"
            order.Price = float(price)

        order.OrderNo = ""
        order.TradeDate = datetime.today().strftime("%Y/%m/%d")
        order.BasketNo = ""
        order.Time_in_force = "0"

        lst = _NetList[_StockOrder]()
        lst.Add(order)

        result = await self._query(
            "SendStockOrder",
            lambda: self._api.SendStockOrder(self.account, lst),
        )
        return self._parse_order_result(result, symbol, quantity, price)

    def _parse_order_result(
        self,
        result: Any,
        symbol: str,
        quantity: int,
        price: float | None,
    ) -> dict:
        try:
            status = result.ResultCount
            items = result.ResultList
            if items.Count > 0:
                item = items[0]
                reply = str(item.ReplyCode)
                return {
                    "order_id": str(item.OrderNO),
                    "reply_code": reply,
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "success": reply == "0000",
                    "error_no": str(item.ErrNO) if reply != "0000" else None,
                    "advisory": str(item.Advisory),
                }
        except Exception as exc:
            logger.warning("下單結果解析失敗: %s", exc)
        return {"order_id": "", "symbol": symbol, "quantity": quantity, "price": price}

    async def cancel_order(self, order_id: str) -> bool:
        if self.simulation:
            logger.info("YuantaBroker [SIM] cancel_order: %s", order_id)
            return True

        self._require_connection()
        order = _StockOrder()
        order.Account = self.account
        order.TradeKind = 4     # 04:取消
        order.OrderNo = order_id
        order.OrderQty = 0
        order.BuySell = ""
        order.StkCode = ""
        order.Price = 0.0
        order.TradeDate = datetime.today().strftime("%Y/%m/%d")
        order.BasketNo = ""
        order.Time_in_force = "0"

        lst = _NetList[_StockOrder]()
        lst.Add(order)

        result = await self._query(
            "SendStockOrder",
            lambda: self._api.SendStockOrder(self.account, lst),
            self._trade_rl,
        )
        try:
            return str(result.ResultCount.MsgCode) == "0001"
        except Exception:
            return False

    # ── 即時訂閱 ─────────────────────────────────────────────────────────────────

    def subscribe_tick(self, symbol: str, callback: Callable[[dict], None]) -> None:
        """訂閱分時 Tick（需已連線登入）。callback 接收每筆 tick dict。"""
        if self.simulation:
            logger.warning("YuantaBroker [SIM] subscribe_tick: 使用輪詢降級 (symbol=%s)", symbol)
            return

        self._require_connection()

        from YuantaOneAPI import StockTick  # type: ignore[import]

        def _handler(raw: Any) -> None:
            try:
                t = raw.Time
                callback({
                    "symbol": str(raw.StkCode),
                    "deal_price": float(raw.DealPrice),
                    "deal_vol": int(raw.DealVol),
                    "buy_price": float(raw.BuyPrice),
                    "sell_price": float(raw.SellPrice),
                    "time": f"{t.bytHour:02d}:{t.bytMin:02d}:{t.bytSec:02d}",
                    "in_out": int(raw.InOutFlag),
                })
            except Exception as exc:
                logger.warning("tick 解析失敗 [%s]: %s", symbol, exc)

        lst = _NetList[StockTick]()
        item = StockTick()
        item.MarketNo = _MarketType.TWSE
        item.StkCode = symbol
        lst.Add(item)

        self._subscribe(
            "SubscribeStockTick",
            _handler,
            lambda: self._api.SubscribeStockTick(self.account, lst),
        )

    def subscribe_real_report(self, callback: Callable[[dict], None]) -> None:
        """訂閱即時回報（委託/成交狀態更新）。"""
        if self.simulation:
            return
        self._require_connection()

        def _handler(raw: Any) -> None:
            try:
                callback({
                    "order_no": str(raw.OrderNo),
                    "symbol": str(raw.CompanyNo),
                    "side": "buy" if str(raw.BS) == "B" else "sell",
                    "qty": int(raw.OrderQty),
                    "price": float(raw.Price),
                    "status": int(raw.OrderStatus),
                })
            except Exception as exc:
                logger.warning("real_report 解析失敗: %s", exc)

        self._subscribe(
            "RR_RealReportMerge",
            _handler,
            lambda: self._api.RR_RealReportMerge(),
        )
