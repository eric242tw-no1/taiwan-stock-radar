"""
PTT Stock 板情緒爬蟲
爬取最新貼文標題，找出含特定股票代號的貼文，以關鍵字規則判斷看漲/看跌情緒
快取於 Redis（TTL 30 分鐘）
"""

import logging
import os
import time
from datetime import datetime, timezone

import httpx
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CACHE_TTL = 1800  # 30 分鐘

BULLISH_KEYWORDS = [
    "多頭", "看漲", "買進", "強勢", "突破", "噴出", "飆漲", "看好",
    "上攻", "作多", "做多", "漲停", "強攻", "拉升", "反彈", "續漲",
    "站上", "衝破", "噴發", "起漲",
]

BEARISH_KEYWORDS = [
    "空頭", "看跌", "賣出", "弱勢", "破底", "崩盤", "下殺", "看壞",
    "出場", "作空", "做空", "跌停", "急殺", "摜壓", "下跌", "跌破",
    "套牢", "止損", "跌深", "爆跌",
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


def _fetch_ptt_articles(pages: int = 5) -> list[dict]:
    """爬取 PTT Stock 板最新 N 頁的貼文列表"""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": "over18=1",  # 跳過年齡驗證
    }
    articles = []

    try:
        with httpx.Client(headers=headers, timeout=15, follow_redirects=True) as client:
            # 先取得最新頁碼
            resp = client.get("https://www.ptt.cc/bbs/Stock/index.html")
            resp.raise_for_status()

            # 從「上頁」連結解析當前最大頁碼
            from html.parser import HTMLParser

            class PageParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.prev_url: str | None = None

                def handle_starttag(self, tag, attrs):
                    if tag == "a":
                        attr_dict = dict(attrs)
                        href = attr_dict.get("href", "")
                        if "/bbs/Stock/index" in href and href.endswith(".html"):
                            self.prev_url = href

            parser = PageParser()
            parser.feed(resp.text)

            # 解析頁碼（e.g. /bbs/Stock/index3980.html → 3980）
            start_page = None
            if parser.prev_url:
                import re
                m = re.search(r"index(\d+)\.html", parser.prev_url)
                if m:
                    start_page = int(m.group(1)) + 1  # 上頁+1 = 最新頁

            if start_page is None:
                logger.warning("PTT: 無法解析頁碼，跳過")
                return []

            # 逐頁爬取
            for page in range(start_page, max(start_page - pages, 0), -1):
                url = f"https://www.ptt.cc/bbs/Stock/index{page}.html"
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    articles.extend(_parse_articles(r.text))
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"PTT: 爬取第 {page} 頁失敗: {e}")

    except Exception as e:
        logger.error(f"PTT: 爬取失敗: {e}")

    return articles


def _parse_articles(html: str) -> list[dict]:
    """從 PTT 列表頁 HTML 解析貼文標題"""
    from html.parser import HTMLParser

    class ArticleParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.articles: list[dict] = []
            self._in_title = False
            self._current_title = ""
            self._current_href = ""

        def handle_starttag(self, tag, attrs):
            attr_dict = dict(attrs)
            if tag == "div" and "r-ent" in attr_dict.get("class", ""):
                self._current_title = ""
                self._current_href = ""
            if tag == "a" and attr_dict.get("href", "").startswith("/bbs/Stock/M."):
                self._in_title = True
                self._current_href = attr_dict["href"]

        def handle_data(self, data):
            if self._in_title:
                self._current_title += data

        def handle_endtag(self, tag):
            if tag == "a" and self._in_title:
                self._in_title = False
                title = self._current_title.strip()
                if title:
                    self.articles.append({"title": title, "href": self._current_href})

    parser = ArticleParser()
    parser.feed(html)
    return parser.articles


def get_ptt_sentiment(symbol: str) -> dict:
    """
    取得指定股票代號的 PTT Stock 板情緒分析。
    優先從 Redis 快取讀取，cache miss 才爬取。
    """
    cache_key = f"ptt_sentiment:{symbol}"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    articles = _fetch_ptt_articles(pages=5)

    # 篩選含有股票代號的貼文（標題含代號或股票名）
    relevant = [a for a in articles if symbol in a["title"]]

    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for a in relevant:
        label = _score_text(a["title"])
        if label == "bullish":
            bullish_count += 1
        elif label == "bearish":
            bearish_count += 1
        else:
            neutral_count += 1

    total = len(relevant)
    if total > 0:
        score = (bullish_count - bearish_count) / total
    else:
        score = 0.0

    if score > 0.1:
        label = "偏多"
    elif score < -0.1:
        label = "偏空"
    else:
        label = "中性"

    result = {
        "symbol": symbol,
        "source": "ptt",
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "total_posts": total,
        "sentiment_score": round(score, 3),
        "label": label,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        import json
        _get_redis().setex(cache_key, CACHE_TTL, json.dumps(result, ensure_ascii=False))
    except Exception:
        pass

    return result
