"""Factor Engine 單元測試：驗算技術指標計算結果。"""
import pandas as pd
import pytest
from factor_engine import technical
from factor_engine.output_formatter import bundle, TechnicalFactors, ChipsFactors


def _make_df(closes: list[float]) -> pd.DataFrame:
    """產生含 close/high/low 的測試 DataFrame。"""
    df = pd.DataFrame({
        "close": closes,
        "high":  [c * 1.01 for c in closes],
        "low":   [c * 0.99 for c in closes],
    })
    return df


# ── TechnicalFactors ────────────────────────────────────────────────────────

def test_rsi_within_range():
    df = _make_df([100 + i * 0.5 for i in range(30)])
    factors = technical.compute("2330", df)
    assert factors.rsi_14 is not None
    assert 0 <= factors.rsi_14 <= 100


def test_rsi_none_when_insufficient_data():
    df = _make_df([100] * 10)
    factors = technical.compute("2330", df)
    assert factors.rsi_14 is None


def test_macd_computed():
    df = _make_df([100 + i for i in range(40)])
    factors = technical.compute("2330", df)
    assert factors.macd is not None
    assert factors.macd_signal is not None
    assert factors.macd_hist is not None


def test_ma20_computed():
    closes = [float(i + 100) for i in range(25)]
    df = _make_df(closes)
    factors = technical.compute("2330", df)
    expected_ma20 = sum(closes[-20:]) / 20
    assert factors.ma20 is not None
    assert abs(factors.ma20 - expected_ma20) < 0.01


def test_bias_positive_uptrend():
    """在上漲趨勢中，乖離率應為正值。"""
    closes = [100 + i * 2 for i in range(25)]
    df = _make_df(closes)
    factors = technical.compute("2330", df)
    assert factors.bias_20 is not None
    assert factors.bias_20 > 0


def test_atr_positive():
    df = _make_df([100 + i * 0.3 for i in range(20)])
    factors = technical.compute("2330", df)
    assert factors.atr_14 is not None
    assert factors.atr_14 >= 0


def test_kd_within_range():
    df = _make_df([100 + (i % 5) for i in range(20)])
    factors = technical.compute("2330", df)
    if factors.kd_k is not None:
        assert 0 <= factors.kd_k <= 100
    if factors.kd_d is not None:
        assert 0 <= factors.kd_d <= 100


# ── FactorBundle ─────────────────────────────────────────────────────────────

def test_bundle_to_dict_no_none():
    tf = TechnicalFactors(rsi_14=55.0, ma20=120.0)
    cf = ChipsFactors(foreign_net=500)
    fb = bundle("2330", tf, cf)
    d = fb.to_dict()

    # to_dict 應移除 None 值
    assert "rsi_14" in d["technical"]
    assert "macd" not in d["technical"]  # None → 移除
    assert d["symbol"] == "2330"


def test_bundle_symbol_and_date():
    from datetime import date
    tf = TechnicalFactors()
    cf = ChipsFactors()
    fb = bundle("2884", tf, cf, as_of=date(2026, 6, 13))
    assert fb.symbol == "2884"
    assert fb.date == "2026-06-13"


# ── 與現有 screener_agent._calc_rsi 一致性驗算 ──────────────────────────────

def test_rsi_matches_screener_calc():
    """factor_engine RSI 結果與 screener_agent 原始計算差異 < 0.1。"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agents.screener_agent import _calc_rsi

    closes = [100 + i * 0.3 + (i % 3) * 0.5 for i in range(40)]
    series = pd.Series(closes)
    df = _make_df(closes)

    legacy_rsi = float(_calc_rsi(series, 14).iloc[-1])
    new_rsi = technical.compute("2330", df).rsi_14

    assert new_rsi is not None
    assert abs(new_rsi - legacy_rsi) < 0.1
