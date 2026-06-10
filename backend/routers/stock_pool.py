"""
Stock pool CRUD API
GET    /api/stock-pool          — list all entries
POST   /api/stock-pool          — add / re-enable a ticker
DELETE /api/stock-pool/{symbol} — remove a ticker
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.stock_pool_service import get_pool, add_stock, remove_stock

router = APIRouter(prefix="/api/stock-pool", tags=["stock-pool"])


class AddRequest(BaseModel):
    symbol: str
    name: str = ""


@router.get("")
def list_pool():
    return {"stocks": get_pool(enabled_only=False)}


@router.post("", status_code=201)
def add_to_pool(body: AddRequest):
    return add_stock(body.symbol, body.name)


@router.delete("/{symbol}")
def delete_from_pool(symbol: str):
    if not remove_stock(symbol):
        raise HTTPException(status_code=404, detail="Symbol not found in pool")
    return {"deleted": symbol.upper()}
