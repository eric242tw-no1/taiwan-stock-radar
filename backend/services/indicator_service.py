"""
Technical indicator service: RSI / MACD / KD / ATR
- Fetches OHLCV from yfinance for a list of TW tickers
- Calculates indicators with pandas-ta
- Upserts into SQLite stock_indicators_daily + daily_price
- In-memory cache for API reads
"""

import logging
from typing import Optional

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from db import get_conn

logger = logging.getLogger(__name__)

from services.stock_pool_service import get_tickers as _get_pool_tickers

TRACKED_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2412.TW",
    "0050.TW", "2308.TW", "2881.TW", "2382.TW",
]

_cache: dict[str, dict] = {}


def ensure_table():
    pass  # schema managed by schema_sqlite.sql


def _calc_indicators(df: pd.DataFrame) -> Optional[dict]:
    if df is None or len(df) < 30:
        return None

    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    rsi = ta.rsi(df["close"], length=14)
    macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
    stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=9, d=3, smooth_k=3)
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)

    last = df.index[-1]

    def safe(series, idx=-1):
        try:
            v = series.iloc[idx]
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    macd_col = [c for c in (macd_df.columns if macd_df is not None else []) if c.startswith("MACD_") and not c.startswith("MACDs") and not c.startswith("MACDh")]
    sig_col  = [c for c in (macd_df.columns if macd_df is not None else []) if c.startswith("MACDs")]
    hist_col = [c for c in (macd_df.columns if macd_df is not None else []) if c.startswith("MACDh")]
    k_col    = [c for c in (stoch_df.columns if stoch_df is not None else []) if c.startswith("STOCHk")]
    d_col    = [c for c in (stoch_df.columns if stoch_df is not None else []) if c.startswith("STOCHd")]

    ma20_series = df["close"].rolling(20).mean()
    ma20_val    = safe(ma20_series)
    close_val   = safe(df["close"])
    ma20_bias   = round((close_val - ma20_val) / ma20_val * 100, 2) if (ma20_val and close_val) else None

    bias_series = ((df["close"] - ma20_series) / ma20_series * 100).dropna()
    if len(bias_series) >= 20 and ma20_bias is not None:
        bias_pct = round(float((bias_series < ma20_bias).mean() * 100), 1)
    else:
        bias_pct = None

    return {
        "trade_date":  last.date().isoformat() if hasattr(last, "date") else str(last)[:10],
        "close":       close_val,
        "volume":      int(df["volume"].iloc[-1]) if not pd.isna(df["volume"].iloc[-1]) else None,
        "rsi14":       safe(rsi),
        "macd":        safe(macd_df[macd_col[0]]) if macd_col else None,
        "macd_signal": safe(macd_df[sig_col[0]])  if sig_col  else None,
        "macd_hist":   safe(macd_df[hist_col[0]]) if hist_col else None,
        "k":           safe(stoch_df[k_col[0]])   if k_col    else None,
        "d":           safe(stoch_df[d_col[0]])   if d_col    else None,
        "atr14":       safe(atr),
        "ma20":        round(ma20_val, 2) if ma20_val else None,
        "ma20_bias":   ma20_bias,
        "bias_pct":    bias_pct,
    }


def calculate_and_store(tickers: list[str] | None = None):
    if tickers is None:
        tickers = _get_pool_tickers() or TRACKED_TICKERS
    logger.info("indicator job started for %d tickers", len(tickers))

    ind_rows   = []
    price_rows = []

    for ticker in tickers:
        try:
            df_raw = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
            result = _calc_indicators(df_raw)
            if result is None:
                logger.warning("not enough data for %s", ticker)
                continue
            result["ticker"] = ticker
            ind_rows.append(result)
            _cache[ticker] = {**result, "ticker": ticker}
            logger.info("  %s RSI=%.1f ATR=%.1f bias=%.1f%% pct=%.0f",
                        ticker, result["rsi14"] or 0, result["atr14"] or 0,
                        result["ma20_bias"] or 0, result["bias_pct"] or 0)

            # store OHLCV to daily_price (symbol = ticker without .TW suffix)
            symbol = ticker.replace(".TW", "").replace(".TWO", "")
            df = df_raw.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            for ts, row in df.tail(5).iterrows():
                price_rows.append((
                    symbol,
                    ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10],
                    float(row["open"])  if not pd.isna(row["open"])  else None,
                    float(row["high"])  if not pd.isna(row["high"])  else None,
                    float(row["low"])   if not pd.isna(row["low"])   else None,
                    float(row["close"]) if not pd.isna(row["close"]) else None,
                    int(row["volume"])  if not pd.isna(row["volume"]) else None,
                ))
        except Exception as e:
            logger.error("indicator calc failed [%s]: %s", ticker, e)

    if ind_rows or price_rows:
        try:
            conn = get_conn()
            cur = conn.cursor()
            if ind_rows:
                cur.executemany(
                    """
                    INSERT INTO stock_indicators_daily
                        (ticker, trade_date, close, volume,
                         rsi14, macd, macd_signal, macd_hist, k, d, atr14,
                         ma20, ma20_bias, bias_pct, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT (ticker, trade_date) DO UPDATE SET
                        close=excluded.close, volume=excluded.volume,
                        rsi14=excluded.rsi14, macd=excluded.macd,
                        macd_signal=excluded.macd_signal, macd_hist=excluded.macd_hist,
                        k=excluded.k, d=excluded.d, atr14=excluded.atr14,
                        ma20=excluded.ma20, ma20_bias=excluded.ma20_bias,
                        bias_pct=excluded.bias_pct, updated_at=datetime('now')
                    """,
                    [(r["ticker"], r["trade_date"], r["close"], r["volume"],
                      r["rsi14"], r["macd"], r["macd_signal"], r["macd_hist"],
                      r["k"], r["d"], r["atr14"], r["ma20"], r["ma20_bias"], r["bias_pct"])
                     for r in ind_rows],
                )
            if price_rows:
                cur.executemany(
                    """
                    INSERT INTO daily_price (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume
                    """,
                    price_rows,
                )
            conn.commit()
            conn.close()
            logger.info("indicator job done — %d indicators, %d price rows", len(ind_rows), len(price_rows))
        except Exception as e:
            logger.error("indicator DB upsert failed: %s", e)


def load_cache_from_db():
    sql = """
        SELECT s.ticker, s.trade_date, s.close, s.volume,
               s.rsi14, s.macd, s.macd_signal, s.macd_hist, s.k, s.d, s.atr14,
               s.ma20, s.ma20_bias, s.bias_pct
        FROM stock_indicators_daily s
        WHERE s.trade_date = (
            SELECT MAX(trade_date) FROM stock_indicators_daily WHERE ticker = s.ticker
        )
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        for row in cur.fetchall():
            ticker = row["ticker"]
            _cache[ticker] = dict(row)
        conn.close()
        logger.info("indicator cache warmed: %d tickers", len(_cache))
    except Exception as e:
        logger.warning("indicator cache warm-up failed: %s", e)


def get_indicators(ticker: str) -> Optional[dict]:
    return _cache.get(ticker)


def get_all_indicators() -> dict:
    return dict(_cache)
