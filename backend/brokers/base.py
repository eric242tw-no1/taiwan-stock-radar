from abc import ABC, abstractmethod
from collections.abc import Callable


class BrokerConnectionError(Exception):
    """券商連線失敗（網路逾時、登入失敗）"""


class BrokerOrderError(Exception):
    """下單或取消委託被拒（資金不足、超過限制等）"""
    def __init__(self, code: int | str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.broker_message = message


class BrokerBase(ABC):
    """抽象券商介面 — 換券商只改實作，不動上層邏輯"""

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict:
        pass

    @abstractmethod
    async def get_positions(self) -> list:
        pass

    @abstractmethod
    async def get_balance(self) -> dict:
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        action: str,           # buy / sell
        order_type: str,       # market / limit / stop
        quantity: int,
        price: float | None = None,
        stop_price: float | None = None,
    ) -> dict:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    async def get_orders(self) -> list:
        pass

    @abstractmethod
    def subscribe_tick(self, symbol: str, callback: Callable[[dict], None]) -> None:
        """訂閱即時 Tick；callback 接收 {price, volume, timestamp} dict。"""
        pass
