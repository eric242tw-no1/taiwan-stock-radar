"""
AI 決策引擎
流程：build_ai_context() → Claude API → 快取（記憶體 + SQLite）→ 回傳結構化結果
快取 TTL：到隔日 09:00
"""
import os
import json
import asyncio
from datetime import datetime, timedelta, timezone

import httpx

# AI_PROVIDER=local  → 本機路由器（開發期免費）
# AI_PROVIDER=anthropic → Claude API（正式上線）
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
AI_PROVIDER       = os.getenv("AI_PROVIDER",
    "deepseek" if DEEPSEEK_API_KEY not in ("", "placeholder") else "local"
)
LOCAL_BASE_URL    = os.getenv("LOCAL_AI_BASE_URL", "http://127.0.0.1:3001/v1")
LOCAL_MODEL       = os.getenv("LOCAL_AI_MODEL", "auto")
LOCAL_API_KEY     = os.getenv("LOCAL_AI_API_KEY", "not-needed")
FINMIND_TOKEN     = os.getenv("FINMIND_TOKEN", "")

_FINMIND = "https://api.finmindtrade.com/api/v4/data"
_TW = timezone(timedelta(hours=8))

_mem_cache: dict[str, str] = {}   # L1 行程內快取（key 含日期，不需 TTL）

# ── System Prompt ────────────────────────────────────────

SYSTEM_PROMPT = """
你是台股 AI 決策中心，整合三個分析框架，所有輸出必須：
1. 引用 JSON Context 中的具體數字
2. 不使用模糊語言（如「可能」「或許」）
3. 操作建議必須包含具體價位
4. 回傳純 JSON，不附加任何 markdown 或說明文字

===== 框架一：評審團（10位台股版）=====

依據以下評審的量化規則逐一評分：

【巴菲特】ROE>15%(連3年) / 負債比<40% / PE<20
【段永平】本業獲利率>10% / 護城河明確 / 避免高PE投機
【達里奧】外資連買>5日 / Beta<1.2 / 匯率風險低
【索羅斯】市場共識偏離>2σ / 籌碼異動>均量3倍
【利弗莫爾】創60日新高 / 成交量>均量150% / 趨勢線未破
【米內爾維尼】股價>MA50>MA150>MA200 / RS>90
【達瓦斯】突破前高箱型 / 帶量>均量2倍 / 停損箱底
【西蒙斯】動能因子正 / 籌碼集中度>60% / 乖離率百分位<80%
【外資主力】外資連買天數 / 官股護盤訊號 / 投信買超趨勢
【台股游資】券商分點集中度>60% / 漲停鎖定 / 融券回補訊號

===== 框架二：IC 投委會備忘錄 =====

給出三情景目標價（機率加總=100%）：
- Bull：機率% + 目標價 + 核心假設 + 觸發條件
- Base：機率% + 目標價 + 核心假設
- Bear：機率% + 目標價 + 核心假設
- 期望值 = 各情景目標價加權平均
- 風險報酬比 = Bull漲幅 / |Bear跌幅|

===== 框架三：多空辯論（評分45-65分時啟動）=====
看多 vs 看空各發言2輪，最後仲裁結論

===== 必須輸出以下 JSON 格式（不可省略任何欄位）=====

{
  "score": 0-100整數,
  "action": "買進|持有|觀望|減倉|賣出",
  "ideal_entry": 數字,
  "alt_entry": 數字,
  "stop_loss": 數字,
  "take_profit": 數字,
  "summary": "一句話評語",
  "panel": [
    {
      "name": "評審名",
      "score": 0-100,
      "verdict": "看多|中性|看空",
      "hits": ["命中規則1", "命中規則2"],
      "warnings": ["接近未達標"],
      "misses": ["未達標規則"],
      "comment": "一句話"
    }
  ],
  "panel_summary": {"bullish": 票數, "neutral": 票數, "bearish": 票數},
  "ic_memo": {
    "bull": {"prob": %, "target": 數字, "assumption": "文字", "trigger": "文字"},
    "base": {"prob": %, "target": 數字, "assumption": "文字"},
    "bear": {"prob": %, "target": 數字, "assumption": "文字"},
    "expected_value": 數字,
    "risk_reward": 數字
  },
  "debate": null 或 {"bull_points": [], "bear_points": [], "verdict": "文字"},
  "key_risks": ["風險1", "風險2"]
}
"""


