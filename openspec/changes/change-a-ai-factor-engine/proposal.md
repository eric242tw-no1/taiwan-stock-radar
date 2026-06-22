## Why

目前 taiwan-stock-radar 的技術指標與籌碼計算邏輯分散在各 service 中，缺乏統一介面，導致重複計算、難以維護、無法支援多 Agent 協同分析。為了實現具備 UZI 評審團、IC 備忘錄與多空辯論的智能決策系統，需要先建立統一的因子引擎與多 Agent 架構基礎。

## What Changes

- 新增 `backend/factor_engine/` 模組，統一封裝技術指標（RSI、MACD、KD、MA、ATR、Bias）與籌碼因子（三大法人、融資融券、大戶集保），輸出標準化 `FactorBundle` dataclass
- 取代現有分散在 screener、backtest、market routers 中的重複計算邏輯
- 新增 `backend/agents/multi_agent_engine.py`，實作六個專責 Agent 協調架構，透過 Claude API tool_use 驅動
- 新增 UZI 評審團（動能派、價值派、風控派多評審加權）、IC 備忘錄（bull/base/bear 三情境＋期望值）、多空辯論（Bull vs Bear + Arbiter 裁決）功能
- 新增 `strategy_versions` DB 表，支援 Prompt 策略版本化與 A/B 測試
- 新增 API 端點：`POST /api/analysis/debate/{symbol}`、`GET /api/analysis/ic-memo/{symbol}`、`GET/POST /api/strategies/versions`、`GET /api/strategies/versions/{id}/activate`

## Capabilities

### New Capabilities

- `factor-engine`：統一因子引擎模組，技術指標＋籌碼因子計算，輸出標準化 FactorBundle
- `multi-agent-engine`：六 Agent 協調架構（技術分析師、籌碼分析師、總經分析師、風控審查員、交易執行員、Devil's Advocate），Claude API tool_use 實作
- `uzi-panel`：UZI 評審團多派系評分系統（動能派、價值派、風控派），最終加權合成評分
- `ic-memo`：Investment Committee Memo，bull/base/bear 三情境分析＋期望值計算
- `bull-bear-debate`：多空辯論機制，Bull Agent vs Bear Agent 各提 3 論點，Arbiter 裁決
- `strategy-versioning`：Prompt 策略版本化管理，支援版本切換與 A/B 測試

### Modified Capabilities

- `market-anomaly`：整合 factor-engine 輸出，取代內部自行計算的技術指標邏輯
- `morning-brief`：整合 multi-agent-engine 輸出，提升分析深度

## Impact

- **後端程式碼**：`backend/routers/screener.py`、`backend/routers/market.py`、`backend/routers/backtest.py` 中的指標計算邏輯將被 factor_engine 取代
- **資料庫**：新增 `strategy_versions` 表；`ic_memo` 表已存在（schema.sql 已有定義）
- **新增路由**：`backend/routers/analysis.py`（debate、ic-memo）、`backend/routers/strategies.py`（versions）
- **Claude API 依賴**：multi_agent_engine 需要 Claude claude-sonnet-4-6 with tool_use
- **相容性**：factor_engine 對外介面為新增，不影響現有 API 端點；舊有計算邏輯漸進式替換，無 BREAKING 變更
