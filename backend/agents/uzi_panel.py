"""
UZI 評審團 — 三位具名虛擬評審（動能派 35%、價值派 35%、風控派 30%）加權評分。
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from factor_engine.output_formatter import FactorBundle

logger = logging.getLogger(__name__)

MODEL = "deepseek-chat"
_DEEPSEEK_BASE = "https://api.deepseek.com"

REVIEWERS = [
    {
        "name": "動能派",
        "persona": "你是動能派投資人，著重技術指標動能、價格突破、成交量放大。",
        "weight": 0.35,
    },
    {
        "name": "價值派",
        "persona": "你是價值派投資人，著重估值合理性、股息、財務健全度與長期成長。",
        "weight": 0.35,
    },
    {
        "name": "風控派",
        "persona": "你是風控派投資人，著重波動度控制、下行風險、流動性與倉位管理。",
        "weight": 0.30,
    },
]

GRADE_MAP = [
    (75, "強力買進"),
    (60, "買進"),
    (40, "觀望"),
    (25, "賣出"),
    (0,  "強力賣出"),
]


@dataclass
class ReviewerScore:
    reviewer: str
    score: float        # 0-100
    reason: str
    weight: float


@dataclass
class UZIPanelResult:
    symbol: str
    weighted_score: float
    grade: str
    reviewers: list[ReviewerScore] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "weighted_score": self.weighted_score,
            "grade": self.grade,
            "reviewers": [
                {"reviewer": r.reviewer, "score": r.score, "reason": r.reason, "weight": r.weight}
                for r in self.reviewers
            ],
        }


class UZIPanel:

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=_DEEPSEEK_BASE,
        )

    async def evaluate(self, symbol: str, factor_bundle: FactorBundle) -> UZIPanelResult:
        tasks = [self._ask_reviewer(symbol, factor_bundle, r) for r in REVIEWERS]
        scores = await asyncio.gather(*tasks, return_exceptions=True)

        reviewer_results: list[ReviewerScore] = []
        for reviewer, score in zip(REVIEWERS, scores):
            if isinstance(score, Exception) or score is None:
                logger.warning("UZIPanel: %s 評分失敗 — %s", reviewer["name"], score)
                reviewer_results.append(ReviewerScore(
                    reviewer=reviewer["name"], score=50.0,
                    reason="評分失敗，使用中性分數", weight=reviewer["weight"],
                ))
            else:
                reviewer_results.append(score)

        weighted = sum(r.score * r.weight for r in reviewer_results)
        grade = _to_grade(weighted)

        return UZIPanelResult(
            symbol=symbol,
            weighted_score=round(weighted, 1),
            grade=grade,
            reviewers=reviewer_results,
        )

    async def _ask_reviewer(self, symbol: str, fb: FactorBundle, reviewer: dict) -> ReviewerScore:
        t = fb.technical
        c = fb.chips
        prompt = (
            f"{reviewer['persona']}\n\n"
            f"請評估台股 {symbol}：\n"
            f"技術：RSI={t.rsi_14}, MACD={t.macd}, MA20={t.ma20}, 乖離率={t.bias_20}\n"
            f"籌碼：外資{c.foreign_net}張, 投信{c.investment_net}張, 融資{c.margin_balance}張\n\n"
            f"給出 0-100 分（100=極度看多），並用 2 句話說明理由。\n"
            f"JSON 格式：{{\"score\": <0-100整數>, \"reason\": \"<2句理由>\"}}"
        )
        resp = await self._client.chat.completions.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
        score = max(0.0, min(100.0, float(data.get("score", 50))))
        return ReviewerScore(
            reviewer=reviewer["name"],
            score=score,
            reason=str(data.get("reason", "")),
            weight=reviewer["weight"],
        )


def _to_grade(score: float) -> str:
    for threshold, label in GRADE_MAP:
        if score >= threshold:
            return label
    return "強力賣出"
