## 1. Factor Engine 基礎模組

- [x] 1.1 建立 `backend/factor_engine/__init__.py`，定義模組公開介面
- [x] 1.2 建立 `backend/factor_engine/output_formatter.py`，定義 `TechnicalFactors`、`ChipsFactors`、`FactorBundle` dataclass 與 `.to_dict()` 方法
- [x] 1.3 建立 `backend/factor_engine/technical.py`，實作 `compute(symbol, ohlcv_df)` 計算 RSI(14)、MACD(12/26/9)、KD(9)、MA(5/10/20/60)、ATR(14)、Bias(20)
- [x] 1.4 建立 `backend/factor_engine/chips.py`，實作 `compute(symbol, date)` 取得三大法人、融資融券、大戶集保數據
- [x] 1.5 撰寫 `backend/tests/test_factor_engine.py`，驗算技術指標計算結果與現有 screener 邏輯一致
- [x] 1.6 將 `backend/routers/screener.py` 中的重複指標計算改為呼叫 `factor_engine.technical.compute()`
- [x] 1.7 將 `backend/routers/market.py` 中的重複指標計算改為呼叫 `factor_engine.technical.compute()`

## 2. DB Schema 更新

- [x] 2.1 在 `backend/services/db_migrations.py` 新增 `strategy_versions` 表建立邏輯（含 `strategy_id` FK、`is_active` 欄位）
- [x] 2.2 更新 `backend/schema.sql`，補充 `strategy_versions` 表定義
- [x] 2.3 驗認 `ic_memo` 表欄位符合 IC 備忘錄 spec（`symbol`、`date`、`scenarios_json`、`expected_value`、`created_at`）

## 3. Multi-Agent Engine 核心架構

- [x] 3.1 建立 `backend/agents/multi_agent_engine.py`，定義 `Orchestrator` 類別與 `MultiAgentReport` dataclass
- [x] 3.2 實作 `TechnicalAnalystAgent`：接收 `FactorBundle`，呼叫 Claude API tool_use，輸出技術面評分與摘要
- [x] 3.3 實作 `ChipsAnalystAgent`：解讀籌碼因子，輸出籌碼面評分與摘要
- [x] 3.4 實作 `MacroAnalystAgent`：整合現有 morning_brief 的總經資料，輸出宏觀環境評分
- [x] 3.5 實作 `RiskReviewerAgent`：評估下行風險，輸出風險評分與停損建議
- [x] 3.6 實作 `TradeExecutorAgent`：建議進場時機與部位大小
- [x] 3.7 實作 `DevilsAdvocateAgent`：挑戰主流論點，提出反向質疑
- [x] 3.8 實作 `Orchestrator.analyze(symbol, factor_bundle)`：並行呼叫技術/籌碼/總經 Agent，串行執行風控/執行員/魔鬼代言人，加權整合最終評分
- [x] 3.9 實作 strategy_versions 動態 prompt 載入邏輯（查詢 active 版本，fallback 至預設 prompt）

## 4. UZI 評審團

- [x] 4.1 建立 `backend/agents/uzi_panel.py`，定義三位評審（動能派、價值派、風控派）的 prompt 模板
- [x] 4.2 實作 `UZIPanel.evaluate(symbol, factor_bundle)`：各評審透過 Claude API 生成評分（0-100）與理由
- [x] 4.3 實作加權合成邏輯（0.35/0.35/0.30）與評分等級對應（強力買進/買進/觀望/賣出/強力賣出）

## 5. IC 備忘錄 API

- [x] 5.1 在 `backend/routers/analysis.py` 建立 `GET /api/analysis/ic-memo/{symbol}` 端點
- [x] 5.2 實作 IC 備忘錄生成邏輯：透過 Claude API 產生 bull/base/bear 三情境（目標價、機率、關鍵假設）
- [x] 5.3 實作機率正規化與期望值計算（加權平均目標價）
- [x] 5.4 實作 DB 讀取快取：當日已有記錄則直接回傳，否則重新生成後寫入 `ic_memo` 表

## 6. 多空辯論 API

- [x] 6.1 在 `backend/routers/analysis.py` 建立 `POST /api/analysis/debate/{symbol}` 端點
- [x] 6.2 實作 `BullAgent`：接收 factor_bundle，透過 Claude API 生成 3 個多方論點（title/argument/evidence）
- [x] 6.3 實作 `BearAgent`：接收 factor_bundle 與 Bull 論點，透過 Claude API 生成 3 個反駁論點
- [x] 6.4 實作 `ArbiterAgent`：接收雙方論點，輸出 verdict/confidence/rationale/key_risk 裁決
- [x] 6.5 組合回應 JSON（symbol、timestamp、bull_arguments、bear_arguments、arbiter）

## 7. 策略版本化 API

- [x] 7.1 在 `backend/routers/strategies.py` 建立 `GET /api/strategies/versions` 端點（支援 `strategy_id` 篩選）
- [x] 7.2 建立 `POST /api/strategies/versions` 端點，寫入新版本（is_active 預設 false）
- [x] 7.3 建立 `GET /api/strategies/versions/{id}/activate` 端點，在單一交易中切換 active 版本

## 8. 路由註冊與整合

- [x] 8.1 在 `backend/main.py` 註冊 `routers/analysis.py` 路由（prefix `/api/analysis`）
- [x] 8.2 在 `backend/main.py` 確認 `routers/strategies.py` 路由已註冊（prefix `/api/strategies`）
- [x] 8.3 更新 `backend/requirements.txt`，確認無新增依賴遺漏

## 9. 既有 Agent 整合

- [x] 9.1 更新 `backend/agents/market_anomaly_agent.py`，改用 `factor_engine.technical.compute()` 取得 RSI，並將 `FactorBundle` 寫入異常事件的 `factor_snapshot` 欄位
- [x] 9.2 在 `backend/agents/morning_brief_agent.py` 加入 `deep_analysis` 設定項，當啟用時呼叫 `Orchestrator.analyze()` 並附加摘要至晨報

## 10. 測試與驗證

- [x] 10.1 撰寫 `backend/tests/test_multi_agent_engine.py`，使用 mock Claude API 驗證 Orchestrator 協調流程
- [x] 10.2 撰寫 `backend/tests/test_debate_api.py`，驗證辯論 API 輸入輸出格式
- [x] 10.3 撰寫 `backend/tests/test_strategy_versions.py`，驗證版本切換的 active 唯一性約束
- [ ] 10.4 手動測試 `POST /api/analysis/debate/2330`，確認回應時間 < 60 秒且格式正確
- [ ] 10.5 手動測試 `GET /api/analysis/ic-memo/2330`，確認首次生成寫入 DB、第二次直接讀取快取
