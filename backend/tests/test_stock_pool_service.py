"""
Tests for services/stock_pool_service.py

Covers:
  - get_pool() returns _DEFAULT_POOL when DB is unavailable (A1 fix)
  - get_tickers() formats symbols correctly
  - _DEFAULT_POOL has the expected structure
"""
from unittest.mock import patch

import services.stock_pool_service as sps


class TestDefaultPool:
    def test_default_pool_not_empty(self):
        assert len(sps._DEFAULT_POOL) > 0

    def test_default_pool_entries_are_tuples(self):
        for entry in sps._DEFAULT_POOL:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            code, name = entry
            assert isinstance(code, str) and len(code) >= 4
            assert isinstance(name, str) and len(name) > 0

    def test_default_pool_contains_tsmc(self):
        codes = [e[0] for e in sps._DEFAULT_POOL]
        assert "2330" in codes, "台積電 should always be in the default pool"


class TestGetPoolFallback:
    def test_returns_defaults_when_db_unavailable(self):
        """A1 fix: get_pool() must return _DEFAULT_POOL when psycopg2 raises."""
        with patch("services.stock_pool_service._get_conn", side_effect=Exception("ECONNREFUSED")):
            result = sps.get_pool()

        assert len(result) == len(sps._DEFAULT_POOL)
        for item in result:
            assert "symbol" in item
            assert "name"   in item
            assert "enabled" in item
            assert item["enabled"] is True

    def test_fallback_symbols_match_defaults(self):
        with patch("services.stock_pool_service._get_conn", side_effect=Exception("DB down")):
            result = sps.get_pool()

        fallback_codes  = {r["symbol"] for r in result}
        expected_codes  = {code for code, _ in sps._DEFAULT_POOL}
        assert fallback_codes == expected_codes

    def test_returns_db_data_when_db_available(self):
        """When DB works, return DB rows (not the hardcoded defaults)."""
        mock_rows = [
            {"symbol": "0050", "name": "元大50", "enabled": True},
            {"symbol": "9999", "name": "測試股", "enabled": True},
        ]

        fake_cursor  = _FakeCursor(mock_rows)
        fake_conn    = _FakeConn(fake_cursor)

        with patch("services.stock_pool_service._get_conn", return_value=fake_conn):
            result = sps.get_pool()

        codes = [r["symbol"] for r in result]
        assert "0050" in codes
        assert "9999" in codes
        # Should NOT include default pool codes that aren't in DB result
        assert len(result) == 2


class TestGetTickers:
    def test_appends_tw_suffix(self):
        with patch("services.stock_pool_service.get_pool", return_value=[
            {"symbol": "2330", "name": "台積電", "enabled": True},
            {"symbol": "2317", "name": "鴻海",   "enabled": True},
        ]):
            tickers = sps.get_tickers()

        assert "2330.TW" in tickers
        assert "2317.TW" in tickers

    def test_empty_pool_returns_empty_list(self):
        with patch("services.stock_pool_service.get_pool", return_value=[]):
            tickers = sps.get_tickers()
        assert tickers == []

    def test_custom_suffix(self):
        with patch("services.stock_pool_service.get_pool", return_value=[
            {"symbol": "2330", "name": "台積電", "enabled": True},
        ]):
            tickers = sps.get_tickers(suffix=".TWO")
        assert tickers == ["2330.TWO"]


# ── fake DB helpers ────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        pass

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, **kwargs):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
