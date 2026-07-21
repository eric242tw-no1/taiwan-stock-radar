# 建議建立的 Issue 清單

以下為建議在 GitHub 建立的初期 Issue，對應 ROADMAP.md 各階段的重點功能。
每個 Issue 包含標題、標籤建議、內容草稿，你可以直接複製到 GitHub 網頁建立，
或使用文件最下方的 `gh` CLI 指令批次建立。

---

### Issue 1：建立 Next.js 15 + FastAPI 專案骨架
**標籤**：`setup`, `infrastructure`
**內容**：
建立前後端專案初始結構，包含基本路由、環境變數設定、開發環境啟動腳本。
對應 Roadmap Phase 0。

---

### Issue 2：串接 FinMind API 取得台股基本面 / 技術面資料
**標籤**：`data`, `backend`
**內容**：
實作 FinMind 資料存取層，涵蓋股價、財報、籌碼等基本資料的取得與快取。
對應 Roadmap Phase 1。

---

### Issue 3：實作六大決策代理人與多空辯論機制
**標籤**：`agents`, `core-feature`
**內容**：
定義六大代理人的輸入輸出介面，並實作多空辯論（Bull/Bear Debate）整合邏輯，
產出最終交易建議。對應 Roadmap Phase 2。

---

### Issue 4：新增新聞情緒分析代理人（第七代理人）
**標籤**：`agents`, `enhancement`
**內容**：
串接 FinMind TaiwanStockNews 資料集，使用 Claude Haiku 進行新聞情緒評分，
並將結果納入代理人辯論流程。對應 Roadmap Phase 3。

---

### Issue 5：串接元大證券 API 實作下單流程
**標籤**：`broker`, `core-feature`
**內容**：
實作下單、查詢委託、查詢庫存等流程，並加入基本風控機制
（單筆金額上限、每日交易次數限制）。對應 Roadmap Phase 4。

---

### Issue 6：建立交易儀表板前端頁面
**標籤**：`frontend`, `enhancement`
**內容**：
建立顯示各代理人觀點、辯論過程、交易紀錄與績效報表的儀表板頁面。
對應 Roadmap Phase 5。

---

## 使用 GitHub CLI 批次建立 Issue（選用）

若你已安裝並登入 `gh` CLI，可在 repo 目錄下執行以下指令快速建立以上 Issue：

```bash
gh issue create --title "建立 Next.js 15 + FastAPI 專案骨架" \
  --body "建立前後端專案初始結構，包含基本路由、環境變數設定、開發環境啟動腳本。對應 Roadmap Phase 0。" \
  --label "setup,infrastructure"

gh issue create --title "串接 FinMind API 取得台股基本面 / 技術面資料" \
  --body "實作 FinMind 資料存取層，涵蓋股價、財報、籌碼等基本資料的取得與快取。對應 Roadmap Phase 1。" \
  --label "data,backend"

gh issue create --title "實作六大決策代理人與多空辯論機制" \
  --body "定義六大代理人的輸入輸出介面，並實作多空辯論整合邏輯，產出最終交易建議。對應 Roadmap Phase 2。" \
  --label "agents,core-feature"

gh issue create --title "新增新聞情緒分析代理人（第七代理人）" \
  --body "串接 FinMind TaiwanStockNews 資料集，使用 Claude Haiku 進行新聞情緒評分。對應 Roadmap Phase 3。" \
  --label "agents,enhancement"

gh issue create --title "串接元大證券 API 實作下單流程" \
  --body "實作下單、查詢委託、查詢庫存等流程，並加入基本風控機制。對應 Roadmap Phase 4。" \
  --label "broker,core-feature"

gh issue create --title "建立交易儀表板前端頁面" \
  --body "建立顯示各代理人觀點、辯論過程、交易紀錄與績效報表的儀表板頁面。對應 Roadmap Phase 5。" \
  --label "frontend,enhancement"
```

註：若標籤（label）尚未在 repo 中建立，`gh issue create` 會報錯，
可先用 `gh label create` 建立對應標籤，或先移除 `--label` 參數，之後在網頁上手動加標籤。
