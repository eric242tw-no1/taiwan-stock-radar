"""
AI 個股分析服務
支援多 provider：Anthropic Claude / DeepSeek / Google Gemini
環境變數優先順序：ANTHROPIC_API_KEY → DEEPSEEK_API_KEY → GEMINI_API_KEY
結果快取到 Redis（TTL 至隔日 09:00）+ PostgreSQL daily_ai_report 表
"""

import json
import logging
import os
from datetime import date, datetime, timedelta

import psycopg2
import redis

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
REDIS_URL         = os.getenv("REDIS_URL", "redis://redis:6379")

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "stockradar"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
    )


def _ttl_until_tomorrow_9am() -> int:
    """Return seconds until tomorrow 09:00 Taiwan time (UTC+8)."""
    now = datetime.utcnow() + timedelta(hours=8)
    tomorrow_9 = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return max(60, int((tomorrow_9 - now).total_seconds()))


def _cache_key(symbol: str, trade_date: str) -> str:
    return f"ai:score:{symbol}:{trade_date}"


def _load_from_redis(symbol: str, trade_date: str) -> dict | None:
    try:
        raw = _get_redis().get(_cache_key(symbol, trade_date))
        if raw:
            data = json.loads(raw)
            data["cached"] = True
            return data
    except Exception as e:
        logger.warning("Redis read failed: %s", e)
    return None


def _save_to_redis(symbol: str, trade_date: str, data: dict):
    try:
        _get_redis().setex(
            _cache_key(symbol, trade_date),
            _ttl_until_tomorrow_9am(),
            json.dumps(data, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("Redis write failed: %s", e)


def _save_to_db(symbol: str, trade_date: str, data: dict):
    sql = """
        INSERT INTO daily_ai_report
            (symbol, date, ai_score, suggestion, summary, key_points, cached_at)
        VALUES (%(symbol)s, %(date)s, %(ai_score)s, %(suggestion)s, %(summary)s, %(key_points)s, NOW())
        ON CONFLICT (symbol, date) DO UPDATE SET
            ai_score   = EXCLUDED.ai_score,
            suggestion = EXCLUDED.suggestion,
            summary    = EXCLUDED.summary,
            key_points = EXCLUDED.key_points,
            cached_at  = NOW();
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, {
                "symbol":     symbol,
                "date":       trade_date,
                "ai_score":   data.get("composite"),
                "suggestion": data.get("suggestion"),
                "summary":    data.get("summary"),
                "key_points": json.dumps(data.get("key_points", []), ensure_ascii=False),
            })
            conn.commit()
    except Exception as e:
        logger.warning("DB write for daily_ai_report failed: %s", e)


def _build_prompt(symbol: str, ind: dict, chip_latest: dict, quote: dict | None) -> str:
    foreign_lots = int(chip_latest.get("foreign", 0)) // 1000
    trust_lots   = int(chip_latest.get("trust", 0)) // 1000
    dealer_lots  = int(chip_latest.get("dealer", 0)) // 1000
    price        = (quote or {}).get("price", "N/A")
    change_pct   = (quote or {}).get("change_pct", 0)
    volume       = (quote or {}).get("volume", "N/A")

    return f"""你是一位專業的台股分析師。根據以下即時數據，對股票 {symbol} 進行綜合評分。

技術指標：
- RSI(14)={ind.get('rsi14', 'N/A')}
- MACD={ind.get('macd', 'N/A')} / Signal={ind.get('macd_signal', 'N/A')} / Hist={ind.get('macd_hist', 'N/A')}
- KD: K={ind.get('k', 'N/A')} / D={ind.get('d', 'N/A')}
- ATR(14)={ind.get('atr14', 'N/A')}

籌碼面（最新一日）：
- 外資買賣超：{foreign_lots} 張
- 投信買賣超：{trust_lots} 張
- 自營商買賣超：{dealer_lots} 張

當日行情：
- 收盤價：{price} 元
- 漲跌幅：{change_pct}%
- 成交量：{volume} 張

請輸出純 JSON（不要 markdown 包裝），格式如下：
{{
  "tech": <技術面評分 0-100>,
  "chip": <籌碼面評分 0-100>,
  "fundamental": <基本面評分 0-100，資料有限時給 50>,
  "macro": <宏觀面評分 0-100，無額外資料時給 50>,
  "risk": <風險評分 0-100，越高表示風險越低>,
  "composite": <綜合評分 0-100>,
  "suggestion": "偏多" or "偏空" or "中性" or "強勢做多" or "強勢放空",
  "summary": "<100字以內的繁體中文操作摘要>",
  "key_points": ["<要點1>", "<要點2>", "<要點3>"]
}}"""


def _parse_response(raw: str) -> dict:
    """Parse LLM response, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    result = json.loads(text.strip())
    for key in ("tech", "chip", "fundamental", "macro", "risk", "composite"):
        if key in result:
            result[key] = max(0, min(100, int(result[key])))
    return result


def _call_anthropic(prompt: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(msg.content[0].text)


def _call_deepseek(prompt: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(resp.choices[0].message.content)


def _call_gemini(prompt: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    return _parse_response(resp.text)


def _call_llm(symbol: str, ind: dict, chip: dict | None, quote: dict | None) -> dict:
    chip_latest = (chip or {}).get("latest", {})
    prompt = _build_prompt(symbol, ind, chip_latest, quote)

    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY not in ("placeholder", ""):
        result = _call_anthropic(prompt)
        result["provider"] = "claude"
    elif DEEPSEEK_API_KEY and DEEPSEEK_API_KEY not in ("placeholder", ""):
        result = _call_deepseek(prompt)
        result["provider"] = "deepseek"
    elif GEMINI_API_KEY and GEMINI_API_KEY not in ("placeholder", ""):
        result = _call_gemini(prompt)
        result["provider"] = "gemini"
    else:
        raise ValueError("No AI API key configured")

    return result


def get_ai_analysis(symbol: str, ind: dict | None, chip: dict | None, quote: dict | None) -> dict:
    """
    Main entry: return AI analysis dict.
    1. Redis cache hit → return immediately
    2. Any AI key available → call LLM, cache, persist
    3. No key → return {} (caller returns source=rule_based)
    """
    trade_date = date.today().isoformat()

    cached = _load_from_redis(symbol, trade_date)
    if cached:
        return cached

    has_key = any([
        ANTHROPIC_API_KEY not in ("", "placeholder"),
        DEEPSEEK_API_KEY  not in ("", "placeholder"),
        GEMINI_API_KEY    not in ("", "placeholder"),
    ])
    if not has_key:
        return {}

    try:
        result = _call_llm(symbol, ind or {}, chip, quote)
        result["source"] = "claude"  # frontend 用這個判斷顯示 "AI 分析" 標籤
        result["cached"] = False
        _save_to_redis(symbol, trade_date, result)
        _save_to_db(symbol, trade_date, result)
        return result
    except Exception as e:
        logger.error("LLM API call failed for %s: %s", symbol, e)
        return {}
