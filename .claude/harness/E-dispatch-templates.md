# E. 標準化派工 Prompt 模板

用法：複製對應模板，把 `{...}` 填滿後作為 Agent 工具的 prompt。
不許刪掉任何欄位；某欄不適用就寫「無」。派工前用 [C-model-dispatch.md](C-model-dispatch.md) 第 2 節核對三件套。
記住：subagent 是冷啟動，你們對話裡的任何共識它都不知道，全部要寫進 prompt。

---

## 模板 1：搜尋研究（subagent_type: Explore，model: sonnet）

```
【目標】回答這個問題：{一句話問題，例：SSE 訊號流從後端哪個函式產生、前端哪個元件消費？}
【背景】{為什麼要查 + 已知線索，例：專案是 FastAPI(Docker:8000)+Next.js(host:3002)，SSE 相關代碼可能在 backend/routers/ 與 frontend/app/}
【範圍】搜尋 {目錄清單}；搜尋廣度：{medium / very thorough}
【禁區】不要讀 node_modules、docs/archive、openspec/changes/archive
【驗收】回答必須含具體 路徑:行號，我會抽查其中一處，查無此內容視為失敗
【回報格式】
- 【結論】一句話答案
- 【證據】路徑:行號 清單，每項一行說明
- 【未確定】查不到或不確定的部分，明說，禁止推測補全
禁止貼超過 15 行的代碼。
```

## 模板 2：功能實作（subagent_type: general-purpose，model: sonnet；> 3 檔或跨層改動——即同時改 frontend/ 與 backend/——用 opus）

```
【目標】{要實作什麼，一句話}
【背景】{需求來源 + 架構事實。至少包含：本專案前端 API 規則（JSON 用相對路徑走代理、SSE 直連 :8000）、後端在 Docker 容器 taiwan-stock-radar-fastapi-1、改 root .env 要 force-recreate}
【必讀】動手前先讀：{檔案路徑清單，含 CLAUDE.md 與相關 skill（.claude/skills/dev-env 或 data-pipeline）}
【禁區】{不許動的檔案，預設至少：frontend/app/stock/page.tsx（使用者手調）、任何風控/下單邏輯、.env}
【驗收條件】完成的定義是以下指令全部通過（實跑，貼輸出）。條目至少涵蓋 harness/D-judgment-checklist.md 第 2 節對應任務類型的全部最低門檻：
1. {指令} → 預期 {輸出}
2. {指令} → 預期 {輸出}
（範例：docker exec taiwan-stock-radar-fastapi-1 python -m pytest tests/test_xxx.py -q → 0 failed）
【重試上限】同一個錯誤最多嘗試 2 種修法；仍失敗就停下，回報完整失敗軌跡（改了什麼、跑了什麼、完整錯誤），不要繼續試
【回報格式】
- 【結論】完成/失敗/部分完成 + 一句話
- 【改動】路徑:行號 清單
- 【驗證】實跑的指令 + 輸出關鍵行原文
- 【未解決/風險】沒有寫「無」
禁止貼超過 15 行的代碼。
```

## 模板 3：代碼重構（subagent_type: general-purpose，model: sonnet）

```
【目標】重構 {對象}，行為不得改變
【背景】{為什麼重構 + 架構事實（同模板 2）}
【行為基準】重構前先執行並記錄：{測試指令 / curl 指令}，此輸出為基準
【必讀】{檔案清單}
【禁區】不改公開介面/回傳格式/DB schema；不順手修無關代碼；不加新依賴；{其他}
【驗收條件】（至少涵蓋 harness/D-judgment-checklist.md 第 2 節對應任務類型的最低門檻）
1. 重構後重跑基準指令，輸出與基準一致（貼前後對照）
2. {相關 pytest} → 0 failed
3. git diff 只含目標範圍的檔案
【重試上限】2 種修法；失敗回報軌跡
【回報格式】同模板 2 四欄位。額外要求：【驗證】必須含基準前後對照。
```

## 模板 4：代碼審查 / 驗收（Fresh-Context Verifier；subagent_type: general-purpose，model: sonnet；風控相關用 opus）

注意：**不要**告訴 verifier 實作者的結論或「我覺得已經完成」，只給需求與驗收條件，避免確認偏誤。

```
【角色】你是獨立驗收員，對此前的實作過程一無所知，也不應信任任何人的宣稱。
【需求原文】{把原始需求貼進來，不是實作者的轉述}
【受驗改動】git diff {range} 或檔案清單：{...}
【驗收動作】（至少做兩項，全部實跑）
1. Read-back：讀 {檔案清單}，核對實作是否符合上面的需求原文，列出任何偏差
2. 實跑測試：{測試指令} → 貼輸出
3. 實打端點：{curl 指令} → 核對 {具體欄位}
【判定標準】以下任一情況判 FAIL：驗收指令失敗；實作與需求原文有偏差；發現需求外的行為變更（順手改了別的東西）
【回報格式】
- 【判定】PASS / FAIL（二選一，不許「基本上通過」）
- 【證據】每項驗收動作的指令 + 輸出關鍵行
- 【偏差清單】路徑:行號 + 一行說明；無偏差寫「無」
禁止貼超過 15 行的代碼。
```

---

## 附錄：填好的完整範例（模板 2 實例）

情境：User 要求「財報日曆頁面加一個『只看未來 14 天』的篩選」。

```
【目標】財報日曆頁面加「只看未來 14 天」篩選開關
【背景】專案為 Taiwan Stock Radar：Next.js 16 前端在 host:3002，FastAPI 後端在 Docker 容器 taiwan-stock-radar-fastapi-1(:8000)。前端 JSON fetch 一律相對路徑走 next.config 代理（不要寫 http://localhost:8000，會 CORS 炸）。日曆資料來自 earnings_calendar 表，API 為 GET /api/calendar/events（見 backend/routers/calendar.py）。日期欄位為 ISO 格式字串。
【必讀】CLAUDE.md、.claude/skills/dev-env/SKILL.md、frontend/app/calendar/page.tsx、backend/routers/ 內含 earnings 的 router
【禁區】frontend/app/stock/page.tsx；後端排程邏輯；.env；不加新 npm 依賴
【驗收條件】
1. preview_start({name:"frontend"}) 後開 /calendar，snapshot 可見篩選開關文字「未來 14 天」→ 預期存在
2. 開啟篩選後 snapshot 中不出現 14 天後的日期 → 預期通過
3. preview_console_logs level=error → 無新錯誤
【重試上限】同一個錯誤最多 2 種修法，失敗回報完整軌跡
【回報格式】【結論】【改動】【驗證】【未解決/風險】四欄，禁止貼超過 15 行代碼
```

派工後的驗收：另開模板 4 的 verifier，貼入 User 需求原文與上面三條驗收條件，判定 PASS 才可向 User 宣告完成。
