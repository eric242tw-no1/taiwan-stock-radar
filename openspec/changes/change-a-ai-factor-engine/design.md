## Context

taiwan-stock-radar 目前已具備基本的選股篩選、回測、盤中異常偵測（market_anomaly_agent）與晨報（morning_brief_agent）功能。然而，技術指標與籌碼計算邏輯分散在 `screener.py`、`market.py`、`backtest.py` 等路由中，彼此重複且難以複用。

本次 Change 建立統一的 **Factor Engine**，並在其之上架設 **6-Agent 多智能體協調系統**，整合 UZI 評審團、IC 備忘錄、多空辯論等高階分析功能，以及 Prompt 策略版本化管理。

現有相關基礎設施：
- Celery + Redis 任務佇列（`celery_app.py`、`celery_tasks.py`）
- `ic_memo` DB 表已存在於 `schema.sql`
- `strategies` DB 表已存在
- Claude API 已整合於現有 agents

## Goals / Non-Goals

**Goals:**
- 建立 `backend/factor_engine/` 統一模組，封裝技術指標與籌碼因子，輸出 `FactorBundle` dataclass
- 實作 6-Agent Orchestrator，透過 Claude API tool_use 協調各專責 Agent
- 實作 UZI 評審團（三派系加權評分）、IC 備忘錄（三情境期望值）、多空辯論（Bull/Bear/Arbiter）
- 新增 `strategy_versions` 表與對應 API，支援 Prompt A/B 測試
- 提供 REST API：`/api/analysis/debate/{symbol}`、`/api/analysis/ic-memo/{symbol}`、`/api/strategies/versions`

**Non-Goals:**
- 不建立即時 WebSocket 推播（使用現有 REST polling 即可）
- 不取代現有 Celery 排程架構（agents 可由 Celery 驅動，但本次不重構排程）
- 不建立前端 UI（僅後端 API，前端整合留待後續 sprint）
- 不修改現有 backtest 引擎邏輯

## Decisions

### 決策 1：Factor Engine 使用 dataclass 輸出 FactorBundle

**選擇**：`FactorBundle` 為 Python dataclass，欄位固定，序列化為 dict 傳入 Agent。

**理由**：相較於 dict 或 Pydantic model，dataclass 在計算管道內部使用更輕量，且可直接轉 JSON 傳給 Claude tool_use。Pydantic 留給 API 層驗證。

**替代方案**：直接傳 pandas DataFrame → 拒絕，DataFrame 太重且無法序列化。

---

### 決策 2：Multi-Agent Engine 採用 Orchestrator + Parallel Agents 模式

**選擇**：`multi_agent_engine.py` 中的 `Orchestrator` 依序（或並行）呼叫各 Agent，蒐集輸出後加權整合。Agent 間不直接溝通，只透過 Orchestrator。

**理由**：
- 降低複雜度，易於除錯
- 各 Agent prompt 獨立，便於版本化管理
- 未來可透過 Celery 並行化

**替代方案**：Agents 互相傳訊（peer-to-peer）→ 拒絕，複雜度過高且難以追蹤決策鏈。

---

### 決策 3：UZI 評審團分數加權設計

**選擇**：三派系固定權重（動能派 35%、價值派 35%、風控派 30%），可透過 `strategy_versions` 調整。

**理由**：固定權重易於解釋與稽核，且可透過版本化系統做 A/B 測試，不需硬編碼。

---

### 決策 4：Debate API 同步執行（非 Celery 任務）

**選擇**：`POST /api/analysis/debate/{symbol}` 同步執行，回應時間預估 10-30 秒，使用 HTTP 長連線。

**理由**：避免引入任務狀態查詢複雜度。若超時問題嚴重，後續可改為 Celery async。

**替代方案**：非同步任務 + polling → 留作後續優化選項。

---

### 決策 5：strategy_versions 表設計

```sql
CREATE TABLE strategy_versions (
    id          SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    version     VARCHAR(50) NOT NULL,
    prompt_template TEXT NOT NULL,
    parameters  JSONB DEFAULT '{}',
    is_active   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

每個 strategy 同時只有一個 active version（透過 activate API 切換）。

## Risks / Trade-offs

- **[風險] Claude API 延遲**：6 Agent 串行呼叫可能累計 30-60 秒 → 緩解：先並行化獨立 Agent（技術、籌碼、總經），再串行風控與辯論
- **[風險] Claude API 費用**：每次分析呼叫多個 Agent → 緩解：加入 cache 層（相同 symbol + 日期的結果快取 1 小時）
- **[風險] factor_engine 替換現有邏輯造成計算差異**：漸進式替換，先並行驗算，確認一致後再移除舊邏輯
- **[取捨] Debate 同步執行**：使用者需等待，但架構簡單；若 UX 問題嚴重則改非同步

## Migration Plan

1. 建立 `factor_engine/` 模組，撰寫單元測試，與現有計算結果比對驗證
2. 建立 `multi_agent_engine.py`，先以 mock Agent 串通整體流程
3. 逐一實作六個 Agent，整合 factor_engine 輸出
4. 實作 UZI / IC Memo / Debate API
5. 新增 `strategy_versions` DB 遷移（`db_migrations.py` 擴充）
6. 將 screener/market/backtest 中的重複計算邏輯改為呼叫 factor_engine
7. 部署前在暫存環境驗算指標一致性

**Rollback**：factor_engine 為新增模組，舊有路由邏輯保留至驗算通過後再移除，可隨時回退。

## Open Questions

- IC 備忘錄的「總經分析師」Agent 資料來源：現有 morning_brief 已有 FRED/Yahoo 資料，是否直接複用？（假設：是）
- UZI 評審團的評審名稱與評分標準是否要儲存在 DB？（假設：初版 hardcode，後續版本化）
- `strategy_versions` 啟用（activate）是否需要 audit log？（假設：初版不需要，記錄 `created_at` 即可）
