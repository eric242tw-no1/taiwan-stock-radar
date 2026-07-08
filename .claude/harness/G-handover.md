# G. 給未來 Session 的交接信

寫信人：Claude Fable 5，2026-07-03。這是本專案唯一一次 Fable 5 session，之後由 Opus 4.8 / Sonnet / Haiku 長期運作。
新 session 首次接手時讀這封信，然後照 CLAUDE.md 的路由表工作。

## 三件 User 沒問、但我認為最關鍵的事

### 1. 這個系統會下真單，但風控只存在於文件層

風控紅線（2% 停損、評分 < 70 不下單等）目前只寫在 CLAUDE.md 裡——它約束的是「模型會不會亂改代碼」，不約束「代碼本身會不會亂下單」。`YUANTA_SIMULATION=true` 是唯一的實體保險絲。任何 session 若涉及把模擬切成實盤，這是全 harness 最高風險的一步：文件層防護對運行中的程式毫無作用。建議在那之前先做程式層 guard（下單路徑上硬編碼的參數檢查 + 測試），並把「切實盤」本身當成需要 User 逐項確認的 checklist 任務。**弱模型請注意：這件事永遠不屬於你可以自主決定的範圍。**

### 2. 測試是「有但沒有牙齒」的狀態

backend/tests 有 12 個 pytest 檔，但沒有 CI、沒有 pre-commit、沒有任何機制強制跑它。前端零測試。這代表 harness 的完成定義（D 第 2 節）是目前**唯一**逼測試被執行的機制——如果未來 session 開始「跳過驗收因為趕時間」，整個品質防線就沒了。同時工作樹有長期未處理的雜物（frontend/tsconfig.json 修改、backend/brokers/yuanta_test_connection.py 未追蹤），髒樹會讓所有 diff-based 工具（/code-review、/ship）的訊號變髒。第一個接手的 session 應該問 User 這兩個檔案要 commit 還是丟棄。

### 3. 全域層的雜訊我沒有權限清，需要 User 手動做

以下是我診斷出但不宜擅動的全域問題（詳見 A-diagnosis.md）：
- `~/.claude/skills/` 的 gstack（35MB）+ superpowers 套件造成技能觸發面爆炸，與內建命令撞名（review/ship/spec）
- `~/.claude/settings.json` 的 agentmemory MCP 與檔案 memory 雙軌並存（本專案已規則層封印，但物理移除要 User 做）
- `~/.claude/rules/python/` 是孤兒配置，Claude Code 不會載入它，是假防護

弱模型不要試圖「幫忙」清這些——它們是跨專案資產，動了會影響其他專案。提醒 User，讓他自己清。

## 制度腐化預測與預防

弱模型長期運作下，這套 harness 最可能的四種死法：

| 腐化模式 | 機制 | 預防（已內建的閘門） |
|---|---|---|
| **文件膨脹** | 弱模型愛 append、不敢刪，pitfalls 與 skills 越長越沒人讀，CLAUDE.md 被塞回大雜燴 | F 第 3 節的長度熔斷（10 條/120 行）；CLAUDE.md 屬紅區、開頭就寫明「不要往這裡加長內容」 |
| **驗收貨物崇拜** | 照抄模板格式但不實跑指令，【驗證】欄開始出現「測試應會通過」這種描述文 | C 第 5 節：指揮官必須檢查驗證欄有無實際指令輸出，沒有就退回；D 第 2 節定義「寫不出指令的驗收不算驗收」 |
| **例外常態化** | 「這次小改就不派 verifier 了」→ 豁免範圍逐次擴大 | 豁免條件已量化（≤ 2 檔、≤ 30 行、不涉風控/寫入）；任何超出量化條件的跳過，必須在回報中寫明「跳過了 X，原因 Y」留書面痕跡 |
| **規則漂移** | 每個 session 微調一點措辭，三個月後規則和原意相反 | A/C/D/E/F 是紅區，改動需 User 同意；A-diagnosis 保留了每條規則的病因，改規則前先讀 A 確認病因是否消失 |

一個總體建議給 User：**每月一次**讓當班模型跑「harness 健檢」——read-back 全部 harness 檔、對照 A 的病因是否復發、pitfalls 是否該整併、.bak 是否堆積。這 15 分鐘是制度的保養成本。

## 本次 session 未完成項目

- [ ] User 決定：agentmemory MCP 是否從全域 settings.json 物理移除（A 痛點 2）
- [ ] User 決定：gstack/superpowers 全域套件去留（A 痛點 1）
- [ ] User 決定：`~/.claude/rules/python/` 孤兒配置的去向（併入或刪除）
- [ ] User 決定：工作樹雜物 frontend/tsconfig.json（已修改）與 backend/brokers/yuanta_test_connection.py（未追蹤）commit 或丟棄
- [ ] 待辦（任一 session 可做，屬綠區外的正常開發任務）：清 `.claude/settings.local.json` 的一次性 permission 殘留
- [ ] harness 檔案尚未 commit——首個接手 session 應提議 User 用 `chore(harness): Fable 5 工作流制度` 之類訊息入版控
- [ ] repo root 的 `CLAUDE.md.bak` 是本次 session 依 User 指示保留的重寫前備份；User 確認新版 CLAUDE.md 沒問題後即可刪除（F 第 4 節的「不留 .bak」規則自此之後生效）
- [ ] 2026-07-04 session（Fable 5）：完成去 Docker 化（User 核准）——移除 Redis/Celery、新增 services/kv_store.py 與 signal_bus.py、一鍵啟動 bat、main.rs 重建 exe（不再拉 Docker、DB 統一 backend/data）。CLAUDE.md 與 dev-env/data-pipeline skill 的架構事實已同步。**全部變更未 commit**，User 驗收後入版控
