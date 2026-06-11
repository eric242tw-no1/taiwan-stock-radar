"""
K 線形態識別 27 種
輸入：最近 10 個交易日 OHLCV DataFrame（pandas）
輸出：偵測到的形態清單 [{"name","type","reliability","desc"}, ...]
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_patterns(df: pd.DataFrame | None) -> list[dict]:
    if df is None or len(df) < 5:
        return []

    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float) if "volume" in df.columns else None
    i = len(df) - 1

    body  = abs(c[i] - o[i])
    upper = h[i] - max(c[i], o[i])
    lower = min(c[i], o[i]) - lo[i]
    total = (h[i] - lo[i]) or 0.001
    is_bull = c[i] >= o[i]

    results: list[dict] = []

    def add(name, typ, rel, desc):
        results.append({"name": name, "type": typ, "reliability": rel, "desc": desc})

    # ── 三K 形態 ─────────────────────────────────────────────────────────

    if i >= 2:
        # 黃昏之星（看跌）
        if (c[i-2] > o[i-2]
                and abs(c[i-1]-o[i-1]) < (h[i-1]-lo[i-1]) * 0.3
                and o[i] < c[i-1] and c[i] < o[i-2]):
            add("黃昏之星", "bearish", "高", "多頭趨勢反轉，建議減碼")

        # 早晨之星（看漲）
        if (c[i-2] < o[i-2]
                and abs(c[i-1]-o[i-1]) < (h[i-1]-lo[i-1]) * 0.3
                and o[i] > c[i-1] and c[i] > o[i-2]):
            add("早晨之星", "bullish", "高", "空頭趨勢反轉，考慮進場")

        # 三白兵（看漲）
        if (c[i]>o[i] and c[i-1]>o[i-1] and c[i-2]>o[i-2]
                and c[i]>c[i-1]>c[i-2] and o[i]>o[i-1]>o[i-2]):
            add("三白兵", "bullish", "高", "連續三陽，多頭強勢確立")

        # 三隻烏鴉（看跌）
        if (c[i]<o[i] and c[i-1]<o[i-1] and c[i-2]<o[i-2]
                and c[i]<c[i-1]<c[i-2]):
            add("三隻烏鴉", "bearish", "高", "連續三陰，空頭強勢確立")

        # 上升三法（看漲）
        if (c[i-2]>o[i-2] and c[i]>o[i]
                and c[i-1]<o[i-1] and c[i-1]>lo[i-2] and c[i-1]<h[i-2]
                and c[i]>c[i-2]):
            add("上升三法", "bullish", "中", "回調整理後多頭續攻")

        # 下降三法（看跌）
        if (c[i-2]<o[i-2] and c[i]<o[i]
                and c[i-1]>o[i-1] and c[i-1]<h[i-2] and c[i-1]>lo[i-2]
                and c[i]<c[i-2]):
            add("下降三法", "bearish", "中", "反彈整理後空頭續跌")

        # 紅三兵（看漲，三陽連漲但上影線短）
        if (c[i]>o[i] and c[i-1]>o[i-1] and c[i-2]>o[i-2]
                and c[i]>c[i-1]>c[i-2]
                and (h[i]-c[i]) < abs(c[i]-o[i])*0.3
                and (h[i-1]-c[i-1]) < abs(c[i-1]-o[i-1])*0.3):
            add("紅三兵", "bullish", "高", "三陽收盤創高，買氣旺盛")

    # ── 雙K 形態 ─────────────────────────────────────────────────────────

    if i >= 1:
        # 陽包陰（看漲）
        if (c[i-1]<o[i-1] and c[i]>o[i]
                and c[i]>o[i-1] and o[i]<c[i-1]):
            add("陽包陰", "bullish", "高", "多方完全吃掉空方，強勢反轉")

        # 陰包陽（看跌）
        if (c[i-1]>o[i-1] and c[i]<o[i]
                and c[i]<o[i-1] and o[i]>c[i-1]):
            add("陰包陽", "bearish", "高", "空方完全吃掉多方，強勢反轉")

        # 母子（孕線）看漲
        if (c[i-1]<o[i-1]
                and c[i]>o[i]
                and h[i]<h[i-1] and lo[i]>lo[i-1]
                and abs(c[i]-o[i]) < abs(c[i-1]-o[i-1])*0.5):
            add("多頭孕線", "bullish", "中", "跌勢中出現小陽，賣壓衰竭")

        # 母子（孕線）看跌
        if (c[i-1]>o[i-1]
                and c[i]<o[i]
                and h[i]<h[i-1] and lo[i]>lo[i-1]
                and abs(c[i]-o[i]) < abs(c[i-1]-o[i-1])*0.5):
            add("空頭孕線", "bearish", "中", "漲勢中出現小陰，買氣衰竭")

        # 穿線（看漲）
        if (c[i-1]<o[i-1]
                and c[i]>o[i]
                and o[i]<lo[i-1]
                and c[i]>(o[i-1]+c[i-1])/2
                and c[i]<o[i-1]):
            add("穿線", "bullish", "中", "低開高收穿過前陰中點，多頭回神")

        # 烏雲蓋頂（看跌）
        if (c[i-1]>o[i-1]
                and c[i]<o[i]
                and o[i]>h[i-1]
                and c[i]<(o[i-1]+c[i-1])/2
                and c[i]>o[i-1]):
            add("烏雲蓋頂", "bearish", "中", "高開低收跌破前陽中點，空頭壓制")

        # 平頂（看跌）
        if abs(h[i]-h[i-1]) < total*0.01 and c[i]<o[i] and c[i-1]>o[i-1]:
            add("平頂", "bearish", "低", "兩K高點相同，壓力明確")

        # 平底（看漲）
        if abs(lo[i]-lo[i-1]) < total*0.01 and c[i]>o[i] and c[i-1]<o[i-1]:
            add("平底", "bullish", "低", "兩K低點相同，支撐明確")

    # ── 單K 形態 ─────────────────────────────────────────────────────────

    # 射擊之星（看跌）
    if upper > body*2 and lower < body*0.5 and body/total < 0.3:
        add("射擊之星", "bearish", "高", "上影線長，賣壓沉重")

    # 錘子線（看漲）
    if lower > body*2 and upper < body*0.5:
        add("錘子線", "bullish", "中", "下影線長，買盤承接力強")

    # 倒錘子（看漲，需前一日為跌）
    if upper > body*2 and lower < body*0.5 and is_bull:
        if i >= 1 and c[i-1] < o[i-1]:
            add("倒錘子", "bullish", "中", "長上影後收陽，反轉訊號")

    # 上吊線（看跌，需前一日為漲）
    if lower > body*2 and upper < body*0.5 and not is_bull:
        if i >= 1 and c[i-1] > o[i-1]:
            add("上吊線", "bearish", "中", "高位長下影，主力誘多")

    # 十字線（中性）
    if body/total < 0.05:
        add("十字線", "neutral", "低", "多空平衡，等待方向確認")

    # 長腳十字（中性）
    if body/total < 0.05 and upper > total*0.3 and lower > total*0.3:
        add("長腳十字", "neutral", "低", "多空激烈交戰，方向未定")

    # 墓碑十字（看跌）
    if body/total < 0.05 and upper > total*0.6 and lower < total*0.05:
        add("墓碑十字", "bearish", "中", "開收同價但拉高遭賣，賣壓強")

    # 蜻蜓十字（看漲）
    if body/total < 0.05 and lower > total*0.6 and upper < total*0.05:
        add("蜻蜓十字", "bullish", "中", "開收同價且低位有承接，買盤強")

    # 大陽線（看漲）
    if is_bull and body/total > 0.8:
        add("大陽線", "bullish", "中", "實體寬大，多頭強勢")

    # 大陰線（看跌）
    if not is_bull and body/total > 0.8:
        add("大陰線", "bearish", "中", "實體寬大，空頭強勢")

    # 紡錘線（中性）
    if 0.1 < body/total < 0.3 and upper > body and lower > body:
        add("紡錘線", "neutral", "低", "上下影線均長，多空猶豫")

    # 量價背離（看跌，需 volume）
    if v is not None and i >= 4:
        price_trend = c[i] > c[i-4]
        vol_trend   = v[i] < np.mean(v[i-4:i])
        if price_trend and vol_trend:
            add("量價背離", "bearish", "中", "股價創高但成交量萎縮，漲勢乏力")

    # 量縮價穩（看漲，底部吸貨）
    if v is not None and i >= 4:
        price_stable = abs(c[i]/c[i-4]-1) < 0.03
        vol_shrink   = v[i] < np.mean(v[i-4:i]) * 0.6
        if price_stable and vol_shrink:
            add("量縮價穩", "bullish", "低", "量縮但股價不跌，底部吸籌")

    return results
