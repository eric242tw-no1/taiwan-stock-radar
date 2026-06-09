"""
台股產業指數抓取
資料來源：TWSE afterTrading MI_INDEX（type=IND）tables[0]
盤後資料，每日收盤後更新
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, Any] = {"sectors": None, "updated_at": None}

# TWSE 類股名稱 → 顯示簡稱（用 startswith 匹配）
SECTOR_MAP: list[tuple[str, str]] = [
    ("半導體類",        "半導體"),
    ("電腦及週邊設備類","電腦週邊"),
    ("數位雲端類",      "數位雲端"),
    ("光電類",          "光電"),
    ("通信網路類",      "通訊"),
    ("電子零組件類",    "零組件"),
    ("電子通路類",      "電通路"),
    ("其他電子類",      "其他電子"),
    ("電子工業類",      "電子"),
    ("金融保險類",      "金融"),
    ("航運類",          "航運"),
    ("建材營造類",      "建材"),
    ("生技醫療類",      "生技"),
    ("綠能環保類",      "綠能"),
    ("鋼鐵類",          "鋼鐵"),
    ("化學類",          "化學"),
    ("塑膠類",          "塑膠"),
    ("食品類",          "食品"),
]

# 最多顯示的產業數
MAX_SECTORS = 16


def _match_label(name: str) -> str | None:
    for prefix, label in SECTOR_MAP:
        if name.startswith(prefix):
            return label
    return None


def fetch_sectors() -> list[dict]:
    """
    Fetch TWSE industry index change percentages.
    Returns list of {label, chg} up to MAX_SECTORS.
    """
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                params={"response": "json", "type": "IND"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()

        tables = data.get("tables", [])
        if not tables:
            return []

        table = tables[0]
        fields = table.get("fields", [])
        rows   = table.get("data",   [])

        # 找欄位索引
        try:
            name_idx = fields.index("指數")
            chg_idx  = fields.index("漲跌百分比(%)")
        except ValueError:
            logger.warning("TWSE MI_INDEX fields changed: %s", fields)
            return []

        # 依 SECTOR_MAP 順序收集（避免重複）
        seen: set[str] = set()
        result: list[dict] = []

        for prefix, label in SECTOR_MAP:
            if len(result) >= MAX_SECTORS:
                break
            for row in rows:
                name = row[name_idx]
                if name.startswith(prefix) and label not in seen:
                    try:
                        chg = round(float(row[chg_idx].replace(",", "")), 2)
                    except (ValueError, IndexError):
                        continue
                    result.append({"label": label, "chg": chg})
                    seen.add(label)
                    break

        with _lock:
            _cache["sectors"] = result
            _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("sectors refreshed: %d industries", len(result))
        return result

    except Exception as e:
        logger.error("fetch_sectors failed: %s", e)
        return []


def get_cached_sectors() -> list[dict]:
    with _lock:
        data = _cache.get("sectors")
    if data is not None:
        return data
    return fetch_sectors()
