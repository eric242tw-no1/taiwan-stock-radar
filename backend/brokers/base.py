from abc import ABC, abstractmethod


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
