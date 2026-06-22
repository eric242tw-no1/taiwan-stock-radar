"""Tests for morning_brief_agent — mock Claude API, test UPSERT dedup."""
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def mock_market_data():
    return {
        "tw_market": {"taiex": 18000, "change_pct": 0.5},
        "us_indices": {"sp500": 5200},
        "alert_count": 3,
    }


@patch("agents.morning_brief_agent._aggregate_market_data")
@patch("agents.morning_brief_agent._upsert_report")
@patch("agents.morning_brief_agent._call_claude", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_generate_morning_brief_success(mock_claude, mock_upsert, mock_aggregate, mock_market_data):
    mock_aggregate.return_value = mock_market_data
    mock_claude.return_value = "今日台股小幅上漲，科技股表現強勁。"

    from agents.morning_brief_agent import generate_morning_brief
    await generate_morning_brief()

    mock_claude.assert_called_once()
    mock_upsert.assert_called_once()
    call_args = mock_upsert.call_args
    assert call_args[0][0] == date.today()
    assert "summary" in call_args[0][1]


@patch("agents.morning_brief_agent._aggregate_market_data")
@patch("agents.morning_brief_agent._upsert_report")
@patch("agents.morning_brief_agent._call_claude", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_generate_morning_brief_timeout(mock_claude, mock_upsert, mock_aggregate, mock_market_data):
    """On Claude timeout, no report should be stored."""
    import asyncio
    mock_aggregate.return_value = mock_market_data
    mock_claude.side_effect = TimeoutError

    from agents.morning_brief_agent import generate_morning_brief
    await generate_morning_brief()

    mock_upsert.assert_not_called()


@patch("agents.morning_brief_agent._get_conn")
def test_upsert_report_dedup(mock_conn):
    """UPSERT ON CONFLICT DO NOTHING should not raise on duplicate date."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn_obj = MagicMock()
    mock_conn_obj.__enter__ = lambda s: s
    mock_conn_obj.__exit__ = MagicMock(return_value=False)
    mock_conn_obj.cursor.return_value = mock_cursor
    mock_conn.return_value = mock_conn_obj

    from agents.morning_brief_agent import _upsert_report
    today = date.today()
    report = {"date": str(today), "summary": "test"}
    _upsert_report(today, report)

    mock_cursor.execute.assert_called_once()
    sql = mock_cursor.execute.call_args[0][0]
    assert "ON CONFLICT" in sql
    assert "DO NOTHING" in sql
