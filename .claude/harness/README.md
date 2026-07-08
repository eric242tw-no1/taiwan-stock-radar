# Harness 索引（本專案工作流制度）

由 Fable 5 於 2026-07-03 建立。讀者是後續長期運作的弱模型（Opus 4.8 / Sonnet / Haiku）。

## 檔案地圖與讀取時機

| 檔案 | 內容 | 何時讀 |
|---|---|---|
| [A-diagnosis.md](A-diagnosis.md) | 漏水診斷書：三大痛點與阻斷方案 | 想理解規則「為什麼」時 |
| [C-model-dispatch.md](C-model-dispatch.md) | 模型調度合約：指揮官不下場、派工三件套、升降級、隔離驗證 | **每次要派 subagent 前** |
| [D-judgment-checklist.md](D-judgment-checklist.md) | 判斷力檢核表：換路徑信號、完成定義、熔斷提問條件 | **卡關時、宣告完成前** |
| [E-dispatch-templates.md](E-dispatch-templates.md) | 派工 Prompt 模板（搜尋/實作/重構/審查） | 派 subagent 時直接複製填空 |
| [F-knowledge-protocol.md](F-knowledge-protocol.md) | 知識迭代協議：哪些檔可自改、踩坑格式、精簡觸發 | 想更新任何 harness 檔前 |
| [G-handover.md](G-handover.md) | Fable 5 交接信：三件關鍵事 + 制度腐化預防 | 新 session 首次接手時 |
| [pitfalls.md](pitfalls.md) | 踩坑紀錄（append-only，格式見 F） | debug 前先查；解題超過 3 輪工具呼叫才必寫（F 第 2 節） |

## 一條鐵律

宣告任何任務「完成」之前，必須通過 [D-judgment-checklist.md](D-judgment-checklist.md) 第 2 節的完成定義（有可執行指令的驗收），且實作者不得自我驗收（見 C 第 4 節）。
