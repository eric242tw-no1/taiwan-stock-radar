## Context

Change A 已實作完整後端 AI 分析功能：UZI 評審團（三位 Agent 加權評分）、IC 備忘錄（Bull/Base/Bear 情境，DB 快取）、多空辯論（BullAgent → BearAgent → ArbiterAgent）以及策略版本化（strategy_versions 表）。目前 `/stock` 頁面只有一張 AI Score 卡片（顯示單一分數），使用者無法存取深度分析結果。

現有 `/stock` 頁面使用 `useState` 管理資料，無 Tab 結構。AI 相關 API 端點全部就緒，無需後端修改。

## Goals / Non-Goals

**Goals:**
- 在 `/stock` 頁面現有 AI Score 卡片下方新增三個 Tab（UZI / IC 備忘錄 / 多空辯論），按需載入（lazy fetch on tab click）
- 新增 `/strategy` 頁面，列出策略版本、可新增版本、可設定 active 版本
- Sidebar 新增「策略版本」連結

**Non-Goals:**
- 不修改後端 API
- 不重構 `/stock` 頁面現有的技術指標、K 線圖、籌碼等功能
- 不實作 WebSocket 即時推播（辯論結果仍為 HTTP polling）
- 不處理 prompt 版本的 diff 比較 UI

## Decisions

**1. Tab 按需載入（lazy fetch）**
選擇：使用者點擊 Tab 才呼叫 API，而非頁面載入時全部呼叫。
理由：UZI 和辯論 API 需要 Claude 呼叫，延遲 5-30 秒，不應阻塞頁面。
替代方案：預先全部載入 → 頁面體驗差，因 debate API 慢。

**2. 辯論面板顯示「載入中...」骨架**
辯論 API 可能 15-60 秒才回應，需要 loading skeleton + timeout 提示（> 30s 顯示「AI 思考中，請稍候」）。

**3. IC 備忘錄用 DB 快取，前端顯示快取時間**
後端 IC 備忘錄已有 DB 快取（同日同 symbol 不重算）。前端在卡片右上角顯示 `generated_at` 時間戳。

**4. 策略版本頁用表單新增，不做線上 prompt 編輯器**
新增版本 UI：name + prompt_template textarea + save。不做複雜的 diff 編輯器。

## Risks / Trade-offs

- [Risk] 辯論 API 超時（60s+）→ Mitigation：前端設 60s timeout，超時顯示錯誤訊息「分析超時，請重試」
- [Risk] UZI API 依賴 Claude haiku，可能失敗 → Mitigation：顯示 fallback 錯誤卡片，不影響其他 Tab
- [Trade-off] Tab 按需載入代表切換 Tab 都要等待 → 可接受，使用者預期 AI 分析需要時間

## Migration Plan

純前端新增，無資料庫遷移，無 API 變更。部署只需 `npm run build`。
