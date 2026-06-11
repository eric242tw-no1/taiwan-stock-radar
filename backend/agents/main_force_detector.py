"""
主力意圖四階段識別（台股版）
四階段：建倉 → 洗盤 → 拉升 → 出貨
台股版：以「官股 + 外資」替代「國家隊」訊號
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_main_force_phase(
    df: pd.DataFrame | None,
    foreign_consecutive: int,   # 正數=連買天數，負數=連賣天數
    gov_stock_signal: str,      # "撐盤介入" | "賣超" | ""
    chip_concentration: float,  # 前五大分點集中度 0-100
) -> dict:
    """
    輸入最近 30-60 根日 K OHLCV + 三大法人訊號，
    回傳 {phase, confidence, signals, risk_note}。
    """
    if df is None or len(df) < 30:
        return {"phase": "不明", "confidence": 0, "signals": ["資料不足，需 30 根以上日K"]}

    closes  = df["close"].values.astype(float)
    volumes = df["volume"].values.astype(float)
    n = len(closes)

    scores: dict[str, tuple[int, list[str]]] = {}

    # ── 建倉：低位 + 外資開始買 + 籌碼集中 ─────────────────────────────
    acc = 0; acc_sig: list[str] = []
    n60 = (closes[-1] / closes[-min(60, n)] - 1) * 100
    if -10 < n60 < 15:
        acc += 20; acc_sig.append(f"近60日漲幅{n60:.1f}%，低位區間")
    if foreign_consecutive >= 3:
        acc += 25; acc_sig.append(f"外資連買{foreign_consecutive}日")
    if chip_concentration >= 50:
        acc += 20; acc_sig.append(f"分點集中度{chip_concentration:.0f}%")
    # 量能溫和放大
    avg_vol = np.mean(volumes[-20:])
    recent_vol = np.mean(volumes[-5:])
    if 1.1 < recent_vol / (avg_vol or 1) < 2.0:
        acc += 15; acc_sig.append("量能溫和放大，吸籌特徵")
    scores["建倉"] = (acc, acc_sig)

    # ── 洗盤：回檔但不破結構 ────────────────────────────────────────────
    wash = 0; wash_sig: list[str] = []
    n5 = (closes[-1] / closes[-min(5, n)] - 1) * 100
    if -8 < n5 < -2:
        wash += 20; wash_sig.append(f"近5日回檔{n5:.1f}%")
    if chip_concentration >= 55:
        wash += 25; wash_sig.append(f"集中度{chip_concentration:.0f}%維持高位，主力未出")
    # 量縮價穩
    if recent_vol < avg_vol * 0.7:
        wash += 20; wash_sig.append("量縮，非恐慌性拋售")
    # 未跌破 20MA
    if n >= 20:
        ma20 = np.mean(closes[-20:])
        if closes[-1] > ma20:
            wash += 15; wash_sig.append("守住20MA，結構完整")
    scores["洗盤"] = (wash, wash_sig)

    # ── 拉升：股價創高 + 外資持續 + 官股護盤 ────────────────────────────
    up = 0; up_sig: list[str] = []
    n20 = (closes[-1] / closes[-min(20, n)] - 1) * 100
    if n20 > 5:
        up += 25; up_sig.append(f"近20日漲幅{n20:.1f}%")
    if foreign_consecutive >= 5:
        up += 20; up_sig.append(f"外資連買{foreign_consecutive}日，持續加碼")
    if gov_stock_signal == "撐盤介入":
        up += 20; up_sig.append("官股護盤確認")
    # 量價齊揚
    if recent_vol > avg_vol * 1.3 and closes[-1] > closes[-2]:
        up += 15; up_sig.append("量價齊揚，主升段特徵")
    scores["拉升"] = (up, up_sig)

    # ── 出貨：高位 + 籌碼鬆散 + 外資轉賣 ───────────────────────────────
    dist = 0; dist_sig: list[str] = []
    if n60 > 30:
        dist += 20; dist_sig.append(f"近60日漲幅{n60:.1f}%，高位風險")
    if foreign_consecutive <= -3:
        dist += 30; dist_sig.append(f"外資連賣{abs(foreign_consecutive)}日")
    if chip_concentration < 30:
        dist += 20; dist_sig.append(f"分點集中度{chip_concentration:.0f}%，籌碼鬆散")
    if gov_stock_signal == "賣超":
        dist += 15; dist_sig.append("官股轉賣，護盤結束")
    # 量大不漲（出貨量）
    if recent_vol > avg_vol * 1.5 and abs(closes[-1] / closes[-2] - 1) < 0.01:
        dist += 15; dist_sig.append("高量低漲，疑似出貨")
    scores["出貨"] = (dist, dist_sig)

    # ── 取最高分階段 ────────────────────────────────────────────────────
    best = max(scores, key=lambda k: scores[k][0])
    score, signals = scores[best]

    if score < 25:
        return {"phase": "不明", "confidence": 0, "signals": ["信號不明確，持續觀察"]}

    risk_notes = {
        "建倉": "主力建倉中，可考慮跟進，停損設近期低點",
        "洗盤": "正常整理，持倉不動，量縮回檔是加碼機會",
        "拉升": "主升段，持股為主，跌破5MA再考慮減碼",
        "出貨": "主力出貨跡象，謹慎減碼，嚴守停損",
    }

    return {
        "phase": best,
        "confidence": min(round(score), 95),
        "signals": signals,
        "risk_note": risk_notes.get(best, ""),
        "all_scores": {k: v[0] for k, v in scores.items()},
    }
