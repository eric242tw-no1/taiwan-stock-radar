# Taiwan AI Stock Radar — 05 策略與回測
> Sprint 5-6 使用，參考 whale-quant 第四、七章

## 四種可用策略模式

### 模式一：波段技術分析（Phase 1 主力）
```
篩選：MA 多頭排列 + MACD 黃金交叉 + 量能放大
AI 評分權重：技術 40% + 籌碼 30% + 法人 20% + 乖離 10%
持有週期：5-20 天
停損：跌破 MA20 或 2.5 倍 ATR
```

### 模式二：事件驅動（Phase 1）
```
觸發：法說會前3天、月營收前5天、FOMC前3天
AI 評分權重：事件 40% + 技術 30% + 籌碼 30%
持有週期：1-5 天
注意：事件結果不如預期立即停損
```

### 模式三：趨勢跟隨（Phase 1）
```
篩選：創60日新高 + 產業族群共振 + 連3日收紅
AI 評分權重：動能 40% + 產業 30% + 籌碼 30%
持有週期：2-6 週
停損：跌破 10 日均線或產業轉弱
```

### 模式四：配對對沖（Phase 3 後）
```
概念：多強勢股 + 空弱勢股，Beta 接近 0
台股高相關配對：台積電/聯電、台達電/光寶科、富邦金/國泰金
前提：元大 API 借券功能確認可用
```

---

## 因子模型（全市場掃描）

### 量化篩選條件（自動，每日 14:30 後跑）
```python
# agents/factor_scanner.py
# 參考 whale-quant 第四章
# https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch04/ch04.ipynb

def factor_scan(all_symbols: list, date: str) -> pd.DataFrame:
    results = []
    for symbol in all_symbols:
        df = get_price_history(symbol)
        chip = get_chip_data(symbol)

        # 六個篩選條件
        liquidity_ok = df['volume'].rolling(20).mean().iloc[-1] * df['close'].iloc[-1] > 3e8
        trend_ok = df['close'].iloc[-1] > ta.sma(df['close'], 60).iloc[-1]
        momentum_ok = df['close'].pct_change(20).iloc[-1] > 0
        chip_ok = chip['foreign_buy'].tail(5).sum() > 0
        vol_ok = df['close'].pct_change(14).std() * df['close'].iloc[-1] < df['close'].iloc[-1] * 0.08
        margin_ok = chip['margin'].pct_change(5).iloc[-1] < 0.20

        if all([liquidity_ok, trend_ok, momentum_ok, chip_ok]):
            # 因子評分（Z-Score 標準化後加權）
            momentum = df['close'].pct_change(20).iloc[-1]
            tech_score = calculate_tech_score(df)
            chip_score = chip['foreign_buy'].tail(5).mean()

            results.append({
                "symbol": symbol,
                "factor_score": momentum*0.30 + tech_score*0.30 + chip_score*0.20,
                "liquidity_ok": liquidity_ok,
                "trend_ok": trend_ok,
                "momentum_ok": momentum_ok,
                "chip_ok": chip_ok
            })

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values('factor_score', ascending=False)
    return df_result.head(30)  # 回傳前30名
```

---

## 回測模組（Sprint 6）

### Backtrader 框架
```python
# backtest/engine.py
# 參考 whale-quant 第七章
# https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch07/ch07.ipynb

import backtrader as bt

class TaiwanWaveStrategy(bt.Strategy):
    params = (
        ('stop_loss_pct', 0.07),
        ('take_profit_pct', 0.15),
        ('max_hold_days', 20),
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(self.data)
        self.rsi = bt.indicators.RSI(self.data, period=14)
        self.sma20 = bt.indicators.SMA(self.data, period=20)
        self.atr = bt.indicators.ATR(self.data, period=14)

    def next(self):
        if not self.position:
            # 進場：MACD 黃金交叉 + RSI < 70 + 站上 MA20
            if (self.macd.macd[0] > self.macd.signal[0] and
                self.macd.macd[-1] <= self.macd.signal[-1] and
                self.rsi[0] < 70 and
                self.data.close[0] > self.sma20[0]):
                self.buy()
                self.entry_price = self.data.close[0]
                self.entry_bar = len(self)
        else:
            # 出場：停損 / 停利 / 跌破MA20 / 持有超時
            stop_price = self.entry_price * (1 - self.params.stop_loss_pct)
            profit_price = self.entry_price * (1 + self.params.take_profit_pct)
            hold_days = len(self) - self.entry_bar

            if (self.data.close[0] < stop_price or
                self.data.close[0] > profit_price or
                self.data.close[0] < self.sma20[0] or
                hold_days >= self.params.max_hold_days):
                self.sell()

def run_backtest(symbol: str, start: str, end: str, params: dict) -> dict:
    cerebro = bt.Cerebro()
    cerebro.addstrategy(TaiwanWaveStrategy, **params)

    data = get_backtest_data(symbol, start, end)
    cerebro.adddata(data)

    cerebro.broker.setcash(1000000)           # 初始資金 100萬
    cerebro.broker.setcommission(0.001425)    # 台股手續費
    cerebro.broker.set_slippage_perc(0.001)   # 滑點

    # 績效指標
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    results = cerebro.run()
    strat = results[0]

    return {
        "total_return": strat.analyzers.returns.get_analysis()['rtot'] * 100,
        "sharpe_ratio": strat.analyzers.sharpe.get_analysis()['sharperatio'],
        "max_drawdown": strat.analyzers.drawdown.get_analysis()['max']['drawdown'],
        "total_trades": strat.analyzers.trades.get_analysis()['total']['total'],
        "win_rate": strat.analyzers.trades.get_analysis()['won']['total'] /
                    strat.analyzers.trades.get_analysis()['total']['total'] * 100,
    }
```

---

## 選股工作流每日時序

```
14:30 收盤
  ↓
Data Agent 爬取（行情 + 籌碼 + 期貨）
  ↓
15:30 指標預算
  ↓
因子模型全市場掃描 → 候選清單 20-30 檔
  ↓
16:00 宏觀連動計算
  ↓
對自選股池（8-10檔）各呼叫一次 Claude API
（Redis 有快取則跳過）
  ↓
每日 AI 報告寫入 daily_ai_report
  ↓
Telegram Bot 推播摘要
  ↓
分析記錄寫入 analysis_history

每週六
  ↓
TDCC 大戶集保更新
  ↓
週報生成（自選股池整週表現摘要）
```

---

## 模擬帳戶測試計畫（Phase 2 前必完成）

```
Week 1-2：模擬帳戶，手動觸發，確認 API 正常
Week 3-4：模擬帳戶，半自動模式，確認風控邏輯
Week 5-6：模擬帳戶，全自動模式，觀察 Agent 決策
Week 7-8：小額真實帳戶（每筆 ≤ NT$10,000）
Week 9+：勝率 > 55% 且最大回撤 < 10% 才擴大資金
```

---

## whale-quant 章節對應

| Sprint | 參考章節 | GitHub 連結 |
|------|------|------|
| Sprint 2 | 第三章：數據獲取 | .../notebook/ch03/ch03.ipynb |
| Sprint 3 | 第四章：量化選股 | .../notebook/ch04/ch04.ipynb |
| Sprint 4 | 第五章：量化擇時 | .../notebook/ch05/ch05.ipynb |
| Sprint 6 | 第七章：量化回測 | .../notebook/ch07/ch07.ipynb |
