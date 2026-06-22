## ADDED Requirements

### Requirement: 統一因子引擎模組

系統 SHALL 提供 `backend/factor_engine/` 模組，封裝所有技術指標與籌碼因子計算邏輯，對外輸出標準化的 `FactorBundle` dataclass。

#### Scenario: 計算技術指標並輸出 FactorBundle

- **WHEN** 呼叫 `technical.compute(symbol, ohlcv_df)` 傳入 OHLCV DataFrame
- **THEN** 系統回傳包含 RSI(14)、MACD(12/26/9)、KD(9)、MA(5/10/20/60)、ATR(14)、Bias(20) 的 `TechnicalFactors` 物件

#### Scenario: 計算籌碼因子

- **WHEN** 呼叫 `chips.compute(symbol, date)` 傳入股票代號與日期
- **THEN** 系統回傳包含三大法人買賣超（外資、投信、自營商）、融資融券餘額變化、大戶集保比例的 `ChipsFactors` 物件

#### Scenario: 輸出統一 FactorBundle

- **WHEN** 呼叫 `output_formatter.bundle(technical_factors, chips_factors)` 
- **THEN** 系統回傳 `FactorBundle` dataclass，包含 `symbol`、`date`、`technical`、`chips` 欄位，可呼叫 `.to_dict()` 序列化為 JSON 相容格式

#### Scenario: 缺少籌碼資料時降級處理

- **WHEN** 計算當日籌碼資料尚未更新（盤中）
- **THEN** `chips` 欄位回傳前一交易日數據，並設定 `chips_date` 為實際資料日期

### Requirement: 取代分散的計算邏輯

系統 SHALL 在 factor_engine 驗算通過後，將 `screener.py`、`market.py`、`backtest.py` 中的重複指標計算改為呼叫 factor_engine。

#### Scenario: 篩選器使用 factor_engine 計算

- **WHEN** 選股篩選器需要 RSI 或 MACD 篩選條件
- **THEN** 系統透過 `factor_engine.technical.compute()` 取得數值，不在路由層自行計算
