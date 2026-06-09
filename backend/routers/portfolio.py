"""
持倉截圖辨識 API
---
目前模式（B方案）：使用 pytesseract 本地 OCR + 正則解析元大庫存截圖
未來升級：在 .env 加入 ANTHROPIC_API_KEY=sk-ant-xxx 後自動切換為 Claude Vision
"""

import os
import re
import io
import logging

from fastapi import APIRouter, File, UploadFile, HTTPException
from PIL import Image

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# ─── 升級開關：有 key 就用 Claude Vision，沒有就用 pytesseract ───────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_CLAUDE_VISION = bool(ANTHROPIC_API_KEY) and ANTHROPIC_API_KEY not in ("placeholder", "sk-ant-placeholder", "")


# ─── Claude Vision 解析（未來用）────────────────────────────────────────────
async def _parse_with_claude_vision(image_bytes: bytes) -> list[dict]:
    """
    TODO: 等取得 ANTHROPIC_API_KEY 後自動啟用
    呼叫 Claude claude-3-5-haiku-20241022 解析元大庫存截圖
    """
    import anthropic
    import base64

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = """這是一張台灣元大證券的庫存截圖。
請擷取所有持股資訊，以 JSON array 格式回傳，每個物件包含：
- code: 股票代號（4碼數字字串）
- name: 股票名稱
- qty: 庫存張數（整數）
- cost: 平均成本/買入均價（數字）
- current_price: 現價（數字，若無則 null）

只回傳 JSON array，不要其他文字。範例：
[{"code":"2330","name":"台積電","qty":1,"cost":2365.0,"current_price":2390.0}]"""

    msg = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )

    import json
    text = msg.content[0].text.strip()
    # 去掉可能的 markdown code block
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
            detail="pytesseract 未安裝。請先設定 ANTHROPIC_API_KEY 使用 Claude Vision 方案。"
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
