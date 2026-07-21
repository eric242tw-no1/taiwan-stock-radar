"""
Tests for routers/market.py

Covers:
  - /top-movers: codes param overrides TRACKED_SYMBOLS (A3 fix)
  - /top-movers: falls back to TRACKED_SYMBOLS when no codes param
  - /leaders:    codes param filters indicator cache (A3 fix)
  - /leaders:    returns empty list gracefully when no indicators available
  - /buffett:    endpoint returns ratio + metadata
"""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app

client = TestClient(app)


# ── helpers ────────────────────────────────────────────────────────────────────

def _mock_yf_ticker(price: float, prev_close: float):
    info      = MagicMock()
    info.last_price     = price
    info.previous_close = prev_close
    ticker    = MagicMock()
    ticker.fast_info    = info
    return ticker


def _tickers_obj(data: dict):
    """Mock yf.Tickers with per-symbol fast_info."""
    obj    = MagicMock()
    tickers_map = {sym: _mock_yf_ticker(*prices) for sym, prices in data.items()}
    obj.tickers = tickers_map
    return obj


# ── /top-movers ────────────────────────────────────────────────────────────────

class TestTopMovers:
    def setup_method(self):
        import routers.market as m
        m._top_movers_cache = {"ts": 0, "data": [], "pool_key": ""}

    def test_returns_200(self):
        with patch("yfinance.Tickers", return_value=_tickers_obj({})):
            resp = client.get("/api/market/top-movers")
        assert resp.status_code == 200

    def test_response_has_results_key(self):
        with patch("yfinance.Tickers", return_value=_tickers_obj({})):
            data = client.get("/api/market/top-movers").json()
        assert "results" in data

    def test_codes_param_restricts_symbols(self):
        """When codes=2330,2317 is passed, only those two symbols should be fetched."""

        captured = []

        def fake_tickers(symbols_str):
            captured.append(symbols_str)
            return _tickers_obj({})

        with patch("yfinance.Tickers", side_effect=fake_tickers):
            client.get("/api/market/top-movers?codes=2330,2317")

        assert len(captured) == 1
        fetched = captured[0].split()
        assert set(fetched) == {"2330.TW", "2317.TW"}

    def test_no_codes_param_uses_tracked_symbols(self):
        """Without codes param, TRACKED_SYMBOLS should be used."""
        import routers.market as m

        captured = []

        def fake_tickers(symbols_str):
            captured.append(symbols_str)
            return _tickers_obj({})

        with patch("yfinance.Tickers", side_effect=fake_tickers):
            client.get("/api/market/top-movers")

        fetched_set = set(captured[0].split())
        tracked_set = set(m.TRACKED_SYMBOLS)
        assert fetched_set == tracked_set

    def test_results_sorted_by_chg_pct_descending(self):
        """Results should be sorted best gainer first."""
        mock_data = {
            "2330.TW": (600.0, 580.0),   # +3.4%
            "2317.TW": (100.0, 102.0),   # -2.0%
            "2454.TW": (900.0, 880.0),   # +2.3%
        }
        import routers.market as m
        m._top_movers_cache = {"ts": 0, "data": [], "pool_key": ""}

        with patch("yfinance.Tickers", return_value=_tickers_obj(mock_data)):
            resp = client.get("/api/market/top-movers?codes=2330,2317,2454&limit=3")

        results = resp.json()["results"]
        chg_pcts = [r["chg_pct"] for r in results]
        assert chg_pcts == sorted(chg_pcts, reverse=True)


# ── /leaders ──────────────────────────────────────────────────────────────────

class TestLeaders:
    def setup_method(self):
        import routers.market as m
        m._leaders_cache = {"ts": 0, "data": [], "pool_key": ""}

    def test_returns_200(self):
        with patch("services.indicator_service.get_all_indicators", return_value={}):
            resp = client.get("/api/market/leaders")
        assert resp.status_code == 200

    def test_empty_when_no_indicators(self):
        with patch("services.indicator_service.get_all_indicators", return_value={}):
            data = client.get("/api/market/leaders").json()
        assert data["results"] == []

    def test_codes_param_filters_indicators(self):
        """When codes=2330 is passed, only 2330.TW indicator should be evaluated."""
        import routers.market as m
        m._leaders_cache = {"ts": 0, "data": [], "pool_key": ""}
        all_ind = {
            "2330.TW": {"ticker": "2330.TW", "rsi14": 65.0, "macd_hist": 0.5,
                        "k": 70.0, "d": 60.0, "close": 800.0, "atr14": 5.0},
            "2317.TW": {"ticker": "2317.TW", "rsi14": 70.0, "macd_hist": 1.0,
                        "k": 75.0, "d": 65.0, "close": 100.0, "atr14": 2.0},
        }
        # patch at the import site (routers.market imports get_all_indicators directly)
        with patch("routers.market.get_all_indicators", return_value=all_ind):
            resp = client.get("/api/market/leaders?codes=2330")

        results = resp.json()["results"]
        codes = [r["code"] for r in results]
        assert "2317" not in codes
        assert "2330" in codes

    def test_score_fields_present(self):
        import routers.market as m
        m._leaders_cache = {"ts": 0, "data": [], "pool_key": ""}
        all_ind = {
            "2330.TW": {"ticker": "2330.TW", "rsi14": 65.0, "macd_hist": 0.5,
                        "k": 70.0, "d": 60.0, "close": 800.0, "atr14": 5.0},
        }
        with patch("routers.market.get_all_indicators", return_value=all_ind):
            resp = client.get("/api/market/leaders?codes=2330")

        results = resp.json()["results"]
        if results:
            r = results[0]
            assert "score" in r
            assert "rsi"   in r
            assert "code"  in r

    def test_leaders_filters_weak_signals(self):
        """Stocks with RSI < 45 or MACD hist ≤ 0 should be excluded."""
        import routers.market as m
        m._leaders_cache = {"ts": 0, "data": [], "pool_key": ""}
        all_ind = {
            "2330.TW": {"ticker": "2330.TW", "rsi14": 40.0, "macd_hist": -0.1,
                        "k": 50.0, "d": 55.0, "close": 800.0, "atr14": 5.0},
        }
        with patch("routers.market.get_all_indicators", return_value=all_ind):
            resp = client.get("/api/market/leaders?codes=2330")

        assert resp.json()["results"] == []


# ── /buffett ───────────────────────────────────────────────────────────────────

class TestBuffettEndpoint:
    def test_returns_200(self):
        mock_data = {
            "ratio": 471.0,
            "market_cap_yi": 1_300_000.0,
            "gdp_yi": 280_000,
            "gdp_year": 2026,
            "source": "taiex_estimated",
            "updated_at": "2026-06-09T22:00:00",
        }
        # patch at the import site in routers.market
        with patch("routers.market.get_cached_buffett", return_value=mock_data):
            resp = client.get("/api/market/buffett")

        assert resp.status_code == 200

    def test_response_contains_ratio(self):
        mock_data = {
            "ratio": 471.0,
            "market_cap_yi": 1_300_000.0,
            "gdp_yi": 280_000,
            "gdp_year": 2026,
            "source": "taiex_estimated",
            "updated_at": "2026-06-09T22:00:00",
        }
        with patch("routers.market.get_cached_buffett", return_value=mock_data):
            data = client.get("/api/market/buffett").json()

        assert data["ratio"] == 471.0
        assert data["source"] == "taiex_estimated"
        assert data["gdp_yi"] == 280_000
