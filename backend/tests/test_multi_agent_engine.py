"""Multi-Agent Engine 單元測試：使用 mock Claude API 驗證 Orchestrator 協調流程。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from factor_engine.output_formatter import FactorBundle, TechnicalFactors, ChipsFactors, bundle


def _make_bundle() -> FactorBundle:
    tf = TechnicalFactors(rsi_14=55.0, macd=0.5, ma20=120.0, bias_20=2.1, atr_14=3.2)
    cf = ChipsFactors(foreign_net=1000, investment_net=200)
    return bundle("2330", tf, cf)


def _fake_claude_response(score: int = 50, summary: str = "測試摘要") -> MagicMock:
    import json
    content = MagicMock()
    content.text = json.dumps({"score": score, "summary": summary})
    msg = MagicMock()
    msg.content = [content]
    return msg


@pytest.mark.asyncio
async def test_orchestrator_returns_report():
    from agents.multi_agent_engine import Orchestrator

    fb = _make_bundle()

    with patch("agents.multi_agent_engine._load_active_prompt", return_value=None), \
         patch("agents.multi_agent_engine._get_macro_summary", return_value="N/A"), \
         patch("anthropic.AsyncAnthropic") as mock_cls:

        instance = mock_cls.return_value
        instance.messages.create = AsyncMock(return_value=_fake_claude_response(40, "看多訊號"))

        orc = Orchestrator()
        # 注入 mock client 至所有 agent
        for a in orc._parallel_agents + orc._serial_agents:
            a._client = instance

        report = await orc.analyze("2330", fb)

    assert report.symbol == "2330"
    assert report.signal in ("buy", "sell", "watch")
    assert len(report.agents) == 6
    assert all(a.status in ("ok", "failed") for a in report.agents)


@pytest.mark.asyncio
async def test_orchestrator_handles_agent_failure():
    """單一 Agent 失敗時，其餘正常輸出，report.signal 仍回傳。"""
    from agents.multi_agent_engine import Orchestrator

    fb = _make_bundle()

    call_count = 0

    async def _sometimes_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:   # 第二個 Agent 失敗
            raise ValueError("模擬 API 錯誤")
        return _fake_claude_response(50, "OK")

    with patch("agents.multi_agent_engine._load_active_prompt", return_value=None), \
         patch("agents.multi_agent_engine._get_macro_summary", return_value="N/A"), \
         patch("anthropic.AsyncAnthropic") as mock_cls:

        instance = mock_cls.return_value
        instance.messages.create = AsyncMock(side_effect=_sometimes_fail)

        orc = Orchestrator()
        for a in orc._parallel_agents + orc._serial_agents:
            a._client = instance

        report = await orc.analyze("2330", fb)

    assert report.signal in ("buy", "sell", "watch")
    failed = [a for a in report.agents if a.status == "failed"]
    assert len(failed) >= 1


@pytest.mark.asyncio
async def test_weighted_score_range():
    """加權評分應在 -100 ~ +100 範圍內。"""
    from agents.multi_agent_engine import Orchestrator

    fb = _make_bundle()

    with patch("agents.multi_agent_engine._load_active_prompt", return_value=None), \
         patch("agents.multi_agent_engine._get_macro_summary", return_value="N/A"), \
         patch("anthropic.AsyncAnthropic") as mock_cls:

        instance = mock_cls.return_value
        instance.messages.create = AsyncMock(return_value=_fake_claude_response(80, "極度看多"))

        orc = Orchestrator()
        for a in orc._parallel_agents + orc._serial_agents:
            a._client = instance

        report = await orc.analyze("2330", fb)

    assert -100 <= report.weighted_score <= 100