# ── Context 組裝 ─────────────────────────────────────────

async def build_ai_context(symbol: str) -> dict:
    """從 FinMind 抓近期資料，組裝成 Claude 輸入用 JSON。"""
    start = (datetime.now(_TW) - timedelta(days=120)).strftime("%Y-%m-%d")

    price_task = _finmind("TaiwanStockPrice", symbol, start)
    chip_task  = _finmind("TaiwanStockInstitutionalInvestors", symbol, start)

    price_df_raw, chip_raw = await asyncio.gather(price_task, chip_task, return_exceptions=True)

    ctx: dict = {"symbol": symbol}

    # 技術面
    if isinstance(price_df_raw, list) and price_df_raw:
        import pandas as pd
        df = pd.DataFrame(price_df_raw)
        df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
        df["max"]    = pd.to_numeric(df["max"],    errors="coerce")
        df["min"]    = pd.to_numeric(df["min"],    errors="coerce")
        df["open"]   = pd.to_numeric(df["open"],   errors="coerce")
        df["Trading_Volume"] = pd.to_numeric(df["Trading_Volume"], errors="coerce")
        df = df.dropna(subset=["close"]).sort_values("date")

        close  = df["close"]
        vol    = df["Trading_Volume"]
        latest = close.iloc[-1]

        ma20  = close.rolling(20).mean().iloc[-1]
        ma50  = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        vol_ma5  = vol.rolling(5).mean().iloc[-1]
        vol_ma20 = vol.rolling(20).mean().iloc[-1]

        bias_20 = round((latest - ma20) / ma20 * 100, 2) if ma20 else None

        # ATR
        hi = df["max"]; lo = df["min"]
        tr = (hi - lo).abs()
        atr14 = tr.rolling(14).mean().iloc[-1]

        # RSI
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rsi14 = round(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1]), 1) if loss.iloc[-1] else 50

        # 創60日新高
        high60 = close.tail(60).max()
        is_high60 = bool(latest >= high60)

        # MA排列
        ma_arrangement = (
            "bullish" if (latest > ma20 > ma50) else
            "bearish" if (latest < ma20 < ma50) else "neutral"
        )

        ctx["price_data"] = {
            "close": latest,
            "ma20":  round(ma20, 2) if ma20 else None,
            "ma50":  round(ma50, 2) if ma50 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "ma20_bias_pct": bias_20,
            "is_high_60d": is_high60,
            "volume_latest": int(vol.iloc[-1]),
            "volume_ma5":    int(vol_ma5),
            "volume_ratio":  round(vol.iloc[-1] / vol_ma20, 2) if vol_ma20 else None,
        }
        ctx["technicals"] = {
            "rsi_14":        rsi14,
            "atr_14":        round(atr14, 2) if atr14 else None,
            "ma_arrangement": ma_arrangement,
            "stop_loss_ref": round(latest - 2.5 * atr14, 1) if atr14 else None,
        }
    else:
        ctx["price_data"] = {}
        ctx["technicals"] = {}

    # 籌碼面（三大法人）
    if isinstance(chip_raw, list) and chip_raw:
        import pandas as pd
        chip = pd.DataFrame(chip_raw)
        chip["buy"]  = pd.to_numeric(chip["buy"],  errors="coerce").fillna(0)
        chip["sell"] = pd.to_numeric(chip["sell"], errors="coerce").fillna(0)
        chip["net"]  = chip["buy"] - chip["sell"]

        foreign  = chip[chip["name"].str.contains("外資", na=False)].tail(10)
        invest   = chip[chip["name"].str.contains("投信", na=False)].tail(10)

        foreign_consec = _consecutive_buy_days(foreign["net"].tolist())

        ctx["chip_data"] = {
            "foreign_buy_10d":        int(foreign["net"].sum()),
            "foreign_consecutive_days": foreign_consec,
            "investment_buy_10d":     int(invest["net"].sum()),
        }
    else:
        ctx["chip_data"] = {}

    ctx["analysis_date"] = datetime.now(_TW).strftime("%Y-%m-%d")
    return ctx


