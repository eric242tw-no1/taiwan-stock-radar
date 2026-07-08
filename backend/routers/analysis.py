"""
AI 分析 API

GET  /api/analysis/{symbol}              — 取得分析結果（有快取直接回）
POST /api/analysis/{symbol}/refresh      — 強制重新分析（每檔 30 分鐘限一次）
GET  /api/analysis/{symbol}/cooldown     — 查詢剩餘冷卻秒數
GET  /api/analysis/{symbol}/context      — 只看 context 原始數據（不呼叫 Claude）
GET  /api/analysis/ic-memo/{symbol}      — IC 備忘錄（三情境 + 期望值，Change A）
POST /api/analysis/debate/{symbol}       — 多空辯論（Bull/Bear/Arbiter，Change A）
"""
import asyncio
import json
import logging
import os
import time
from datetime import date


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.ai_engine import get_ai_analysis, build_ai_context
from db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])

REFRESH_COOLDOWN = 30 * 60   # 秒
_last_refresh: dict[str, float] = {}


@router.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    _validate(symbol)
    try:
        return await get_ai_analysis(symbol, force=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analysis/{symbol}/refresh")
async def refresh_analysis(symbol: str):
    _validate(symbol)
    remaining = _cooldown_remaining(symbol)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"刷新冷卻中，請 {remaining // 60} 分 {remaining % 60} 秒後再試",
                "cooldown_seconds": REFRESH_COOLDOWN,
                "remaining_seconds": remaining,
            },
        )
    _last_refresh[symbol] = time.time()
    try:
        return await get_ai_analysis(symbol, force=True)
    except Exception as e:
        _last_refresh.pop(symbol, None)   # 失敗時重置，讓使用者可以重試
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analysis/{symbol}/cooldown")
async def get_cooldown(symbol: str):
    """前端用來顯示倒數計時。"""
    _validate(symbol)
    remaining = _cooldown_remaining(symbol)
    return {
        "symbol": symbol,
        "cooldown_seconds": REFRESH_COOLDOWN,
        "remaining_seconds": remaining,
        "can_refresh": remaining == 0,
    }


def _cooldown_remaining(symbol: str) -> int:
    last = _last_refresh.get(symbol)
    if last is None:
        return 0
    elapsed = int(time.time() - last)
    return max(0, REFRESH_COOLDOWN - elapsed)


@router.get("/api/analysis/{symbol}/context")
async def get_context(symbol: str):
    """只取原始數據，不呼叫 Claude（除錯 / 前端快速顯示用）。"""
    _validate(symbol)
    try:
        return await build_ai_context(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _validate(symbol: str) -> None:
    if not symbol.isdigit() or len(symbol) not in (4, 5, 6):
        raise HTTPException(status_code=400, detail="股票代號格式錯誤（4-6位數字）")


# ── UZI 評審團 ───────────────────────────────────────────────────────────────

@router.post("/api/analysis/uzi/{symbol}")
async def run_uzi(symbol: str):
    """UZI 評審團：動能派 / 價值派 / 風控派 三位 Claude 評審加權評分。"""
    _validate(symbol)
    from factor_engine import TechnicalFactors, ChipsFactors, bundle as make_bundle
    from agents.uzi_panel import UZIPanel
    from datetime import datetime, timezone

    tech = TechnicalFactors()
    chips = ChipsFactors()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT rsi14, macd, macd_signal, macd_hist, k, d, atr14, ma20, ma20_bias "
            "FROM stock_indicators_daily WHERE ticker=? ORDER BY trade_date DESC LIMIT 1",
            (f"{symbol}.TW",),
        )
        row = cur.fetchone()
        if row:
            tech = TechnicalFactors(
                rsi_14=row["rsi14"], macd=row["macd"],
                macd_signal=row["macd_signal"], macd_hist=row["macd_hist"],
                kd_k=row["k"], kd_d=row["d"],
                atr_14=row["atr14"], ma20=row["ma20"], bias_20=row["ma20_bias"],
            )
        cur.execute(
            "SELECT foreign_buy, investment_buy, dealer_buy, margin, short_interest "
            "FROM chip_data WHERE symbol=? ORDER BY date DESC LIMIT 1",
            (symbol,),
        )
        crow = cur.fetchone()
        if crow:
            chips = ChipsFactors(
                foreign_net=crow["foreign_buy"], investment_net=crow["investment_buy"],
                dealer_net=crow["dealer_buy"], margin_balance=crow["margin"],
                short_balance=crow["short_interest"],
            )
        conn.close()
    except Exception as exc:
        logger.warning("uzi: DB 查詢失敗 — %s", exc)

    fb = make_bundle(symbol, tech, chips)
    panel = UZIPanel()
    result = await panel.evaluate(symbol, fb)
    d = result.to_dict()
    # 正規化欄位名稱供前端統一使用
    d["reviewers"] = [
        {
            "name": r["reviewer"], "score": r["score"],
            "reasoning": r["reason"], "weight": r["weight"],
            "verdict": "看多" if r["score"] >= 60 else "看空" if r["score"] < 40 else "中性",
        }
        for r in d.get("reviewers", [])
    ]
    d["consensus"] = d.pop("grade", "")
    d["generated_at"] = datetime.now(timezone.utc).isoformat()

    # AI Audit：記錄 UZI 評分預測
    try:
        from services.audit import record_prediction
        score = d.get("weighted_score") or d.get("score") or 0
        direction = "up" if score >= 60 else "down" if score < 40 else "neutral"
        record_prediction(symbol, direction, confidence=score / 100)
    except Exception:
        pass

    return d


