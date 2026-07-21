"""
選股掃描 Agent
資料流：
  TWSE OpenAPI (全市場一次) → 基礎篩選 → FinMind 歷史 (只對候選股) → 技術指標篩選
"""
import os
import asyncio
from datetime import datetime, timedelta
import httpx
import pandas as pd

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
_TWSE_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
_FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# 技術指標篩選時，一次最多查幾檔（省 FinMind 額度）
MAX_TECH_CANDIDATES = 60


async def fetch_market_snapshot() -> pd.DataFrame:
    """
    從 TWSE OpenAPI 取得全市場當日行情（一個 request）。
    回傳欄位：symbol, name, close, open, high, low, volume, change, change_pct
    """
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(_TWSE_ALL_URL)
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame(data)
    # OpenAPI 欄位對應
    df = df.rename(columns={
        "Code":            "symbol",
        "Name":            "name",
        "ClosingPrice":    "close",
        "OpeningPrice":    "open",
        "HighestPrice":    "high",
        "LowestPrice":     "low",
        "TradeVolume":     "volume",   # 股
        "Change":          "change",
    })

    keep = ["symbol", "name", "close", "open", "high", "low", "volume", "change"]
    df = df[[c for c in keep if c in df.columns]].copy()

    # 轉數值，非數值（ETF 特殊欄位等）填 NaN 後濾掉
    for col in ["close", "open", "high", "low", "volume", "change"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

    df = df.dropna(subset=["close", "volume"])
    df = df[df["close"] > 0]

    # 張 = 股 / 1000
    df["volume_lot"] = (df["volume"] / 1000).astype(int)

    # 漲跌幅 %（以收盤推算昨收）
    df["prev_close"] = df["close"] - df["change"]
    df["change_pct"] = df.apply(
        lambda r: round(r["change"] / r["prev_close"] * 100, 2) if r["prev_close"] > 0 else 0,
        axis=1,
    )

    return df.reset_index(drop=True)


def apply_basic_filters(df: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    """
    criteria 可用欄位：
      min_change_pct  漲幅下限 %
      max_change_pct  漲幅上限 %
      min_volume_lot  成交量下限（張）
      min_price       最低股價
      max_price       最高股價
    """
    if (v := criteria.get("min_change_pct")) is not None:
        df = df[df["change_pct"] >= v]
    if (v := criteria.get("max_change_pct")) is not None:
        df = df[df["change_pct"] <= v]
    if (v := criteria.get("min_volume_lot")) is not None:
        df = df[df["volume_lot"] >= v]
    if (v := criteria.get("min_price")) is not None:
        df = df[df["close"] >= v]
    if (v := criteria.get("max_price")) is not None:
        df = df[df["close"] <= v]
    return df.copy()


async def apply_tech_filters(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """
    strategy:
      "ma20_breakout"   — 今日收盤突破 MA20，且成交量 > 5 日均量 1.5 倍
      "rsi_oversold"    — RSI(14) 由下往上穿越 30
      "high_60d"        — 創近 60 日收盤新高
      "momentum_20d"    — 近 20 日報酬率 > 10%（動能因子）
      "foreign_consec"  — 外資連買 ≥ 3 日（籌碼因子）
    只對前 MAX_TECH_CANDIDATES 檔計算（依成交量排序）
    """
    if strategy not in ("ma20_breakout", "rsi_oversold", "high_60d", "momentum_20d", "foreign_consec"):
        return df

    candidates = df.nlargest(MAX_TECH_CANDIDATES, "volume_lot")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    tasks = [_fetch_history(sym, start_date) for sym in candidates["symbol"]]
    histories = await asyncio.gather(*tasks, return_exceptions=True)

    passed = []
    for sym, hist in zip(candidates["symbol"], histories):
        if isinstance(hist, Exception) or hist is None or len(hist) < 25:
            continue
        if strategy == "ma20_breakout" and _check_ma20_breakout(hist):
            passed.append(sym)
        elif strategy == "rsi_oversold" and _check_rsi_oversold(hist):
            passed.append(sym)
        elif strategy == "high_60d" and _check_high_60d(hist):
            passed.append(sym)
        elif strategy == "momentum_20d" and _check_momentum_20d(hist):
            passed.append(sym)
        elif strategy == "foreign_consec" and await _check_foreign_consec(sym):
            passed.append(sym)

    return df[df["symbol"].isin(passed)].copy()


# ── 技術指標判斷 ──────────────────────────────────────────

def _check_ma20_breakout(hist: pd.DataFrame) -> bool:
    if len(hist) < 22:
        return False
    close = hist["close"]
    vol = hist["volume"]
    ma20 = close.rolling(20).mean()
    vol_ma5 = vol.rolling(5).mean()
    # 今日突破且昨日未突破
    return (
        close.iloc[-1] > ma20.iloc[-1]
        and close.iloc[-2] <= ma20.iloc[-2]
        and vol.iloc[-1] > vol_ma5.iloc[-1] * 1.5
    )


def _check_rsi_oversold(hist: pd.DataFrame) -> bool:
    if len(hist) < 16:
        return False
    from factor_engine import technical as fe_tech
    factors = fe_tech.compute("", hist)
    if factors.rsi_14 is None:
        return False
    rsi_prev = _calc_rsi(hist["close"], 14).iloc[-2]
    return factors.rsi_14 > 30 and float(rsi_prev) <= 30


def _check_momentum_20d(hist: pd.DataFrame) -> bool:
    if len(hist) < 22:
        return False
    close = hist["close"]
    ret_20d = (close.iloc[-1] - close.iloc[-21]) / close.iloc[-21] * 100
    return ret_20d > 10


def _check_high_60d(hist: pd.DataFrame) -> bool:
    if len(hist) < 2:
        return False
    recent = hist.tail(60)
    return hist["close"].iloc[-1] >= recent["close"].max()


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


# ── 籌碼因子：外資連買 ────────────────────────────────────

async def _check_foreign_consec(symbol: str, min_days: int = 3) -> bool:
    """外資連買 ≥ min_days 日。"""
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    params = {
        "dataset": "TaiwanStockInstitutionalInvestors",
        "data_id": symbol,
        "start_date": start_date,
        "token": FINMIND_TOKEN,
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(_FINMIND_URL, params=params)
        rows = r.json().get("data", [])
        if not rows:
            return False
        chip = pd.DataFrame(rows)
        chip["buy"]  = pd.to_numeric(chip["buy"],  errors="coerce").fillna(0)
        chip["sell"] = pd.to_numeric(chip["sell"], errors="coerce").fillna(0)
        chip["net"]  = chip["buy"] - chip["sell"]
        foreign = chip[chip["name"].str.contains("外資", na=False)].sort_values("date")
        consec = 0
        for v in reversed(foreign["net"].tolist()):
            if v > 0:
                consec += 1
            else:
                break
        return consec >= min_days
    except Exception:
        return False


# ── FinMind 歷史資料 ──────────────────────────────────────

async def _fetch_history(symbol: str, start_date: str) -> pd.DataFrame | None:
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": symbol,
        "start_date": start_date,
        "token": FINMIND_TOKEN,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(_FINMIND_URL, params=params)
        records = r.json().get("data", [])
        if not records:
            return None
        df = pd.DataFrame(records)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df.get("Trading_Volume", df.get("volume", 0)), errors="coerce")
        return df.dropna(subset=["close"])
    except Exception:
        return None
