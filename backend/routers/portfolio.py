"""
持倉追蹤 API
---
CRUD: GET/POST /api/portfolio, PUT/DELETE /api/portfolio/{id}
截圖辨識: POST /api/portfolio/parse-screenshot
"""

import os
import re
import io
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from PIL import Image

from services.portfolio_service import (
    list_holdings, add_holding, update_holding, delete_holding,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ─── Pydantic models ─────────────────────────────────────────────────────────

class HoldingIn(BaseModel):
    code: str
    name: str = ""
    qty: int
    cost: float
    buy_date: Optional[str] = None
    note: str = ""


# ─── CRUD endpoints ──────────────────────────────────────────────────────────

@router.get("")
async def get_portfolio():
    return {"holdings": list_holdings()}


@router.post("", status_code=201)
async def create_holding(body: HoldingIn):
    row = add_holding(body.code, body.name, body.qty, body.cost, body.buy_date, body.note)
    return row


@router.put("/{holding_id}")
async def edit_holding(holding_id: int, body: HoldingIn):
    row = update_holding(holding_id, body.code, body.name, body.qty, body.cost, body.buy_date, body.note)
    if row is None:
        raise HTTPException(status_code=404, detail="持倉不存在")
    return row


@router.delete("/{holding_id}")
async def remove_holding(holding_id: int):
    ok = delete_holding(holding_id)
    if not ok:
        raise HTTPException(status_code=404, detail="持倉不存在")
    return {"deleted": holding_id}


# ─── Yuanta 真實資料 endpoints (Change D) ────────────────────────────────────

@router.get("/positions")
async def get_yuanta_positions():
    """
    從元大 API 取得即時持倉列表。
    simulation 模式回傳空列表 + simulation badge。
    """
    from main import _broker
    simulation = getattr(_broker, "simulation", True)
    try:
        positions = await _broker.get_positions()
        return {
            "simulation": simulation,
            "positions": positions,
            "updated_at": _tw_now(),
            "error": None,
        }
    except Exception as exc:
        logger.error("get_yuanta_positions failed: %s", exc)
        return {
            "simulation": simulation,
            "positions": [],
            "updated_at": _tw_now(),
            "error": str(exc),
        }


@router.get("/summary")
async def get_yuanta_summary():
    """
    從元大 API 取得帳戶摘要（總市值、現金、保證金使用率）。
    simulation 模式回傳 mock 資料。
    """
    from main import _broker
    simulation = getattr(_broker, "simulation", True)
    try:
        balance = await _broker.get_balance()
        return {
            "simulation": simulation,
            "total_value": balance.get("total_value", 0),
            "cash": balance.get("cash", 0),
            "margin_usage": balance.get("margin_usage", 0),
            "updated_at": _tw_now(),
            "error": None,
        }
    except Exception as exc:
        logger.error("get_yuanta_summary failed: %s", exc)
        return {
            "simulation": simulation,
            "total_value": 0,
            "cash": 0,
            "margin_usage": 0,
            "updated_at": _tw_now(),
            "error": str(exc),
        }


def _tw_now() -> str:
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

# ─── 升級開關：有 OpenAI key 優先，其次 Groq，沒有就用 pytesseract ──────────
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USE_CLAUDE_VISION = bool(_OPENAI_API_KEY) or bool(_GROQ_API_KEY)


# ─── Vision 解析（OpenAI GPT-4o 優先，fallback Groq）────────────────────────
async def _parse_with_claude_vision(image_bytes: bytes) -> list[dict]:
    import base64, json
    import httpx

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    prompt = """This is a screenshot from Yuanta Securities (元大證券) Taiwan stock portfolio app.

The table columns are: 名稱(name) | 平均成本(avg cost) | 庫存股數(shares) | 現股當沖(day trade) | 損益(P&L)

Extract ALL stock positions shown. Return ONLY a JSON array with no other text:
[{"code":"2330","name":"台積電","qty":1,"cost":2365.0,"current_price":2390.0}]

Rules:
- code: 4-digit Taiwan stock code (find it near the stock name, or infer from name)
- qty: 庫存股數 divided by 1000 = lots/張 (e.g. 11000 shares = 11張)
- cost: 平均成本 column value (number only)
- current_price: if visible, otherwise null
- Include every row in the table"""

    if _OPENAI_API_KEY:
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = _OPENAI_API_KEY
        model = "openai/gpt-4o"
    else:
        api_url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = _GROQ_API_KEY
        model = "meta-llama/llama-4-scout-17b-16e-instruct"

    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        r.raise_for_status()

    text = r.json()["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ─── pytesseract 本地 OCR 解析（B方案）─────────────────────────────────────
def _parse_with_tesseract(image_bytes: bytes) -> list[dict]:
    """
    本地 OCR 解析元大庫存截圖
    元大庫存頁格式：股票代號 | 股票名稱 | 庫存股數 | 平均成本 | 現值
    """
    try:
        import pytesseract
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="pytesseract 未安裝。請先設定 LOCAL_AI_API_KEY 使用 DeepSeek Vision 方案。"
        )

    img = Image.open(io.BytesIO(image_bytes))

    # 放大提升 OCR 精準度
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)

    # 強制繁體中文 + 英數字
    text = pytesseract.image_to_string(img, lang="chi_tra+eng")
    logger.info("OCR raw text:\n%s", text)

    return _parse_yuanta_text(text)