# ── IC 備忘錄 ─────────────────────────────────────────────────────────────────

@router.get("/api/analysis/ic-memo/{symbol}")
async def get_ic_memo(symbol: str, force: bool = False):
    """
    IC 備忘錄：bull/base/bear 三情境目標價 + 機率 + 期望值。
    當日已有記錄則直接回傳（快取），否則呼叫 Claude 生成後寫入 DB。
    """
    _validate(symbol)
    today = date.today()

    # 嘗試讀取當日快取
    if not force:
        cached = _read_ic_memo(symbol, today)
        if cached:
            return cached

    # 生成新 IC 備忘錄
    memo = await _generate_ic_memo(symbol)
    _write_ic_memo(symbol, today, memo)

    # AI Audit：以 base 情境作為預測基準
    try:
        from services.audit import record_prediction
        base = memo.get("scenarios", {}).get("base", {})
        base_prob = base.get("probability", 0.5)
        base_price = base.get("target_price")
        direction = "up" if base_prob >= 0.4 else "down"
        record_prediction(symbol, direction, confidence=base_prob, target_price=base_price)
    except Exception:
        pass

    return memo


def _read_ic_memo(symbol: str, as_of: date) -> dict | None:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol,date,bull_price,bull_prob,bull_assumption,base_price,base_prob,base_assumption,"
            "bear_price,bear_prob,bear_assumption,expected_value,risk_reward FROM ic_memo WHERE symbol=? AND date=?",
            (symbol, str(as_of)),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return _ic_row_to_response(dict(row))
    except Exception as exc:
        logger.warning("ic_memo read error: %s", exc)
        return None


def _write_ic_memo(symbol: str, as_of: date, memo: dict) -> None:
    s = memo.get("scenarios", {})
    bull = s.get("bull", {})
    base = s.get("base", {})
    bear = s.get("bear", {})
    sql = """
    INSERT INTO ic_memo
        (symbol, date, bull_price, bull_prob, bull_assumption,
         base_price, base_prob, base_assumption,
         bear_price, bear_prob, bear_assumption, expected_value, risk_reward)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (symbol, date) DO UPDATE SET
        bull_price=excluded.bull_price, bull_prob=excluded.bull_prob,
        base_price=excluded.base_price, base_prob=excluded.base_prob,
        bear_price=excluded.bear_price, bear_prob=excluded.bear_prob,
        expected_value=excluded.expected_value
    """
    try:
        conn = get_conn()
        conn.execute(sql, (
            symbol, str(as_of),
            bull.get("target_price"), bull.get("probability"),
            json.dumps(bull.get("key_assumptions", []), ensure_ascii=False),
            base.get("target_price"), base.get("probability"),
            json.dumps(base.get("key_assumptions", []), ensure_ascii=False),
            bear.get("target_price"), bear.get("probability"),
            json.dumps(bear.get("key_assumptions", []), ensure_ascii=False),
            memo.get("expected_value"), None,
        ))
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("ic_memo write error: %s", exc)


