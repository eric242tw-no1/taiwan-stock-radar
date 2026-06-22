"""Tests for market_anomaly_agent — three anomaly conditions."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_ohlcv(closes: list[float], volumes: list[int] | None = None) -> list[dict]:
    rows = []
    for i, c in enumerate(closes):
        rows.append({"close": c, "open": c, "volume": (volumes[i] if volumes else 1000)})
    return rows


@patch("agents.market_anomaly_agent._is_trading_hours", return_value=True)
@patch("agents.market_anomaly_agent.send_message", new_callable=AsyncMock)
@patch("agents.market_anomaly_agent.fetch_ohlcv")
@patch("agents.market_anomaly_agent.get_cached_tw_market")
@pytest.mark.asyncio
async def test_gap_anomaly(mock_market, mock_ohlcv, mock_telegram, mock_hours):
    """Gap >3% should trigger an alert."""
    mock_market.return_value = {
        "stocks": [{"symbol": "2330", "name": "台積電", "close": 600, "open": 620, "volume": 5000}]
    }
    # prev_close=580, open=620 → gap = (620-580)/580 ≈ 6.9% > 3%
    mock_ohlcv.return_value = _make_ohlcv([580, 600])

    from agents.market_anomaly_agent import scan_anomalies
    results = await scan_anomalies()

    assert len(results) == 1
    assert any("跳空" in a for a in results[0]["anomalies"])
    mock_telegram.assert_called_once()


@patch("agents.market_anomaly_agent._is_trading_hours", return_value=True)
@patch("agents.market_anomaly_agent.send_message", new_callable=AsyncMock)
@patch("agents.market_anomaly_agent.fetch_ohlcv")
@patch("agents.market_anomaly_agent.get_cached_tw_market")
@pytest.mark.asyncio
async def test_volume_surge_anomaly(mock_market, mock_ohlcv, mock_telegram, mock_hours):
    """Volume >3× 20-day avg should trigger an alert."""
    avg_vol = 1000
    big_vol = 4000  # 4× avg
    mock_market.return_value = {
        "stocks": [{"symbol": "2330", "name": "台積電", "close": 600, "open": 598, "volume": big_vol}]
    }
    # 20 normal rows + 1 big-volume row (current, not in ohlcv)
    rows = _make_ohlcv([600] * 22, [avg_vol] * 22)
    mock_ohlcv.return_value = rows

    from agents.market_anomaly_agent import scan_anomalies
    results = await scan_anomalies()

    assert any("爆量" in a for a in results[0]["anomalies"])


@patch("agents.market_anomaly_agent._is_trading_hours", return_value=True)
@patch("agents.market_anomaly_agent.send_message", new_callable=AsyncMock)
@patch("agents.market_anomaly_agent.fetch_ohlcv")
@patch("agents.market_anomaly_agent.get_cached_tw_market")
@pytest.mark.asyncio
async def test_limit_up_anomaly(mock_market, mock_ohlcv, mock_telegram, mock_hours):
    """Price at +10% limit should trigger an alert."""
    prev_close = 600.0
    limit_up = round(prev_close * 1.10, 2)  # 660.0
    mock_market.return_value = {
        "stocks": [{"symbol": "2330", "name": "台積電", "close": limit_up, "open": 610, "volume": 8000}]
    }
    mock_ohlcv.return_value = _make_ohlcv([prev_close, limit_up])

    from agents.market_anomaly_agent import scan_anomalies
    results = await scan_anomalies()

    assert any("漲停" in a for a in results[0]["anomalies"])


@patch("agents.market_anomaly_agent._is_trading_hours", return_value=False)
@pytest.mark.asyncio
async def test_outside_trading_hours(mock_hours):
    """Outside trading hours should return empty list immediately."""
    from agents.market_anomaly_agent import scan_anomalies
    results = await scan_anomalies()
    assert results == []
