# F. 知識迭代與反思協議

目的：讓弱模型能安全地更新這套 harness，既不僵化也不腐化。

## 1. 權限分層

**綠區——可自行更新，無需徵求同意**（更新後在回覆中告知 User 即可）：
- `harness/pitfalls.md`：踩坑紀錄（append + 依第 3 節整併）
- 使用者層 memory 檔案（依 memory 系統本身的規則）
- `.claude/skills/dev-env/`、`.claude/skills/data-pipeline/` 的**事實補充**（新的實測結論、新端點、新陷阱）——僅限「增加已驗證的事實」，不得改流程結構
- `harness/G-handover.md` 末節「未完成項目」的勾銷與補充

**紅區——必須先取得 User 明確同意才能動**：
- `CLAUDE.md`（路由中心，牽一髮動全身）
- `harness/` 的 README.md、A、C、D、E、F 本體，以及 G 本體（G 末節「未完成項目」除外，屬綠區）
- 風控紅線的任何字句（即使只是「換個說法」）
- `~/.claude/settings.json`、`.claude/settings.local.json`、hooks、MCP 配置
- 刪除任何 harness 檔案或 skill

判斷模糊時的規則：**分不清綠紅就當紅區**。

## 2. 踩坑紀錄寫入格式（pitfalls.md）

觸發時機：任何 debug 花超過 3 輪工具呼叫才解決的問題，解決後**必須**寫一條。新條目加在檔案最上方。

格式（五欄全填，一坑一段）：

```markdown
## [2026-07-03] 一句話標題（症狀導向，方便未來 grep）
- 症狀：實際看到的錯誤/現象原文（貼關鍵行）
- 根因：一句話
- 正確做法：下次直接這樣做（可執行的指令或步驟）
- 驗證方式：怎麼確認問題解了（指令）
- 來源：實測 / 官方文件連結 / 推測（推測必須標明）
```

**完美正例**：
```markdown
## [2026-07-03] preview 上 SSE 頁面永遠空白
- 症狀：EventSource 連線 open 但 onmessage 不觸發
- 根因：後端 CORS 白名單只有 3000-3002，preview 跑 3010
- 正確做法：SSE 用 curl -sN http://localhost:8000/api/stream/signals 直連驗證，不在 preview 驗
- 驗證方式：curl 有持續輸出 data: 行
- 來源：實測
```

**典型反例**（禁止）：「今天遇到 SSE 問題，花了很久，最後解決了。要小心 CORS。」（無症狀原文、無指令、下次遇到等於重踩）

## 3. 精簡與抽象化觸發條件

- `pitfalls.md` 超過 **10 條或 120 行** → 當次任務結束後執行整併：
  1. 重複/同根因的條目合併成一條
  2. 已失效的（環境已改、依賴已換）搬到 `harness/archive/pitfalls-YYYY-MM.md`（archive 目錄不存在就自行建立，這不算紅區改動）
  3. 出現 **3 次以上同類坑** → 這是規則缺口：起草一條規則升級提案（要加進哪個檔、加什麼字句），**以提案形式問 User**（紅區）
- 使用者層 memory 的整併沿用 `consolidate-memory` skill
- skill 檔（dev-env/data-pipeline）超過 100 行 → 提案拆分或精簡（紅區，先問）

## 4. 修改前備份規則

- 修改任何**紅區**檔案（已獲同意後）：先複製 `<檔名>.bak` 於同目錄，完成並驗證後**刪除 .bak**（不要留著堆積）
- 綠區的 pitfalls.md / memory 為 append 性質，不需 .bak；整併（會刪內容）時需 .bak，整併驗證後刪除
- repo 內檔案本來就有 git 版控，.bak 只是同 session 內的快速回退手段；session 結束時不應留任何 .bak 未清

## 5. Retro 習慣（輕量，不許膨脹成儀式）

每完成一個非 trivial 任務（動了 ≥ 3 檔或 debug 過），在最終回報前自問一題：「這次有什麼事，下次的我如果早知道就能省 10 分鐘？」——有答案就寫 pitfalls.md 或 memory，沒有就跳過。禁止為了寫而寫。
