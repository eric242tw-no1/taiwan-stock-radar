"""
Technical indicator service: RSI / MACD / KD / ATR
- Fetches OHLCV from yfinance for a list of TW tickers
- Calculates indicators with pandas-ta
- Upserts into PostgreSQL stock_indicators_daily
- In-memory cache for API reads
"""

import logging
import os
from datetime import date, datetime
from typing import Optional

import pandas as pd
import pandas_ta as ta
import psycopg2
import psycopg2.extras
import yfinance as yf

logger = logging.getLogger(__name__)

from services.stock_pool_service import get_tickers as _get_pool_tickers

# ── Ticker list ──────────────────────────────────────────────────────────────
# Kept as fallback if DB is unavailable at import time; runtime jobs use get_tickers().
TRACKED_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2412.TW",
    "0050.TW", "2308.TW", "2881.TW", "2382.TW",
]

# ── In-memory cache {ticker: dict} ───────────────────────────────────────────
_cache: dict[str, dict] = {}


def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "stockradar"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
    )


def ensure_table():
    """Create stock_indicators_daily and daily_price if they don't exist."""
    ddl_indicators = """
    CREATE TABLE IF NOT EXISTS stock_indicators_daily (
        ticker        VARCHAR(16)  NOT NULL,
        trade_date    DATE         NOT NULL,
        close         NUMERIC(12,4),
        volume        BIGINT,
        rsi14         NUMERIC(8,4),
        macd          NUMERIC(12,6),
        macd_signal   NUMERIC(12,6),
        macd_hist     NUMERIC(12,6),
        k             NUMERIC(8,4),
        d             NUMERIC(8,4),
        atr14         NUMERIC(12,6),
        ma20          NUMERIC(12,4),
        ma20_bias     NUMERIC(8,4),
        bias_pct      NUMERIC(8,4),
        updated_at    TIMESTAMP    DEFAULT NOW(),
        PRIMARY KEY (ticker, trade_date)
    );
    ALTER TABLE stock_indicators_daily
        ADD COLUMN IF NOT EXISTS ma20       NUMERIC(12,4),
        ADD COLUMN IF NOT EXISTS ma20_bias  NUMERIC(8,4),
        ADD COLUMN IF NOT EXISTS bias_pct   NUMERIC(8,4);
    """
    ddl_price = """
    CREATE TABLE IF NOT EXISTS daily_price (
        ticker      VARCHAR(16)  NOT NULL,
        trade_date  DATE         NOT NULL,
        open        NUMERIC(12,4),
        high        NUMERIC(12,4),
        low         NUMERIC(12,4),
        close       NUMERIC(12,4),
        volume      BIGINT,
        PRIMARY KEY (ticker, trade_date)
    );
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(ddl_indicators)
            cur.execute(ddl_price)
            conn.commit()
        logger.info("stock_indicators_daily + daily_price tables ready")
    except Exception as e:
        logger.error("ensure_table failed: %s", e)


def _calc_indicators(df: pd.DataFrame) -> Optional[dict]:
    """Return latest indicator dict from OHLCV DataFrame, or None if insufficient data."""
    if df is None or len(df) < 30:
        return None

    df = df.copy()
    # yfinance >=0.2.x may return MultiIndex columns ('Close', ticker) — flatten to lowercase
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    # RSI(14)
    rsi = ta.rsi(df["close"], length=14)

    # MACD(12,26,9)
    macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)

    # Stochastic KD(9,3,3)
    stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=9, d=3, smooth_k=3)

    # ATR(14)
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

    # MA20 乖離率 + 歷史百分位
    ma20_series = df["close"].rolling(20).mean()
    ma20_val    = safe(ma20_series)
    close_val   = safe(df["close"])
    ma20_bias   = round((close_val - ma20_val) / ma20_val * 100, 2) if (ma20_val and close_val) else None

    # 歷史百分位：過去 252 交易日的乖離率分布
    bias_series = ((df["close"] - ma20_series) / ma20_series * 100).dropna()
    if len(bias_series) >= 20 and ma20_bias is not None:
        bias_pct = round(float((bias_series < ma20_bias).mean() * 100), 1)
    else:
        bias_pct = None

    return {
        "trade_date":  last.date() if hasattr(last, "date") else str(last)[:10],
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
    """Fetch 1y OHLCV, calculate indicators + 乖離率百分位, upsert to DB."""
    if tickers is None:
        tickers = _get_pool_tickers() or TRACKED_TICKERS
    logger.info("indicator job started for %d tickers", len(tickers))

    ind_sql = """
        INSERT INTO stock_indicators_daily
            (ticker, trade_date, close, volume,
             rsi14, macd, macd_signal, macd_hist, k, d, atr14,
             ma20, ma20_bias, bias_pct, updated_at)
        VALUES
            (%(ticker)s, %(trade_date)s, %(close)s, %(volume)s,
             %(rsi14)s, %(macd)s, %(macd_signal)s, %(macd_hist)s,
             %(k)s, %(d)s, %(atr14)s,
             %(ma20)s, %(ma20_bias)s, %(bias_pct)s, NOW())
        ON CONFLICT (ticker, trade_date) DO UPDATE SET
            close       = EXCLUDED.close,  volume     = EXCLUDED.volume,
            rsi14       = EXCLUDED.rsi14,  macd       = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal, macd_hist = EXCLUDED.macd_hist,
            k           = EXCLUDED.k,      d          = EXCLUDED.d,
            atr14       = EXCLUDED.atr14,  ma20       = EXCLUDED.ma20,
            ma20_bias   = EXCLUDED.ma20_bias, bias_pct = EXCLUDED.bias_pct,
            updated_at  = NOW();
    """
    price_sql = """
        INSERT INTO daily_price (ticker, trade_date, open, high, low, close, volume)
        VALUES (%(ticker)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
        ON CONFLICT (ticker, trade_date) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, volume=EXCLUDED.volume;
    """

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

            # 儲存完整 OHLCV 到 daily_price
            df = df_raw.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            for ts, row in df.tail(5).iterrows():
                price_rows.append({
                    "ticker": ticker,
                    "trade_date": ts.date() if hasattr(ts, "date") else str(ts)[:10],
                    "open": float(row["open"]) if not pd.isna(row["open"]) else None,
                    "high": float(row["high"]) if not pd.isna(row["high"]) else None,
                    "low":  float(row["low"])  if not pd.isna(row["low"])  else None,
                    "close":float(row["close"])if not pd.isna(row["close"])else None,
                    "volume": int(row["volume"]) if not pd.isna(row["volume"]) else None,
                })
        except Exception as e:
            logger.error("indicator calc failed [%s]: %s", ticker, e)

    if ind_rows or price_rows:
        try:
            with _get_conn() as conn, conn.cursor() as cur:
                if ind_rows:
                    psycopg2.extras.execute_batch(cur, ind_sql, ind_rows)
                if price_rows:
                    psycopg2.extras.execute_batch(cur, price_sql, price_rows)
                conn.commit()
            logger.info("indicator job done — %d indicators, %d price rows", len(ind_rows), len(price_rows))
        except Exception as e:
            logger.error("indicator DB upsert failed: %s", e)


def load_cache_from_db():
    """Warm up in-memory cache from DB on startup (latest row per ticker)."""
    sql = """
        SELECT DISTINCT ON (ticker)
            ticker, trade_date, close, volume,
            rsi14, macd, macd_signal, macd_hist, k, d, atr14,
            ma20, ma20_bias, bias_pct
        FROM stock_indicators_daily
        ORDER BY ticker, trade_date DESC;
    """
    try:
        with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                ticker = row["ticker"]
                _cache[ticker] = dict(row)
        logger.info("indicator cache warmed: %d tickers", len(_cache))
    except Exception as e:
        logger.warning("indicator cache warm-up failed (table may not exist yet): %s", e)


def get_indicators(ticker: str) -> Optional[dict]:
    return _cache.get(ticker)


def get_all_indicators() -> dict:
    return dict(_cache)