def _ic_row_to_response(row: dict) -> dict:
    def parse_assumptions(val) -> list:
        if not val:
            return []
        try:
            return json.loads(val) if isinstance(val, str) else val
        except Exception:
            return [str(val)]

    return {
        "symbol": row["symbol"],
        "date": str(row["date"]),
        "scenarios": {
            "bull": {"target_price": float(row["bull_price"] or 0), "probability": float(row["bull_prob"] or 0),
                     "key_assumptions": parse_assumptions(row["bull_assumption"])},
            "base": {"target_price": float(row["base_price"] or 0), "probability": float(row["base_prob"] or 0),
                     "key_assumptions": parse_assumptions(row["base_assumption"])},
            "bear": {"target_price": float(row["bear_price"] or 0), "probability": float(row["bear_prob"] or 0),
                     "key_assumptions": parse_assumptions(row["bear_assumption"])},
        },
        "expected_value": float(row["expected_value"] or 0),
        "source": "cache",
    }


async def _generate_ic_memo(symbol: str) -> dict:
    from openai import AsyncOpenAI as _AsyncOpenAI
    client = _AsyncOpenAI(api_key=os.getenv("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com", timeout=30.0, max_retries=2)

    # 取得當前價格（盡力）
    current_price = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT close FROM daily_price WHERE symbol=? ORDER BY date DESC LIMIT 1",
            (symbol,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            current_price = float(row[0])
    except Exception:
        pass

    price_hint = f"當前參考股價：{current_price}" if current_price else "（股價未知）"
    prompt = (
        f"你是投資委員會分析師。請為台股 {symbol} {price_hint} 產生 IC 備忘錄，"
        f"包含三個情境（樂觀/基本/悲觀）。\n\n"
        f"回傳嚴格 JSON 格式（不要有其他文字）：\n"
        f'{{"scenarios": {{'
        f'"bull": {{"target_price": <數字>, "probability": <0-1小數>, "key_assumptions": ["假設1","假設2","假設3"]}}, '
        f'"base": {{"target_price": <數字>, "probability": <0-1小數>, "key_assumptions": ["假設1","假設2"]}}, '
        f'"bear": {{"target_price": <數字>, "probability": <0-1小數>, "key_assumptions": ["假設1","假設2"]}}'
        f"}}}}"
    )
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    data = json.loads(text[text.find("{"):text.rfind("}") + 1])

    # 正規化機率
    s = data["scenarios"]
    total_prob = sum(s[k].get("probability", 0) for k in ("bull", "base", "bear"))
    if total_prob > 0:
        for k in ("bull", "base", "bear"):
            s[k]["probability"] = round(s[k]["probability"] / total_prob, 4)

    ev = (
        s["bull"]["target_price"] * s["bull"]["probability"]
        + s["base"]["target_price"] * s["base"]["probability"]
        + s["bear"]["target_price"] * s["bear"]["probability"]
    )
    upside_pct = ((ev - current_price) / current_price * 100) if current_price else None

    return {
        "symbol": symbol,
        "date": date.today().isoformat(),
        "scenarios": s,
        "expected_value": round(ev, 2),
        "current_price": current_price,
        "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
        "source": "generated",
    }


# ── 多空辯論 ──────────────────────────────────────────────────────────────────

class DebateRequest(BaseModel):
    context: str = ""   # 額外補充資訊（可選）


@router.post("/api/analysis/debate/{symbol}")
async def run_debate(symbol: str, body: DebateRequest | None = None):
    """
    多空辯論：Bull Agent vs Bear Agent 各提 3 個論點，Arbiter 裁決。
    同步執行，預估 15-40 秒。
    """
    _validate(symbol)
    extra_context = (body.context if body else "") or ""

    from openai import AsyncOpenAI as _AsyncOpenAI
    client = _AsyncOpenAI(api_key=os.getenv("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com", timeout=30.0, max_retries=2)

    # 取得基本資料
    price_ctx = _get_price_context(symbol)

    def _new_client():
        from openai import AsyncOpenAI as _C
        return _C(api_key=os.getenv("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com", timeout=30.0, max_retries=2)

    # Bull → Bear 循序執行（bear 拿到 bull 論點逐一反駁，才是真辯論）
    bull_args = await _run_bull_agent(_new_client(), symbol, price_ctx, extra_context)
    bear_args = await _run_bear_agent(_new_client(), symbol, price_ctx, bull_args, extra_context)

    # Arbiter 裁決
    arbiter = await _run_arbiter(client, symbol, bull_args, bear_args)

    from datetime import datetime, timezone
    result = {
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bull_arguments": bull_args,
        "bear_arguments": bear_args,
        "arbiter": arbiter,
    }

    # AI Audit：以 arbiter verdict 作為方向預測
    try:
        from services.audit import record_prediction
        verdict = arbiter.get("verdict", "neutral").lower()
        direction = "up" if "多" in verdict or "bull" in verdict else "down" if "空" in verdict or "bear" in verdict else "neutral"
        confidence = float(arbiter.get("confidence", 0.5))
        record_prediction(symbol, direction, confidence=confidence)
    except Exception:
        pass

    return result


def _get_price_context(symbol: str) -> str:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT close, date FROM daily_price WHERE symbol=? ORDER BY date DESC LIMIT 1",
            (symbol,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return f"最近收盤價 {row[0]}（{row[1]}）"
    except Exception:
        pass
    return "（價格資料不可用）"


async def _run_bull_agent(client, symbol: str, price_ctx: str, extra: str) -> list[dict]:
    prompt = (
        f"你是多方（Bull）分析師，為台股 {symbol} {price_ctx} 提出 3 個最有力的看多論點。\n"
        f"{f'補充資訊：{extra}' if extra else ''}\n\n"
        f"每個論點格式：{{\"title\": \"<標題>\", \"argument\": \"<詳細說明，至少2句>\", \"evidence\": \"<具體數據或事實>\"}}\n"
        f"回傳 JSON 陣列：[論點1, 論點2, 論點3]"
    )
    return await _parse_arguments(client, prompt)


async def _run_bear_agent(client, symbol: str, price_ctx: str, bull_args: list, extra: str) -> list[dict]:
    lines = [
        f"你是空方（Bear）分析師，為台股 {symbol} {price_ctx} 提出 3 個最有力的看空論點。",
    ]
    if extra:
        lines.append(f"補充資訊：{extra}")
    if bull_args:
        lines.append(f"多方論點（請逐一反駁）：{json.dumps(bull_args, ensure_ascii=False)}")
    lines.extend([
        '每個論點格式：{"title": "<標題>", "argument": "<詳細說明，至少2句>", "evidence": "<具體數據或事實>"}',
        "回傳 JSON 陣列：[論點1, 論點2, 論點3]",
    ])
    prompt = "\n".join(lines)
    return await _parse_arguments(client, prompt)


async def _run_arbiter(client, symbol: str, bull_args: list, bear_args: list) -> dict:
    bull_text = json.dumps(bull_args, ensure_ascii=False)
    bear_text = json.dumps(bear_args, ensure_ascii=False)
    prompt = (
        f"你是中立裁判（Arbiter），評估台股 {symbol} 的多空辯論並給出裁決。\n\n"
        f"多方論點：{bull_text}\n空方論點：{bear_text}\n\n"
        f"回傳 JSON：{{\"verdict\": \"bull|bear|neutral\", \"confidence\": <60-100整數>, "
        f"\"rationale\": \"<裁決理由，至少3句>\", \"key_risk\": \"<最重要下行風險>\"}}"
    )
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


async def _parse_arguments(client, prompt: str) -> list[dict]:
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    return json.loads(text[start:end]) if start >= 0 else []
