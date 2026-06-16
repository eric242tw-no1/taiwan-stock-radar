"""
Multi-Agent Engine — 六專責 Agent + Orchestrator 協調架構。

流程：
  並行 → TechnicalAnalystAgent, ChipsAnalystAgent, MacroAnalystAgent
  串行 → RiskReviewerAgent(depends on parallel), TradeExecutorAgent, DevilsAdvocateAgent
  整合 → Orchestrator 加權評分 → MultiAgentReport
"""
from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from factor_engine.output_formatter import FactorBundle

logger = logging.getLogger(__name__)

MODEL = "deepseek-chat"
_DEEPSEEK_BASE = "https://api.deepseek.com"


# ── 資料結構 ─────────────────────────────────────────────────────────────────

@dataclass
class AgentOutput:
    agent: str
    score: int | None       # -100 ~ +100
    summary: str
    details: dict = field(default_factory=dict)
    status: str = "ok"      # "ok" | "failed" | "skipped"


@dataclass
class MultiAgentReport:
    symbol: str
    weighted_score: float   # -100 ~ +100
    signal: str             # "buy" | "sell" | "watch"
    agents: list[AgentOutput] = field(default_factory=list)
    rationale: str = ""


# ── Agent 基底 ───────────────────────────────────────────────────────────────

class _BaseAgent:
    name: str = "base"
    weight: float = 1.0

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=_DEEPSEEK_BASE,
        )

    async def analyze(self, symbol: str, factor_bundle: FactorBundle, context: dict | None = None) -> AgentOutput:
        try:
            prompt = self._build_prompt(symbol, factor_bundle, context or {})
            active_prompt = _load_active_prompt(self.name) or prompt
            score, summary, details = await self._call_llm(active_prompt)
            return AgentOutput(agent=self.name, score=score, summary=summary, details=details)
        except Exception as exc:
            logger.warning("%s failed for %s: %s", self.name, symbol, exc)
            return AgentOutput(agent=self.name, score=None, summary=str(exc), status="failed")

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        raise NotImplementedError

    async def _call_llm(self, prompt: str) -> tuple[int | None, str, dict]:
        import json
        resp = await self._client.chat.completions.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        try:
            # 嘗試解析 JSON
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
            score = int(data.get("score", 0))
            score = max(-100, min(100, score))
            summary = str(data.get("summary", ""))
            details = {k: v for k, v in data.items() if k not in ("score", "summary")}
            return score, summary, details
        except Exception:
            # fallback：嘗試從文字抽取數字
            import re
            nums = re.findall(r"[-+]?\d+", text)
            score = int(nums[0]) if nums else 0
            score = max(-100, min(100, score))
            return score, text[:200], {}


# ── 六個專責 Agent ────────────────────────────────────────────────────────────

class TechnicalAnalystAgent(_BaseAgent):
    name = "technical_analyst"
    weight = 0.25

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        t = fb.technical
        return (
            f"你是專業技術分析師。分析台股 {symbol} 的技術指標，給出評分（-100 最看空，+100 最看多）。\n\n"
            f"技術指標：RSI={t.rsi_14}, MACD={t.macd}, MACD信號={t.macd_signal}, "
            f"KD-K={t.kd_k}, KD-D={t.kd_d}, MA20={t.ma20}, MA60={t.ma60}, "
            f"ATR={t.atr_14}, 乖離率={t.bias_20}\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-100到+100整數>, \"summary\": \"<2句話摘要>\", "
            f"\"trend\": \"<uptrend|downtrend|sideways>\", \"key_signal\": \"<最重要訊號>\"}}"
        )


class ChipsAnalystAgent(_BaseAgent):
    name = "chips_analyst"
    weight = 0.20

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        c = fb.chips
        return (
            f"你是籌碼分析師。分析台股 {symbol} 的法人與籌碼動向，給出評分（-100 最看空，+100 最看多）。\n\n"
            f"外資買賣超：{c.foreign_net}張, 投信：{c.investment_net}張, "
            f"自營商：{c.dealer_net}張, 融資餘額：{c.margin_balance}張, "
            f"融券餘額：{c.short_balance}張, 大戶集保≥400張：{c.holders_over_400}人\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-100到+100整數>, \"summary\": \"<2句話摘要>\", "
            f"\"institutional_trend\": \"<accumulate|distribute|neutral>\"}}"
        )


class MacroAnalystAgent(_BaseAgent):
    name = "macro_analyst"
    weight = 0.15

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        macro = context.get("macro", "暫無總經資料")
        return (
            f"你是總經分析師。根據當前宏觀環境評估台股 {symbol} 的投資環境，給出評分（-100 最看空，+100 最看多）。\n\n"
            f"總經環境摘要：{macro}\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-100到+100整數>, \"summary\": \"<2句話摘要>\", "
            f"\"macro_stance\": \"<risk-on|risk-off|neutral>\"}}"
        )


class RiskReviewerAgent(_BaseAgent):
    name = "risk_reviewer"
    weight = 0.20

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        parallel_scores = context.get("parallel_scores", {})
        return (
            f"你是風控審查員。評估台股 {symbol} 的下行風險，給出評分（-100 風險極高，+100 風險極低）。\n\n"
            f"ATR(14)={fb.technical.atr_14}, RSI={fb.technical.rsi_14}, 乖離率={fb.technical.bias_20}\n"
            f"技術面評分={parallel_scores.get('technical_analyst')}, 籌碼面評分={parallel_scores.get('chips_analyst')}\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-100到+100整數>, \"summary\": \"<2句話摘要>\", "
            f"\"stop_loss_pct\": <建議停損百分比>, \"risk_level\": \"<low|medium|high>\"}}"
        )


