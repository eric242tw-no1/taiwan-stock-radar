"""
主力意圖四階段分析（規則式，依 design.md D5 規則）

階段：吸籌 / 拉抬 / 出貨 / 打壓
輸入：chip dict（法人籌碼）+ indicators dict（技術指標）
輸出：{phase, confidence, signals}
"""
from __future__ import annotations


def detect_phase(chip: dict, indicators: dict) -> dict:
    """
    chip 鍵（finmind_fetcher _aggregate 輸出）：
      foreign, trust, dealer, date

    indicators 鍵（參考 indicator_service）：
      close, ma20, rsi14, macd_hist, k, d, volume, atr14
    """
    signals: list[str] = []
    scores: dict[str, float] = {"吸籌": 0.0, "拉抬": 0.0, "出貨": 0.0, "打壓": 0.0}

    foreign_net    = float(chip.get("foreign") or 0)
    invest_net     = float(chip.get("trust") or 0)
    volume_ratio   = float(chip.get("volume_ratio") or indicators.get("volume_ratio") or 1.0)
    tdcc_trend     = chip.get("tdcc_trend", 0)   # +1 集中度上升 / -1 下降 / 0 持平

    close = float(indicators.get("close") or 0)
    ma20  = float(indicators.get("ma20")  or 0)
    rsi   = float(indicators.get("rsi14") or 50)
    macd_h = float(indicators.get("macd_hist") or 0)
    foreign_days_sold = int(chip.get("foreign_consecutive_sell_days") or 0)
    limit_down_days   = int(chip.get("consecutive_limit_down") or 0)

    # ── 吸籌：TDCC 集中度連升 3 日 AND 量比 < 0.8 ────────────────
    if tdcc_trend >= 3 and volume_ratio < 0.8:
        scores["吸籌"] += 0.7
        signals.append("TDCC 集中度連升，縮量吸籌中")
    if volume_ratio < 0.6 and rsi < 45:
        scores["吸籌"] += 0.2
        signals.append("低量低 RSI，潛在吸籌跡象")

    # ── 拉抬：收盤 > MA20 AND（外資或投信買超）AND 量比 > 1.5 ─────
    if close > ma20 and (foreign_net > 0 or invest_net > 0) and volume_ratio > 1.5:
        scores["拉抬"] += 0.8
        buyer = "外資" if foreign_net > 0 else "投信"
        signals.append(f"站上 MA20，{buyer}買超，放量拉抬")
    if macd_h > 0 and rsi > 55 and close > ma20:
        scores["拉抬"] += 0.15
        signals.append("MACD 多頭排列，動能轉強")

    # ── 出貨：高檔縮量（量比 < 0.7）AND 籌碼分散（TDCC 下降）──────
    if volume_ratio < 0.7 and tdcc_trend <= -1 and rsi > 60:
        scores["出貨"] += 0.75
        signals.append("高檔縮量，籌碼分散，疑似出貨")
    if foreign_net < 0 and invest_net < 0 and close > ma20:
        scores["出貨"] += 0.2
        signals.append("外資投信同步賣超，高檔出貨訊號")

    # ── 打壓：連續 2 日跌停 OR 外資連賣 5 日以上 ─────────────────
    if limit_down_days >= 2:
        scores["打壓"] += 0.9
        signals.append(f"連續 {limit_down_days} 日跌停，強力打壓")
    if foreign_days_sold >= 5:
        scores["打壓"] += 0.6
        signals.append(f"外資連賣 {foreign_days_sold} 日，持續打壓")
    if rsi < 30 and macd_h < 0:
        scores["打壓"] += 0.1
        signals.append("RSI 超賣區，MACD 死叉，空頭打壓")

    # ── 決策 ───────────────────────────────────────────────────────
    if all(v == 0 for v in scores.values()):
        return {"phase": "觀望", "confidence": 0.0, "signals": ["資料不足，無法判斷"]}

    best_phase = max(scores, key=lambda k: scores[k])
    best_score = scores[best_phase]
    total = sum(scores.values())
    confidence = round(best_score / total, 3) if total > 0 else 0.0

    return {
        "phase": best_phase,
        "confidence": confidence,
        "signals": signals,
        "scores": {k: round(v, 2) for k, v in scores.items()},
    }
