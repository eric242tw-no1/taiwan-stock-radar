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

# ── Ticker list ──────────────────────────────────────────────────────────────
TRACKED_TICKERS = [
    "2330.TW",  # 台積電
    "2317.TW",  # 鴻海
    "2454.TW",  # 聯發科
    "2412.TW",  # 中華電
    "0050.TW",  # 元大台灣50
    "2308.TW",  # 台達電
    "2881.TW",  # 富邦金
    "2382.TW",  # 廣達
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
    """Create stock_indicators_daily if it doesn't exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS stock_indicators_daily (
        ticker      VARCHAR(16)  NOT NULL,
        trade_date  DATE         NOT NULL,
        close       NUMERIC(12,4),
        volume      BIGINT,
        rsi14       NUMERIC(8,4),
        macd        NUMERIC(12,6),
        macd_signal NUMERIC(12,6),
        macd_hist   NUMERIC(12,6),
        k           NUMERIC(8,4),
        d           NUMERIC(8,4),
        atr14       NUMERIC(12,6),
        updated_at  TIMESTAMP    DEFAULT NOW(),
        PRIMARY KEY (ticker, trade_date)
    );
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()
        logger.info("stock_indicators_daily table ready")
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

    return {
        "trade_date": last.date() if hasattr(last, "date") else str(last)[:10],
        "close":      safe(df["close"]),
        "volume":     int(df["volume"].iloc[-1]) if not pd.isna(df["volume"].iloc[-1]) else None,
        "rsi14":      safe(rsi),
        "macd":       safe(macd_df[macd_col[0]]) if macd_col else None,
        "macd_signal":safe(macd_df[sig_col[0]])  if sig_col  else None,
        "macd_hist":  safe(macd_df[hist_col[0]]) if hist_col else None,
        "k":          safe(stoch_df[k_col[0]])   if k_col    else None,
        "d":          safe(stoch_df[d_col[0]])   if d_col    else None,
        "atr14":      safe(atr),
    }


def calculate_and_store(tickers: list[str] = TRACKED_TICKERS):
    """Fetch OHLCV, calculate indicators, upsert to DB. Called by APScheduler."""
    logger.info("indicator job started for %d tickers", len(tickers))
    upsert_sql = """
        INSERT INTO stock_indicators_daily
            (ticker, trade_date, close, volume, rsi14, macd, macd_signal, macd_hist, k, d, atr14, updated_at)
        VALUES
            (%(ticker)s, %(trade_date)s, %(close)s, %(volume)s,
             %(rsi14)s, %(macd)s, %(macd_signal)s, %(macd_hist)s,
             %(k)s, %(d)s, %(atr14)s, NOW())
        ON CONFLICT (ticker, trade_date) DO UPDATE SET
            close       = EXCLUDED.close,
            volume      = EXCLUDED.volume,
            rsi14       = EXCLUDED.rsi14,
            macd        = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            macd_hist   = EXCLUDED.macd_hist,
            k           = EXCLUDED.k,
            d           = EXCLUDED.d,
            atr14       = EXCLUDED.atr14,
            updated_at  = NOW();
    """
    rows = []
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="90d", interval="1d", progress=False, auto_adjust=True)
            result = _calc_indicators(df)
            if result is None:
                logger.warning("not enough data for %s", ticker)
                continue
            result["ticker"] = ticker
            rows.append(result)
            _cache[ticker] = result
            logger.info("  %s: RSI=%.1f  MACD=%.4f  K=%.1f", ticker,
                        result["rsi14"] or 0, result["macd"] or 0, result["k"] or 0)
        except Exception as e:
            logger.error("indicator calc failed [%s]: %s", ticker, e)

    if rows:
        try:
            with _get_conn() as conn, conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, upsert_sql, rows)
                conn.commit()
            logger.info("indicator job done — %d rows upserted", len(rows))
        except Exception as e:
            logger.error("indicator DB upsert failed: %s", e)


def load_cache_from_db():
    """Warm up in-memory cache from DB on startup (latest row per ticker)."""
    sql = """
        SELECT DISTINCT ON (ticker)
            ticker, trade_date, close, volume,
            rsi14, macd, macd_signal, macd_hist, k, d, atr14
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