def _parse_yuanta_text(text: str) -> list[dict]:
    """
    從 OCR 文字中解析元大庫存格式
    支援格式：
      2330  台積電  1,000  2,365.00  2,390.00
      或各欄位在不同行的情況
    """
    results = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 台股代號：4碼數字
    code_pattern = re.compile(r"\b(\d{4})\b")
    # 金額：可能有逗號分隔，1~6位整數 + 可選小數
    price_pattern = re.compile(r"[\d,]+\.?\d*")

    i = 0
    while i < len(lines):
        line = lines[i]
        m = code_pattern.search(line)
        if m:
            code = m.group(1)
            # 跳過非股票代號（如郵遞區號等）
            if int(code) < 1000 or int(code) > 9999:
                i += 1
                continue

            # 嘗試從同行或下幾行抓數字
            context = " ".join(lines[i:i+4])
            nums = price_pattern.findall(context)
            nums = [float(n.replace(",", "")) for n in nums if n.replace(",", "").replace(".", "").isdigit()]

            # 移除代號本身
            nums = [n for n in nums if n != float(code)]

            # 嘗試抓名稱（代號旁邊的中文）
            name_m = re.search(r"[一-鿿]{2,6}", context)
            name = name_m.group(0) if name_m else f"股票{code}"

            # 元大格式：庫存股數、平均成本、現值
            qty = None
            cost = None
            current_price = None

            if len(nums) >= 3:
                # 股數通常是整數且較大（1000股=1張）
                qty_candidates = [n for n in nums if n >= 1000 and n == int(n)]
                if qty_candidates:
                    qty_shares = int(qty_candidates[0])
                    qty = qty_shares // 1000  # 轉換為張數
                    remaining = [n for n in nums if n != qty_shares]
                    if len(remaining) >= 2:
                        cost = remaining[0]
                        current_price = remaining[1]
                    elif len(remaining) == 1:
                        cost = remaining[0]
            elif len(nums) == 2:
                cost = nums[0]
                current_price = nums[1]
                qty = 1

            if code and cost:
                results.append({
                    "code": code,
                    "name": name,
                    "qty": qty or 1,
                    "cost": cost,
                    "current_price": current_price,
                })

        i += 1

    return results


# ─── API Endpoint ────────────────────────────────────────────────────────────
@router.post("/parse-screenshot")
async def parse_screenshot(file: UploadFile = File(...)):
    """
    上傳元大庫存截圖，自動解析持倉資訊

    - 有 ANTHROPIC_API_KEY：使用 Claude Vision（高精準度）
    - 無 API Key：使用 pytesseract 本地 OCR

    回傳：解析出的持倉列表，可直接匯入持倉追蹤
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="請上傳圖片檔案（PNG/JPG）")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB 上限
        raise HTTPException(status_code=400, detail="圖片不能超過 10MB")

    method = "claude_vision" if USE_CLAUDE_VISION else "tesseract_ocr"
    logger.info("解析截圖，使用方案：%s", method)

    try:
        if USE_CLAUDE_VISION:
            positions = await _parse_with_claude_vision(image_bytes)
        else:
            positions = _parse_with_tesseract(image_bytes)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("截圖解析失敗：%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"解析失敗：{str(e)}")

    return {
        "method": method,
        "count": len(positions),
        "positions": positions,
        "note": "請確認解析結果後再匯入，OCR 可能有誤差" if method == "tesseract_ocr" else "Claude Vision 解析完成",
    }


@router.get("/parse-screenshot/status")
async def parse_status():
    """查詢目前使用哪種解析方案"""
    return {
        "mode": "claude_vision" if USE_CLAUDE_VISION else "tesseract_ocr",
        "api_key_configured": USE_CLAUDE_VISION,
        "upgrade_hint": "在 .env 加入 ANTHROPIC_API_KEY=sk-ant-xxx 即可升級為 Claude Vision",
    }
