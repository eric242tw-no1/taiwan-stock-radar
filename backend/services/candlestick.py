"""
K 線形態識別（純 Python + numpy，不依賴 TA-Lib）
detect(bars) 接收最近 N 根 K 棒（list of dict: open/high/low/close），
回傳當前偵測到的形態名稱列表。
"""
from __future__ import annotations
import numpy as np

Bar = dict  # {"open": float, "high": float, "low": float, "close": float}


def detect(bars: list[Bar]) -> list[str]:
    """偵測 bars 最新一組 K 棒的形態，回傳中文形態名稱列表。"""
    if len(bars) < 3:
        return []
    patterns: list[str] = []
    b = bars  # alias

    # ── 單根形態 ──────────────────────────────────────────────
    patterns += _single(b[-1], b[-2] if len(b) >= 2 else None)

    # ── 雙根形態 ──────────────────────────────────────────────
    if len(b) >= 2:
        patterns += _double(b[-2], b[-1])

    # ── 三根形態 ──────────────────────────────────────────────
    if len(b) >= 3:
        patterns += _triple(b[-3], b[-2], b[-1])

    return patterns


# ── 輔助 ──────────────────────────────────────────────────────────────────────

def _body(bar: Bar) -> float:
    return abs(bar["close"] - bar["open"])

def _range(bar: Bar) -> float:
    return bar["high"] - bar["low"]

def _upper(bar: Bar) -> float:
    return bar["high"] - max(bar["open"], bar["close"])

def _lower(bar: Bar) -> float:
    return min(bar["open"], bar["close"]) - bar["low"]

def _bull(bar: Bar) -> bool:
    return bar["close"] > bar["open"]

def _bear(bar: Bar) -> bool:
    return bar["close"] < bar["open"]

def _mid(bar: Bar) -> float:
    return (max(bar["open"], bar["close"]) + min(bar["open"], bar["close"])) / 2

def _is_doji(bar: Bar) -> bool:
    r = _range(bar)
    return r > 0 and _body(bar) <= r * 0.1


# ── 單根 9 種 ─────────────────────────────────────────────────────────────────

def _single(c: Bar, p: Bar | None) -> list[str]:
    result = []
    body = _body(c)
    upper = _upper(c)
    lower = _lower(c)
    rng = _range(c)
    if rng == 0:
        return result

    # 十字星類（body 極小）
    if body <= rng * 0.1:
        # 墓碑十字：body≈0，上影長，下影≈0
        if upper >= rng * 0.6 and lower <= rng * 0.05:
            result.append("墓碑十字")
        # 蜻蜓十字：body≈0，下影長，上影≈0
        elif lower >= rng * 0.6 and upper <= rng * 0.05:
            result.append("蜻蜓十字")
        # 長十字：body≈0，上下影均長
        elif upper >= rng * 0.3 and lower >= rng * 0.3:
            result.append("長十字")
        else:
            result.append("十字星")
        return result  # 十字星不再判斷其他單根

    # 紡錘：小 body，上下影均存在
    if body <= rng * 0.3 and upper >= rng * 0.15 and lower >= rng * 0.15:
        result.append("紡錘")
        return result

    # 錘子 / 上吊：下影 >= 2x body，上影 <= 0.1x body
    if lower >= 2 * body and upper <= body * 0.3:
        if p and _bear(p):
            result.append("錘子")
        else:
            result.append("上吊")

    # 倒錘子 / 流星：上影 >= 2x body，下影 <= 0.1x body
    elif upper >= 2 * body and lower <= body * 0.3:
        if p and _bear(p):
            result.append("倒錘子")
        else:
            result.append("流星")

    return result


# ── 雙根 9 種 ─────────────────────────────────────────────────────────────────

