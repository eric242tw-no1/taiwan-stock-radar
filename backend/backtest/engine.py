"""
回測引擎
資料來源：FinMind TaiwanStockPrice（真實歷史資料）
框架：Backtrader
"""
import os
import httpx
import pandas as pd
import backtrader as bt
from datetime import datetime

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
_FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


# ── 資料取得 ─────────────────────────────────────────────

async def fetch_backtest_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """從 FinMind 取歷史 OHLCV，回傳乾淨 DataFrame。"""
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": symbol,
        "start_date": start,
        "end_date": end,
        "token": FINMIND_TOKEN,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(_FINMIND_URL, params=params)
    r.raise_for_status()
    records = r.json().get("data", [])
    if not records:
        raise ValueError(f"FinMind 無資料：{symbol} {start}~{end}")

    df = pd.DataFrame(records)
    df = df.rename(columns={
        "date": "datetime",
        "open": "open",
        "max": "high",
        "min": "low",
        "close": "close",
        "Trading_Volume": "volume",
    })
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def df_to_bt_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    df = df.set_index("datetime")
    return bt.feeds.PandasData(
        dataname=df,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,
    )


# ── 策略定義 ─────────────────────────────────────────────

class WaveStrategy(bt.Strategy):
    """
    波段技術分析策略：
    進場：MACD 黃金交叉 + RSI < 70 + 站上 MA20
    出場：停損 / 停利 / 跌破 MA20 / 持有超時
    """
    params = (
        ("stop_loss_pct",   0.07),
        ("take_profit_pct", 0.15),
        ("max_hold_days",   20),
    )

    def __init__(self):
        self.macd     = bt.indicators.MACD(self.data)
        self.rsi      = bt.indicators.RSI(self.data, period=14)
        self.sma20    = bt.indicators.SMA(self.data, period=20)
        self.entry_price = 0.0
        self.entry_bar   = 0

    def next(self):
        if not self.position:
            if (self.macd.macd[0] > self.macd.signal[0]
                    and self.macd.macd[-1] <= self.macd.signal[-1]
                    and self.rsi[0] < 70
                    and self.data.close[0] > self.sma20[0]):
                self.buy()
                self.entry_price = self.data.close[0]
                self.entry_bar   = len(self)
        else:
            hold = len(self) - self.entry_bar
            stop   = self.entry_price * (1 - self.params.stop_loss_pct)
            target = self.entry_price * (1 + self.params.take_profit_pct)
            if (self.data.close[0] < stop
                    or self.data.close[0] > target
                    or self.data.close[0] < self.sma20[0]
                    or hold >= self.params.max_hold_days):
                self.sell()


class MomentumStrategy(bt.Strategy):
    """
    趨勢跟隨策略：
    進場：創 60 日新高 + 連 3 日收紅
    出場：跌破 10 日均線
    """
    params = (
        ("stop_loss_pct", 0.10),
        ("max_hold_days", 42),
    )

    def __init__(self):
        self.sma10 = bt.indicators.SMA(self.data, period=10)
        self.high60 = bt.indicators.Highest(self.data.close, period=60)
        self.entry_price = 0.0
        self.entry_bar   = 0

    def next(self):
        if not self.position:
            three_up = all(
                self.data.close[-i] > self.data.close[-i - 1] for i in range(3)
            )
            if self.data.close[0] >= self.high60[-1] and three_up:
                self.buy()
                self.entry_price = self.data.close[0]
                self.entry_bar   = len(self)
        else:
            hold = len(self) - self.entry_bar
            stop = self.entry_price * (1 - self.params.stop_loss_pct)
            if (self.data.close[0] < self.sma10[0]
                    or self.data.close[0] < stop
                    or hold >= self.params.max_hold_days):
                self.sell()


STRATEGIES = {
    "wave":     WaveStrategy,
    "momentum": MomentumStrategy,
}


# ── 執行回測 ─────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, strategy: str, params: dict, initial_cash: float = 1_000_000) -> dict:
    """
    同步執行 Backtrader 回測，回傳績效摘要。
    df：已取得的 OHLCV DataFrame
    """
    strat_cls = STRATEGIES.get(strategy)
    if strat_cls is None:
        raise ValueError(f"未知策略：{strategy}，可用：{list(STRATEGIES)}")

    cerebro = bt.Cerebro()
    cerebro.addstrategy(strat_cls, **params)
    cerebro.adddata(df_to_bt_feed(df))

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(0.001425)   # 手續費 0.1425%
    cerebro.broker.set_slippage_perc(0.001)  # 滑點 0.1%

    cerebro.addanalyzer(bt.analyzers.SharpeRatio,  _name="sharpe",   riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown,      _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns,       _name="returns")
    cerebro.addanalyzer(bt.analyzers.TimeReturn,    _name="tret",     timeframe=bt.TimeFrame.Days)

    results = cerebro.run()
    s = results[0]

    trade_stats = s.analyzers.trades.get_analysis()
    total_trades = trade_stats.get("total", {}).get("total", 0)
    won          = trade_stats.get("won",   {}).get("total", 0)
    win_rate     = round(won / total_trades * 100, 1) if total_trades else 0

    sharpe = s.analyzers.sharpe.get_analysis().get("sharperatio")
    dd     = s.analyzers.drawdown.get_analysis()
    ret    = s.analyzers.returns.get_analysis()

    # 每日報酬序列（供前端畫曲線）
    daily_ret = s.analyzers.tret.get_analysis()
    equity_curve = _build_equity_curve(daily_ret, initial_cash)

    final_value  = cerebro.broker.getvalue()
    total_return = round((final_value - initial_cash) / initial_cash * 100, 2)

    return {
        "strategy":      strategy,
        "initial_cash":  initial_cash,
        "final_value":   round(final_value, 0),
        "total_return":  total_return,
        "sharpe_ratio":  round(sharpe, 3) if sharpe else None,
        "max_drawdown":  round(dd.get("max", {}).get("drawdown", 0), 2),
        "total_trades":  total_trades,
        "win_rate":      win_rate,
        "equity_curve":  equity_curve,
    }


def _build_equity_curve(daily_ret: dict, initial_cash: float) -> list[dict]:
    curve = []
    value = initial_cash
    for dt, ret in sorted(daily_ret.items()):
        value *= (1 + ret)
        curve.append({"date": str(dt.date()), "value": round(value, 0)})
    return curve
