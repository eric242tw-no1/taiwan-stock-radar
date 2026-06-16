"""Morning Brief Agent — generates a daily AI summary at 08:30 Taiwan time."""
import asyncio
import json
import logging
import os
from datetime import date

from db import get_conn

logger = logging.getLogger(__name__)


def _aggregate_market_data() -> dict:
    """Collect market overview, screener top-5, and alert count from in-memory caches."""
    from services.twse_fetcher import get_cached_tw_market
    from services.data_fetcher import get_cached_us_indices

    tw = get_cached_tw_market()
    us = get_cached_us_indices()

    # alert count from DB
    alert_count = 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM tv_signals WHERE status='pending' "
            "AND created_at >= datetime('now','-1 day')"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            alert_count = row[0]
    except Exception as exc:
        logger.warning("morning_brief: alert count failed — %s", exc)

    return {
        "tw_market": tw,
        "us_indices": us,
        "alert_count": alert_count,
    }


async def _call_llm(market_data: dict) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com")
    prompt = (
        "你是台股投資助理。根據以下市場資料，用繁體中文撰寫一份簡潔的早晨市場摘要（200字以內）。\n\n"
        f"台股市場：{json.dumps(market_data['tw_market'], ensure_ascii=False, default=str)}\n"
        f"美股指數：{json.dumps(market_data['us_indices'], ensure_ascii=False, default=str)}\n"
        f"待處理警報數：{market_data['alert_count']}\n\n"
        "請涵蓋：主要指數表現、盤面重點、今日需關注事項。"
    )
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _upsert_report(today: date, report_json: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_ai_report (date, report_json) VALUES (?,?) ON CONFLICT (date) DO NOTHING",
        (str(today), json.dumps(report_json, ensure_ascii=False, default=str)),
    )
    conn.commit()
    conn.close()


DEEP_ANALYSIS_ENABLED = os.getenv("MORNING_BRIEF_DEEP_ANALYSIS", "false").lower() == "true"
DEEP_ANALYSIS_SYMBOL  = os.getenv("MORNING_BRIEF_DEEP_SYMBOL", "2330")   # 每日深度分析標的


async def generate_morning_brief() -> None:
    """Main entry point called by APScheduler at 08:30 Mon–Fri."""
    today = date.today()
    logger.info("morning_brief: generating for %s", today)
    try:
        market_data = _aggregate_market_data()
        async with asyncio.timeout(30):
            summary = await _call_llm(market_data)

        report = {"date": str(today), "summary": summary, "market_data": market_data}

        # 選配：深度多 Agent 分析（MORNING_BRIEF_DEEP_ANALYSIS=true 才啟用）
        if DEEP_ANALYSIS_ENABLED:
            deep = await _run_deep_analysis(DEEP_ANALYSIS_SYMBOL)
            if deep:
                report["deep_analysis"] = deep

        _upsert_report(today, report)
        logger.info("morning_brief: stored for %s", today)
    except TimeoutError:
        logger.error("morning_brief: Claude API timed out — skipping")
    except Exception as exc:
        logger.error("morning_brief: failed — %s", exc)


async def _run_deep_analysis(symbol: str) -> dict | None:
    """呼叫 Orchestrator 對指定股票做深度六 Agent 分析，附加至晨報。"""
    try:
        import pandas as pd
        from factor_engine import technical as fe_tech, chips as fe_chips
        from factor_engine.output_formatter import bundle as fe_bundle
        from agents.multi_agent_engine import Orchestrator
        from services.ohlcv_service import fetch_ohlcv

        rows = fetch_ohlcv(f"{symbol}.TW", period="90d")
        if not rows:
            return None
        df = pd.DataFrame(rows)
        tech = fe_tech.compute(symbol, df)
        chips = fe_chips.compute(symbol)
        fb = fe_bundle(symbol, tech, chips)

        orchestrator = Orchestrator()
        async with asyncio.timeout(60):
            report = await orchestrator.analyze(symbol, fb)

        return {
            "symbol": symbol,
            "weighted_score": report.weighted_score,
            "signal": report.signal,
            "rationale": report.rationale,
        }
    except Exception as exc:
        logger.warning("morning_brief deep_analysis failed: %s", exc)
        return None