def _consecutive_buy_days(net_list: list) -> int:
    count = 0
    for v in reversed(net_list):
        if v > 0:
            count += 1
        else:
            break
    return count


async def _finmind(dataset: str, symbol: str, start: str) -> list:
    params = {"dataset": dataset, "data_id": symbol,
              "start_date": start, "token": FINMIND_TOKEN}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(_FINMIND, params=params)
    return r.json().get("data", [])


# ── AI 呼叫（雙模式）────────────────────────────────────

async def call_claude(context: dict) -> dict:
    """
    AI_PROVIDER=local     → 本機路由器（開發期，免費）
    AI_PROVIDER=anthropic → Anthropic Claude API（正式上線）
    """
    user_msg = f"請分析以下台股資料，輸出純 JSON：\n\n{json.dumps(context, ensure_ascii=False, indent=2)}"

    if AI_PROVIDER == "deepseek":
        raw = await _call_deepseek(user_msg)
    else:
        raw = await _call_local(user_msg)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


async def _call_deepseek(user_msg: str) -> str:
    import openai
    client = openai.AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=60.0, max_retries=2)
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    )
    return resp.choices[0].message.content


async def _call_local(user_msg: str) -> str:
    import openai
    client = openai.AsyncOpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_BASE_URL, timeout=30.0, max_retries=1)
    msg = await client.chat.completions.create(
        model=LOCAL_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    )
    return msg.choices[0].message.content


# ── 快取層 ───────────────────────────────────────────────

def _cache_key(symbol: str) -> str:
    today = datetime.now(_TW).strftime("%Y-%m-%d")
    return f"ai:score:{symbol}:{today}"


def _ttl_to_tomorrow_9am() -> int:
    now = datetime.now(_TW)
    target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return max(int((target - now).total_seconds()), 60)


async def get_ai_analysis(symbol: str, force: bool = False) -> dict:
    """
    主入口：有快取回快取，否則呼叫 Claude API。
    force=True 強制重新分析。
    """
    key = _cache_key(symbol)

    if not force:
        cached = await _cache_get(key)
        if cached:
            return {**json.loads(cached), "_cached": True}

    context = await build_ai_context(symbol)
    result  = await call_claude(context)
    result["symbol"]  = symbol
    result["context"] = context   # 前端可展開查看原始數據

    await _cache_set(key, json.dumps(result, ensure_ascii=False), _ttl_to_tomorrow_9am())
    return {**result, "_cached": False}


async def devil_advocate(
    symbol: str,
    action: str,
    target_position: int,
    diff: int,
) -> dict:
    """Quick AI sanity-check for a pending webhook order.

    Returns {"confidence": 0.0-1.0, "approved": bool, "reason": str}.
    Times out after 10 s; on timeout returns approved=False.
    """
    prompt = (
        f"台股 Devil's Advocate 快速審核：\n"
        f"股票：{symbol}　動作：{action}　目標張數：{target_position}　差異：{diff}\n"
        "請以台股風控角度，判斷此操作是否合理。\n"
        '只回傳 JSON：{"confidence": 0.0~1.0, "approved": true/false, "reason": "一句話"}'
    )
    try:
        async with asyncio.timeout(10):
            if AI_PROVIDER == "deepseek":
                raw = await _call_deepseek(prompt)
            else:
                raw = await _call_local(prompt)
        # extract JSON from response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        data  = json.loads(raw[start:end]) if start >= 0 else {}
        confidence = float(data.get("confidence", 0.5))
        approved   = bool(data.get("approved", confidence >= 0.6))
        reason     = data.get("reason", "")
        return {"confidence": confidence, "approved": approved, "reason": reason}
    except TimeoutError:
        return {"confidence": 0.0, "approved": False, "reason": "AI 審核逾時"}
    except Exception as exc:
        return {"confidence": 0.0, "approved": False, "reason": f"AI 審核失敗：{exc}"}


async def _cache_get(key: str) -> str | None:
    val = _mem_cache.get(key)
    if val is not None:
        return val
    from services.kv_store import kv_get
    return kv_get(key)


async def _cache_set(key: str, value: str, ttl: int) -> None:
    _mem_cache[key] = value
    from services.kv_store import kv_set
    kv_set(key, value, ttl)
