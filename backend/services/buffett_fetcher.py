"""
Taiwan Buffett Indicator: Total Stock Market Cap / GDP %

Data sources:
  - Market cap: TAIEX index × calibration factor (yfinance ^TWII)
  - GDP: DGBAS annual estimate (hardcoded, update Jan each year)

Calibration reference points (update annually):
  Dec 2023: TAIEX 17,930 → mkt cap ~55.2 兆 → factor 30.8
  Dec 2024: TAIEX 22,000 → mkt cap ~65.0 兆 → factor 29.5  ← current
  (Factor may drift ±5% due to new listings; recalibrate each December)

Indicator zones (Taiwan context — chronically higher than US due to
export-heavy, high-export economy and TSMC concentration effect):
  < 150%  : Reasonable / mild undervaluation
  150-250%: Moderate overvaluation
  250-350%: Elevated (historically normal bull market territory for TW)
  > 350%  : Extreme — highest historical territory
"""
import logging
import time
from datetime import datetime
from typing import Optional

import httpx
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Taiwan GDP (億元 TWD, nominal) ──────────────────────────────────────
# Source: DGBAS National Statistics ROC
# Update this each January when the new annual estimate is published.
_GDP_TWD_YI = 280_000   # 28.0 兆 TWD (2026 estimated, based on DGBAS trend)
_GDP_YEAR   = 2026

# ── TAIEX → Total Market Cap calibration ───────────────────────────────
# Calibration: TAIEX 22,000 (Dec 2024) ≈ total listed market cap 65.0 兆 TWD
# Factor (億元 per TAIEX point): 650,000 / 22,000 ≈ 29.5
# Update this each December using TWSE official annual market cap statistics.
_MKT_CAP_FACTOR = 29.5   # 億元 per 1 TAIEX index point

# ── Simple in-memory cache ──────────────────────────────────────────────
_cache: dict = {"ts": 0, "data": None}
_CACHE_TTL = 3600   # 1 hour


_TWSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mis.twse.com.tw/",
}


def _fetch_twse_market_cap_yi() -> Optional[float]:
    """
    Attempt to parse total listed market cap (億元 TWD) from TWSE MI_INDEX table[6].
    Table[6] columns (afterTrading): 名稱 | 成交量 | 成交金額(千元) | 市值(千元)
    The 4th column (index 3) of the '全部' row = total market cap in 千元.
    Returns None on failure — caller falls back to TAIEX calibration.
    """
    from datetime import date as _date
    today = _date.today().strftime("%Y%m%d")
    try:
        with httpx.Client(follow_redirects=True) as c:
            resp = c.get(
                "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                params={"response": "json", "date": today},
                headers=_TWSE_HEADERS,
                timeout=8,
            )
            resp.raise_for_status()
            tables = resp.json().get("tables", [])
        if len(tables) > 6:
            rows = tables[6].get("data", [])
            fields = tables[6].get("fields", [])
            # Need ≥4 columns; col[3] = 市值(千元)
            if len(fields) >= 4 and rows:
                for row in rows:
                    if len(row) >= 4:
                        try:
                            mktcap_qian = float(str(row[3]).replace(",", ""))
                            # 千元 → 億元: / 100,000
                            mktcap_yi = mktcap_qian / 100_000
                            if 300_000 < mktcap_yi < 5_000_000:
                                logger.info("TWSE direct market cap: %.0f 億元", mktcap_yi)
                                return mktcap_yi
                        except (ValueError, TypeError):
                            pass
        logger.warning("TWSE market cap column not parseable — using calibration fallback")
        return None
    except Exception as e:
        logger.warning("TWSE market cap fetch failed: %s", e)
        return None


def _fetch_taiex_market_cap_yi() -> Optional[float]:
    """Estimate total market cap via TAIEX index × calibration factor."""
    try:
        ticker = yf.Ticker("^TWII")
        info = ticker.fast_info
        index_level = float(info.last_price or 0)
        if index_level > 5_000:
            return round(index_level * _MKT_CAP_FACTOR, 0)
        return None
    except Exception as e:
        logger.warning("TAIEX yfinance fetch failed: %s", e)
        return None


def fetch_buffett() -> dict:
    """
    Return Taiwan Buffett Indicator data.
    Cached for 1 hour.
    """
    if time.time() - _cache["ts"] < _CACHE_TTL and _cache["data"]:
        return _cache["data"]

    market_cap_yi: Optional[float] = None
    source = "unavailable"

    # Strategy 1: TWSE official stats
    market_cap_yi = _fetch_twse_market_cap_yi()
    if market_cap_yi:
        source = "twse"

    # Strategy 2: yfinance TAIEX calibration
    if not market_cap_yi:
        market_cap_yi = _fetch_taiex_market_cap_yi()
        if market_cap_yi:
            source = "taiex_estimated"

    ratio: Optional[float] = None
    if market_cap_yi and _GDP_TWD_YI > 0:
        ratio = round(market_cap_yi / _GDP_TWD_YI * 100, 1)

    result = {
        "ratio":          ratio,
        "market_cap_yi":  round(market_cap_yi, 0) if market_cap_yi else None,
        "gdp_yi":         _GDP_TWD_YI,
        "gdp_year":       _GDP_YEAR,
        "source":         source,
        "updated_at":     datetime.now().isoformat(),
    }
    _cache.update({"ts": time.time(), "data": result})
    logger.info("Buffett indicator: ratio=%.1f%% source=%s", ratio or 0, source)
    return result


def get_cached_buffett() -> dict:
    return _cache["data"] or fetch_buffett()
