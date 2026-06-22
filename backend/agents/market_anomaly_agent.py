"""Market Anomaly Agent — scans for price/volume anomalies every 10 min during trading hours."""
import asyncio
import logging
from datetime import datetime, time as dtime

import pytz
from utils.telegram import send_message  # imported at module level for testability
from services.twse_fetcher import get_cached_tw_market
from services.ohlcv_service import fetch_ohlcv

logger = logging.getLogger(__name__)

TW_TZ = pytz.timezone("Asia/Taipei")
MARKET_OPEN = dtime(9, 0)
MARKET_CLOSE = dtime(13, 30)

GAP_THRESHOLD = 0.03       # 3% gap
VOLUME_MULTIPLIER = 3.0    # 3× 20-day avg volume


def _is_trading_hours() -> bool:
    now_tw = datetime.now(TW_TZ).time()
    return MARKET_OPEN <= now_tw <= MARKET_CLOSE


def _limit_price(close: float, direction: str) -> float:
    """Taiwan stock exchange daily limit: ±10%."""
    if direction == "up":
        return round(close * 1.10, 2)
    return round(close * 0.90, 2)


async def scan_anomalies() -> list[dict]:
    """Scan all tracked symbols for anomalies; send Telegram alerts on findings."""
    if not _is_trading_hours():
        logger.debug("scan_anomalies: outside trading hours, skip")
        return []

    market = get_cached_tw_market()
    stocks: list[dict] = market.get("stocks", [])
    if not stocks:
        logger.warning("scan_anomalies: no market data available")
        return []

    anomalies: list[dict] = []

    for stock in stocks:
        symbol = stock.get("symbol", "")
        close = stock.get("close") or stock.get("price")
        open_price = stock.get("open")
        volume = stock.get("volume")  # shares

        if not symbol or close is None:
            continue

        detected: list[str] = []

        # Gap detection (open vs previous close)
        if open_price and close:
            try:
                rows = fetch_ohlcv(f"{symbol}.TW", period="5d")
                if len(rows) >= 2:
                    prev_close = rows[-2]["close"]
                    gap = abs(open_price - prev_close) / prev_close
                    if gap > GAP_THRESHOLD:
                        direction = "上漲" if open_price > prev_close else "下跌"
                        detected.append(f"跳空{direction} {gap*100:.1f}%（前收 {prev_close}，開盤 {open_price}）")
            except Exception:
                pass

        # Volume surge detection
        if volume:
            try:
                rows = fetch_ohlcv(f"{symbol}.TW", period="30d")
                if len(rows) >= 20:
                    avg_vol = sum(r["volume"] for r in rows[-20:]) / 20
                    if avg_vol > 0 and volume > VOLUME_MULTIPLIER * avg_vol:
                        detected.append(f"爆量 {volume/avg_vol:.1f}× 20日均量")
            except Exception:
                pass

        # Limit up/down detection
        if close:
            try:
                rows = fetch_ohlcv(f"{symbol}.TW", period="5d")
                if len(rows) >= 2:
                    prev_close = rows[-2]["close"]
                    limit_up = _limit_price(prev_close, "up")
                    limit_down = _limit_price(prev_close, "down")
                    if abs(close - limit_up) / limit_up < 0.001:
                        detected.append(f"漲停 {close}")
                    elif abs(close - limit_down) / limit_down < 0.001:
                        detected.append(f"跌停 {close}")
            except Exception:
                pass

        if detected:
            name = stock.get("name", symbol)
            msg = f"⚠️ <b>{name}（{symbol}）異常偵測</b>\n" + "\n".join(f"• {d}" for d in detected)

            # 附加 factor_snapshot（使用 factor_engine）
            factor_snapshot = None
            try:
                import pandas as pd
                from factor_engine import technical as fe_tech
                rows = fetch_ohlcv(f"{symbol}.TW", period="90d")
                if len(rows) >= 20:
                    df_ohlcv = pd.DataFrame(rows).rename(columns={"time": "date"})
                    factors = fe_tech.compute(symbol, df_ohlcv)
                    factor_snapshot = {"rsi_14": factors.rsi_14, "macd": factors.macd,
                                       "ma20": factors.ma20, "bias_20": factors.bias_20}
            except Exception:
                pass

            anomalies.append({
                "symbol": symbol, "name": name, "anomalies": detected,
                "factor_snapshot": factor_snapshot,
            })
            try:
                await send_message(msg)
            except Exception as exc:
                logger.warning("scan_anomalies: telegram failed for %s — %s", symbol, exc)

    logger.info("scan_anomalies: found %d anomalies", len(anomalies))
    return anomalies
