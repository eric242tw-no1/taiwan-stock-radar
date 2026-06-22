## Why

Change A（AI 決策核心）已完整實作六個後端 Agent 與 Factor Engine，但前端目前只有基本 AI 評分顯示，使用者無法看到 UZI 評審團分數、IC 備忘錄情境、或多空辯論過程。此 Change 將這些 AI 功能帶到前端，讓投資決策完整可視化。

## What Changes

- `/stock` 頁面新增三個 AI 分析 Tab：
  - **UZI 評審**：呼叫 `POST /api/analysis/uzi/{symbol}`，顯示動能派/價值派/風控派三位評審評分與理由
  - **IC 備忘錄**：呼叫 `GET /api/analysis/ic-memo/{symbol}`，顯示 Bull/Base/Bear 三情境卡與期望值
  - **多空辯論**：呼叫 `POST /api/analysis/debate/{symbol}`，顯示 Bull→Bear→Arbiter 辯論流程與結論
- 新增 `/strategy` 頁面：策略版本管理，可查看、新增、切換 prompt 版本

## Capabilities

### New Capabilities
- `uzi-panel`: UZI 評審團三位評審評分顯示（動能/價值/風控派，含加權分數與理由）
- `ic-memo-panel`: IC 備忘錄情境卡（Bull/Base/Bear 三情境，含期望值與進出場建議）
- `debate-panel`: 多空辯論面板（BullAgent → BearAgent → ArbiterAgent 流程展示）
- `strategy-version-page`: 策略版本管理頁面（列表、新增、切換 active 版本）

### Modified Capabilities
<!-- 無既有 spec 的規格層需求變更 -->

## Impact

- **前端**：`frontend/app/stock/page.tsx`（新增 Tab UI）、`frontend/app/strategy/page.tsx`（新頁面）、`frontend/components/layout/Sidebar.tsx`（新增策略連結）
- **後端**：不需修改，所有 API 端點已存在
- **相依 API**：`POST /api/analysis/uzi/{symbol}`、`GET /api/analysis/ic-memo/{symbol}`、`POST /api/analysis/debate/{symbol}`、`GET /api/strategies/versions`、`POST /api/strategies/versions`
