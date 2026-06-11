import os

import httpx

from brokers.base import BrokerBase


class YuantaBroker(BrokerBase):
    """元大證券 API 實作（模擬/正式由 YUANTA_SIMULATION 控制）"""

    def __init__(self):
        self.base_url = os.getenv("YUANTA_BASE_URL", "")
        self.api_key = os.getenv("YUANTA_API_KEY", "")
        self.account = os.getenv("YUANTA_ACCOUNT", "")
        self.simulation = os.getenv("YUANTA_SIMULATION", "true") == "true"
        self._client = httpx.AsyncClient(timeout=10)

    # ── read-only ──────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        r = await self._client.get(
            f"{self.base_url}/quote/{symbol}",
            headers={"X-API-KEY": self.api_key},
        )
        r.raise_for_status()
        return r.json()

    async def get_positions(self) -> list:
        r = await self._client.get(
            f"{self.base_url}/positions",
            params={"account": self.account},
            headers={"X-API-KEY": self.api_key},
        )
        r.raise_for_status()
        return r.json()

    async def get_balance(self) -> dict:
        r = await self._client.get(
            f"{self.base_url}/balance",
            params={"account": self.account},
            headers={"X-API-KEY": self.api_key},
        )
        r.raise_for_status()
        return r.json()

    async def get_orders(self) -> list:
        r = await self._client.get(
            f"{self.base_url}/orders",
            params={"account": self.account},
            headers={"X-API-KEY": self.api_key},
        )
        r.raise_for_status()
        return r.json()

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
        payload = {
            "account": self.account,
            "symbol": symbol,
            "bs_flag": "B" if action == "buy" else "S",
            "order_type": self._map_order_type(order_type),
            "quantity": quantity * 1000,  # 張 → 股
            "price": str(price) if price else "0",
            "stop_price": str(stop_price) if stop_price else "0",
            "simulation": self.simulation,
        }
        r = await self._client.post(
            f"{self.base_url}/order",
            json=payload,
            headers={"X-API-KEY": self.api_key},
        )
        r.raise_for_status()
        return r.json()

    async def cancel_order(self, order_id: str) -> bool:
        r = await self._client.delete(
            f"{self.base_url}/order/{order_id}",
            headers={"X-API-KEY": self.api_key},
        )
        return r.status_code == 200

    # ── internal ───────────────────────────────────────────────────────────

    def _map_order_type(self, t: str) -> str:
        return {"market": "MKT", "limit": "LMT", "stop": "STP"}.get(t, "MKT")