def _double(p: Bar, c: Bar) -> list[str]:
    result = []
    p_body = _body(p)
    c_body = _body(c)
    if p_body == 0 or c_body == 0:
        return result

    p_top = max(p["open"], p["close"])
    p_bot = min(p["open"], p["close"])
    c_top = max(c["open"], c["close"])
    c_bot = min(c["open"], c["close"])

    # 多頭吞噬
    if _bear(p) and _bull(c) and c["open"] < p["close"] and c["close"] > p["open"]:
        result.append("多頭吞噬")

    # 空頭吞噬
    elif _bull(p) and _bear(c) and c["open"] > p["close"] and c["close"] < p["open"]:
        result.append("空頭吞噬")

    # 穿頭破腳：前黑後白，白棒收盤 > 黑棒中點
    if _bear(p) and _bull(c) and c["open"] < p["low"] and c["close"] > _mid(p):
        result.append("穿頭破腳")

    # 烏雲罩頂：前白後黑，黑棒開盤 > 白棒最高，收盤 < 白棒中點
    if _bull(p) and _bear(c) and c["open"] > p["high"] and c["close"] < _mid(p):
        result.append("烏雲罩頂")

    # 母子線（陽）：前大黑，後小陽在前棒 body 內
    if _bear(p) and _bull(c) and c_top < p_top and c_bot > p_bot and c_body < p_body * 0.5:
        result.append("母子線(陽)")

    # 母子線（陰）：前大陽，後小陰在前棒 body 內
    if _bull(p) and _bear(c) and c_top < p_top and c_bot > p_bot and c_body < p_body * 0.5:
        result.append("母子線(陰)")

    # 平頂：兩棒最高相近，前陽後陰
    if _bull(p) and _bear(c) and abs(p["high"] - c["high"]) <= _range(p) * 0.02:
        result.append("平頂")

    # 平底：兩棒最低相近，前陰後陽
    if _bear(p) and _bull(c) and abs(p["low"] - c["low"]) <= _range(p) * 0.02:
        result.append("平底")

    # 切入：前大黑，後小陽收盤接近前棒收盤（在前棒低點附近）
    if _bear(p) and _bull(c) and abs(c["close"] - p["close"]) <= p_body * 0.1:
        result.append("切入")

    return result


# ── 三根 9 種 ─────────────────────────────────────────────────────────────────

def _triple(a: Bar, b: Bar, c: Bar) -> list[str]:
    result = []

    a_body = _body(a)
    b_body = _body(b)
    c_body = _body(c)

    # 晨星：大黑 + 小星（跳空向下） + 大白收過 a 中點
    if (_bear(a) and a_body > 0 and b_body < a_body * 0.4
            and _bull(c) and c["close"] > _mid(a)):
        result.append("晨星")

    # 夜星：大白 + 小星（跳空向上） + 大黑收過 a 中點
    if (_bull(a) and a_body > 0 and b_body < a_body * 0.4
            and _bear(c) and c["close"] < _mid(a)):
        result.append("夜星")

    # 棄嬰：星形+雙向跳空（gap from a to b AND b to c）
    if _is_doji(b):
        gap_ab = b["high"] < a["low"] or b["low"] > a["high"]
        gap_bc = c["high"] < b["low"] or c["low"] > b["high"]
        if gap_ab and gap_bc:
            if _bear(a) and _bull(c):
                result.append("棄嬰(看漲)")
            elif _bull(a) and _bear(c):
                result.append("棄嬰(看跌)")

    # 三白兵：連三根大陽，每根開在前棒 body 中，收近高點
    if (all(_bull(x) for x in [a, b, c])
            and b["open"] > a["open"] and b["open"] < a["close"]
            and c["open"] > b["open"] and c["open"] < b["close"]
            and _upper(c) <= c_body * 0.3):
        result.append("三白兵")

    # 三黑鴉：連三根大陰
    if (all(_bear(x) for x in [a, b, c])
            and b["open"] < a["open"] and b["open"] > a["close"]
            and c["open"] < b["open"] and c["open"] > b["close"]
            and _lower(c) <= c_body * 0.3):
        result.append("三黑鴉")

    # 紅三兵（Rising Three Methods）：大陽 + 三小熊在 a body 內 + 大陽突破
    # 此處用3根簡化：大陽 + 小黑回測 + 大陽創高
    if (_bull(a) and _bear(b) and _bull(c)
            and b["close"] > a["open"] and b["close"] < a["close"]
            and c["close"] > a["close"] and c_body > b_body):
        result.append("紅三兵")

    # 黑三兵（Falling Three Methods）
    if (_bear(a) and _bull(b) and _bear(c)
            and b["close"] < a["open"] and b["close"] > a["close"]
            and c["close"] < a["close"] and c_body > b_body):
        result.append("黑三兵")

    # 上升三法：同紅三兵，別名
    # 下降三法：同黑三兵，別名（跳過重複回報）

    return result


# ── 批次偵測（給 OHLCV DataFrame 或 list 用）────────────────────────────────

def detect_from_ohlcv(ohlcv_rows: list[dict]) -> list[str]:
    """
    ohlcv_rows: list of dict with keys Open/High/Low/Close (yfinance 格式)
    正規化 key 後轉交 detect()
    """
    bars = []
    for r in ohlcv_rows:
        bars.append({
            "open":  float(r.get("Open") or r.get("open") or 0),
            "high":  float(r.get("High") or r.get("high") or 0),
            "low":   float(r.get("Low")  or r.get("low")  or 0),
            "close": float(r.get("Close") or r.get("close") or 0),
        })
    return detect(bars)
