"""
CMoney 個股討論區情緒爬蟲
使用 Playwright 非同步爬取個股討論頁最近留言，以關鍵字規則判斷看漲/看跌情緒
快取於 Redis（TTL 30 分鐘）；爬取失敗時 graceful 回傳 None
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CACHE_TTL = 1800  # 30 分鐘
MAX_COMMENTS = 30

BULLISH_KEYWORDS = [
    "多頭", "看漲", "買進", "強勢", "突破", "噴出", "飆漲", "看好",
    "上攻", "作多", "做多", "漲停", "強攻", "拉升", "反彈", "續漲",
    "站上", "衝破", "噴發", "起漲",
    # 論壇常見用語
    "外資買超", "投信買超", "法人買超", "大買", "狂買", "大漲",
    "創新高", "噴漲", "強彈", "多方", "偏多", "有撐", "看到",
    "衝高", "急漲", "補漲", "趨勢向上", "黃金交叉",
]

BEARISH_KEYWORDS = [
    "空頭", "看跌", "賣出", "弱勢", "破底", "崩盤", "下殺", "看壞",
    "出場", "作空", "做空", "跌停", "急殺", "摜壓", "下跌", "跌破",
    "套牢", "止損", "跌深", "爆跌",
    # 論壇常見用語
    "外資賣超", "外資續賣", "投信賣超", "法人賣超", "大賣", "狂跌",
    "創新低", "死貓彈", "空方", "偏空", "無力", "撐不住",
    "急跌", "趨勢向下", "死亡交叉", "開盤空", "弱勢整理",
]

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _score_text(text: str) -> str:
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


async def _scrape_cmoney(symbol: str) -> list[str]:
    """用 Playwright 爬取 CMoney 個股討論頁最近留言文字"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("CMoney: playwright 未安裝，跳過")
        return []

    url = f"https://www.cmoney.tw/forum/stock/{symbol}"
    comments: list[str] = []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="zh-TW",
            )
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=20000)
            # 隨機 delay 避免被偵測
            await asyncio.sleep(random.uniform(2, 4))

            # 抓貼文區塊（article 為 CMoney 論壇主要容器）
            elements = await page.query_selector_all("article")
            for el in elements[:MAX_COMMENTS]:
                text = await el.inner_text()
                if text.strip():
                    comments.append(text.strip())

            await browser.close()
    except Exception as e:
        logger.warning(f"CMoney: 爬取 {symbol} 失敗: {e}")

    return comments


def get_cmoney_sentiment(symbol: str) -> dict | None:
    """
    取得指定股票代號的 CMoney 討論區情緒分析。
    同步包裝非同步爬取，優先讀 Redis 快取。
    失敗時回傳 None（前端不顯示此區塊）。
    """
    cache_key = f"cmoney_sentiment:{symbol}"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return data if data else None
    except Exception:
        pass

    # 執行非同步爬取
    try:
        loop = asyncio.new_event_loop()
        comments = loop.run_until_complete(_scrape_cmoney(symbol))
        loop.close()
    except Exception as e:
        logger.warning(f"CMoney: event loop 錯誤: {e}")
        comments = []

    if not comments:
        # 快取空結果避免頻繁重試
        try:
            _get_redis().setex(cache_key, 300, json.dumps(None))
        except Exception:
            pass
        return None

    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for text in comments:
        label = _score_text(text)
        if label == "bullish":
            bullish_count += 1
        elif label == "bearish":
            bearish_count += 1
        else:
            neutral_count += 1

    total = len(comments)
    score = (bullish_count - bearish_count) / total if total > 0 else 0.0

    if score > 0.1:
        sentiment_label = "偏多"
    elif score < -0.1:
        sentiment_label = "偏空"
    else:
        sentiment_label = "中性"

    result = {
        "symbol": symbol,
        "source": "cmoney",
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "total_posts": total,
        "sentiment_score": round(score, 3),
        "label": sentiment_label,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _get_redis().setex(cache_key, CACHE_TTL, json.dumps(result, ensure_ascii=False))
    except Exception:
        pass

    return result
