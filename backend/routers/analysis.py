"""
AI 分析 API

GET  /api/analysis/{symbol}          — 取得分析結果（有快取直接回）
POST /api/analysis/{symbol}/refresh  — 強制重新分析（每檔 30 分鐘限一次）
GET  /api/analysis/{symbol}/cooldown — 查詢剩餘冷卻秒數
GET  /api/analysis/{symbol}/context  — 只看 context 原始數據（不呼叫 Claude）
"""
import time
from fastapi import APIRouter, HTTPException
from agents.ai_engine import get_ai_analysis, build_ai_context

router = APIRouter(tags=["analysis"])

REFRESH_COOLDOWN = 30 * 60   # 秒
_last_refresh: dict[str, float] = {}


@router.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    _validate(symbol)
    try:
        return await get_ai_analysis(symbol, force=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analysis/{symbol}/refresh")
async def refresh_analysis(symbol: str):
    _validate(symbol)
    remaining = _cooldown_remaining(symbol)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"刷新冷卻中，請 {remaining // 60} 分 {remaining % 60} 秒後再試",
                "cooldown_seconds": REFRESH_COOLDOWN,
                "remaining_seconds": remaining,
            },
        )
    _last_refresh[symbol] = time.time()
    try:
        return await get_ai_analysis(symbol, force=True)
    except Exception as e:
        _last_refresh.pop(symbol, None)   # 失敗時重置，讓使用者可以重試
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analysis/{symbol}/cooldown")
async def get_cooldown(symbol: str):
    """前端用來顯示倒數計時。"""
    _validate(symbol)
    remaining = _cooldown_remaining(symbol)
    return {
        "symbol": symbol,
        "cooldown_seconds": REFRESH_COOLDOWN,
        "remaining_seconds": remaining,
        "can_refresh": remaining == 0,
    }


def _cooldown_remaining(symbol: str) -> int:
    last = _last_refresh.get(symbol)
    if last is None:
        return 0
    elapsed = int(time.time() - last)
    return max(0, REFRESH_COOLDOWN - elapsed)


@router.get("/api/analysis/{symbol}/context")
async def get_context(symbol: str):
    """只取原始數據，不呼叫 Claude（除錯 / 前端快速顯示用）。"""
    _validate(symbol)
    try:
        return await build_ai_context(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _validate(symbol: str) -> None:
    if not symbol.isdigit() or len(symbol) not in (4, 5, 6):
        raise HTTPException(status_code=400, detail="股票代號格式錯誤（4-6位數字）")
