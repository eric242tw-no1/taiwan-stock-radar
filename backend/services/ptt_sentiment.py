"""
PTT Stock 板情緒爬蟲
爬取最新貼文標題，找出含特定股票代號的貼文，以關鍵字規則判斷看漲/看跌情緒
快取於 SQLite cache 表（TTL 30 分鐘）
"""

import logging
import time
from datetime import datetime, timezone

import httpx

from services.kv_store import kv_get, kv_set

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 分鐘

BULLISH_KEYWORDS = [
    "多頭", "看漲", "買進", "強勢", "突破", "噴出", "飆漲", "看好",
    "上攻", "作多", "做多", "漲停", "強攻", "拉升", "反彈", "續漲",
    "站上", "衝破", "噴發", "起漲",
    "外資買超", "投信買超", "法人買超", "大買", "大漲",
    "創新高", "強彈", "多方", "偏多", "衝高", "急漲", "補漲", "黃金交叉",
    # 擴充：常見利多/口語
    "利多", "噴", "紅通通", "大紅", "長紅",
    "新高", "歷史新高", "創高", "暴漲", "狂漲", "回神",
    "進場", "加碼", "抄底", "撿便宜",
    "目標價調升", "升評", "翻紅", "領漲", "強漲", "轉強",
]

BEARISH_KEYWORDS = [
    "空頭", "看跌", "賣出", "弱勢", "破底", "崩盤", "下殺", "看壞",
    "出場", "作空", "做空", "跌停", "急殺", "摜壓", "下跌", "跌破",
    "套牢", "止損", "跌深", "爆跌",
    "外資賣超", "外資續賣", "投信賣超", "法人賣超", "大賣", "狂跌",
    "創新低", "空方", "偏空", "無力", "撐不住", "急跌", "死亡交叉", "弱勢整理",
    # 擴充：常見利空/口語
    "利空", "崩", "大綠", "長黑", "翻黑", "新低", "創低",
    "暴跌", "重挫", "殺盤", "賣壓", "認賠", "逃命", "領跌",
    "目標價調降", "降評", "轉弱", "走弱", "雪崩", "血流成河",
]

def _score_text(text: str) -> str:
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def _search_ptt_articles(query: str, pages: int = 2) -> list[dict]:
    """用 PTT 站內搜尋抓含關鍵字的貼文（命中率遠高於爬最新列表）。"""
    import urllib.parse
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Cookie": "over18=1",
    }
    articles: list[dict] = []
    q = urllib.parse.quote(query)
    try:
        with httpx.Client(headers=headers, timeout=15, follow_redirects=True, verify=False) as client:
            for page in range(1, pages + 1):
                url = f"https://www.ptt.cc/bbs/Stock/search?q={q}&page={page}"
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    found = _parse_articles(r.text)
                    if not found:
                        break
                    articles.extend(found)
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"PTT search 第 {page} 頁失敗: {e}")
                    break
    except Exception as e:
        logger.error(f"PTT search 失敗: {e}")
    return articles


def _fetch_ptt_articles(pages: int = 5) -> list[dict]:
    """爬取 PTT Stock 板最新 N 頁的貼文列表"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Cookie": "over18=1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    articles = []

    try:
        with httpx.Client(headers=headers, timeout=15, follow_redirects=True, verify=False) as client:
            # 先取得最新頁碼
            resp = client.get("https://www.ptt.cc/bbs/Stock/index.html")
            resp.raise_for_status()

            # 找所有頁碼連結，取最大值+1 = 最新頁
            import re
            all_nums = [int(m.group(1)) for m in re.finditer(r"/bbs/Stock/index(\d+)\.html", resp.text)]
            start_page = max(all_nums) + 1 if all_nums else None

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


def get_ptt_sentiment(symbol: str, name: str | None = None) -> dict:
    """
    取得指定股票代號的 PTT Stock 板情緒分析。
    name 為公司名稱（如「台積電」），一併搜尋以提升命中率。
    優先從快取讀取，cache miss 才爬取。
    """
    cache_key = f"ptt_sentiment:{symbol}"
    cached = kv_get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    # 用 PTT 站內搜尋（公司名命中率最高；無名稱時用代號）
    query = name or symbol
    articles = _search_ptt_articles(query, pages=2)
    # 搜尋結果已是相關文；去重後全數採用
    seen = set()
    relevant = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            relevant.append(a)

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
    # 情緒分數只看「有方向性」的文章（多+空），避免大量中性新聞稀釋掉訊號
    directional = bullish_count + bearish_count
    if directional > 0:
        score = (bullish_count - bearish_count) / directional
    else:
        score = 0.0

    # 需至少 2 篇方向性文章才下偏多/偏空判定，降低單篇雜訊
    if directional >= 2 and score > 0.15:
        label = "偏多"
    elif directional >= 2 and score < -0.15:
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

    import json
    kv_set(cache_key, json.dumps(result, ensure_ascii=False), CACHE_TTL)

    return result