class TradeExecutorAgent(_BaseAgent):
    name = "trade_executor"
    weight = 0.10

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        parallel_scores = context.get("parallel_scores", {})
        risk_score = context.get("risk_score", 0)
        return (
            f"你是交易執行員。根據分析結果建議 {symbol} 的進場策略，給出執行積極度評分（-100 強烈出場，+100 積極進場）。\n\n"
            f"綜合評分：技術={parallel_scores.get('technical_analyst')}, "
            f"籌碼={parallel_scores.get('chips_analyst')}, 風控={risk_score}\n"
            f"MA20={fb.technical.ma20}, ATR={fb.technical.atr_14}\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-100到+100整數>, \"summary\": \"<2句話摘要>\", "
            f"\"entry_timing\": \"<immediate|wait_pullback|avoid>\", "
            f"\"position_size_pct\": <建議倉位比例1-20>}}"
        )


class DevilsAdvocateAgent(_BaseAgent):
    name = "devils_advocate"
    weight = 0.10

    def _build_prompt(self, symbol: str, fb: FactorBundle, context: dict) -> str:
        consensus_score = context.get("consensus_score", 0)
        return (
            f"你是魔鬼代言人。挑戰目前對 {symbol} 的主流看法（當前共識評分={consensus_score}），"
            f"提出最有力的反向論點。評分代表反向修正程度（-50 大幅看空修正，+50 大幅看多修正，0 維持）。\n\n"
            f"請用 JSON 格式回應：{{\"score\": <-50到+50整數>, \"summary\": \"<2句話反向觀點>\", "
            f"\"key_risk\": \"<最關鍵的尾部風險>\"}}"
        )


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """協調六 Agent，加權整合最終評分。"""

    def __init__(self):
        self._parallel_agents = [
            TechnicalAnalystAgent(),
            ChipsAnalystAgent(),
            MacroAnalystAgent(),
        ]
        self._serial_agents = [
            RiskReviewerAgent(),
            TradeExecutorAgent(),
            DevilsAdvocateAgent(),
        ]

    async def analyze(self, symbol: str, factor_bundle: FactorBundle, context: dict | None = None) -> MultiAgentReport:
        ctx = context or {}
        ctx.setdefault("macro", _get_macro_summary())

        # ── 1. 並行執行技術/籌碼/總經 ─────────────────────────────
        parallel_outputs = await asyncio.gather(
            *[a.analyze(symbol, factor_bundle, ctx) for a in self._parallel_agents],
            return_exceptions=False,
        )

        parallel_scores = {
            o.agent: o.score for o in parallel_outputs if o.status == "ok" and o.score is not None
        }
        ctx["parallel_scores"] = parallel_scores

        # ── 2. 串行執行風控/執行員/魔鬼代言人 ────────────────────
        serial_outputs: list[AgentOutput] = []
        consensus = _weighted_avg(parallel_outputs, self._parallel_agents)

        for agent in self._serial_agents:
            if agent.name == "devils_advocate":
                ctx["consensus_score"] = consensus
            elif agent.name == "risk_reviewer":
                pass
            elif agent.name == "trade_executor":
                ctx["risk_score"] = next(
                    (o.score for o in serial_outputs if o.agent == "risk_reviewer"), 0
                )
            out = await agent.analyze(symbol, factor_bundle, ctx)
            serial_outputs.append(out)

        all_outputs = list(parallel_outputs) + serial_outputs
        all_agents  = self._parallel_agents + self._serial_agents

        # ── 3. 加權整合 ────────────────────────────────────────────
        weighted_score = _weighted_avg(all_outputs, all_agents)
        signal = "buy" if weighted_score > 30 else ("sell" if weighted_score < -30 else "watch")

        return MultiAgentReport(
            symbol=symbol,
            weighted_score=round(weighted_score, 1),
            signal=signal,
            agents=all_outputs,
            rationale=_build_rationale(all_outputs, weighted_score),
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _weighted_avg(outputs: list[AgentOutput], agents: list[_BaseAgent]) -> float:
    total_weight = 0.0
    weighted_sum = 0.0
    agent_map = {a.name: a.weight for a in agents}
    for out in outputs:
        if out.status == "ok" and out.score is not None:
            w = agent_map.get(out.agent, 0)
            weighted_sum += out.score * w
            total_weight += w
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _build_rationale(outputs: list[AgentOutput], score: float) -> str:
    parts = [f"加權評分 {score:+.1f}。"]
    for o in outputs:
        if o.status == "ok":
            parts.append(f"[{o.agent}] {o.summary}")
    return " ".join(parts)


def _get_macro_summary() -> str:
    """取得已快取的總經摘要（來自 morning_brief）。"""
    try:
        from services.twse_fetcher import get_cached_tw_market
        from services.data_fetcher import get_cached_us_indices
        tw = get_cached_tw_market()
        us = get_cached_us_indices()
        tw_idx = tw.get("index", {})
        return (
            f"台股加權指數={tw_idx.get('close', 'N/A')}, "
            f"S&P500={us.get('sp500', {}).get('price', 'N/A')}, "
            f"VIX={us.get('vix', {}).get('level', 'N/A')}"
        )
    except Exception:
        return "N/A"


def _load_active_prompt(agent_name: str) -> str | None:
    """查詢 strategy_versions 表取得 active prompt，無則回傳 None（使用預設）。"""
    from db import get_conn
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT sv.prompt_template FROM strategy_versions sv "
            "JOIN strategies s ON s.id = sv.strategy_id "
            "WHERE s.name = ? AND sv.is_active = 1 LIMIT 1",
            (agent_name,),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None
