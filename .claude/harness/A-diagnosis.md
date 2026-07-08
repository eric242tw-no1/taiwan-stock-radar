# A. Harness 漏水診斷書

診斷日期：2026-07-03。診斷者：Claude Fable 5（本專案唯一一次）。
本檔是後續所有 harness 規則的「為什麼」。改規則前先讀這裡，確認原始病因是否還存在。

---

## 痛點 1：技能觸發面爆炸與重複註冊（最常引發調用錯誤）

**現況證據**
- 全域 `~/.claude/skills/` 有 39+ 個技能（gstack 套件約 35MB、superpowers 套件、ui-ux-pro-max 等），加上 9 個全域 commands。每個技能的描述都佔用每次 session 的 system prompt。
- 專案內 openspec 工作流被**雙重註冊**：`.claude/skills/openspec-*`（5 個 SKILL.md）與 `.claude/commands/opsx/*.md`（5 個 commands）內容近乎相同，技能清單同時出現 `openspec-apply-change` 和 `opsx:apply`。
- 撞名三連：gstack 的 `review`、內建 `/review`、內建 `/code-review` 同時存在；gstack 的 `ship`/`spec` 也與常見語意重疊。

**傷害機制**
弱模型在近似名稱間選錯的機率遠高於強模型。選錯技能 = 載入數千 token 的錯誤指令 + 執行偏離的工作流，而且弱模型通常不會發現自己走錯，會把錯誤工作流執行到底。

**物理級阻斷方案**（已執行的與建議的）
1. ✅ 已封存專案內重複的 5 個 `openspec-*` skills → `.claude/archive/skills-openspec-duplicates/`（git 可還原）。唯一入口是 `/opsx:*` commands。
2. ✅ CLAUDE.md 建立**技能白名單**：本專案只允許 `dev-env`、`data-pipeline`、`/opsx:*`、內建 `verify`/`code-review`。白名單外的技能不得自動觸發，除非 User 在訊息中明確點名。
3. ⬜ 建議 User 手動處理（全域資產，本 session 不擅動）：把不再用的 gstack/superpowers 從 `~/.claude/skills/` 與 `~/.claude/commands/` 移出。判斷標準：一個月沒用過的套件就移到 `~/.claude/skills-archive/`。

## 痛點 2：雙記憶系統分裂

**現況證據**
- 全域 `settings.json` 掛載 `agentmemory` MCP server（`npx @agentmemory/mcp`，需要 localhost:3111 有服務在跑）。
- 同時 harness 內建檔案式 auto-memory（`~/.claude/projects/...-taiwan-stock-radar/memory/MEMORY.md` + 個別檔）已在正常運作，索引乾淨。

**傷害機制**
兩套記憶 = 弱模型不知道寫哪邊、讀哪邊；事實分裂後兩邊各半真。更糟的是 agentmemory 依賴本機 3111 服務——服務沒跑時 MCP 工具報錯，弱模型的典型反應是重試三次、換參數再試，燒掉大量 token 才放棄。

**物理級阻斷方案**
1. ✅ 規則層封印（寫入 CLAUDE.md）：本專案**禁止呼叫任何 `mcp__agentmemory__*` 工具**。事實記憶唯一正典 = 檔案 memory；操作程序唯一正典 = `.claude/skills/`；工作流制度唯一正典 = `.claude/harness/`。
2. ⬜ 需 User 決定：若其他專案也不用 agentmemory，直接從 `~/.claude/settings.json` 的 `mcpServers` 移除該條目（記得先備份 settings.json.bak）。這是真正的物理阻斷，規則層封印只是次佳解。

## 痛點 3：主對話閉環迭代 —— 讀檔塞爆 context + 自我驗證

**現況證據**
- 無任何派工合約：歷史 session 中主對話直接大量 Read/Grep 掃 repo（backend 有數十個 service/router 檔），context 被原始碼塞爆後，模型對早期指令的遵循度顯著下降（失焦）。
- 無驗證隔離：寫 code 的同一個模型自己宣告「測試應該會過」。backend/tests 有 12 個 pytest 檔，但沒有任何機制強制實跑。
- 孤兒配置假防護：`~/.claude/rules/python/`（5 個規則檔，coding-style/fastapi/patterns/security/testing）**不會被 Claude Code 自動載入**——規則寫了等於沒寫，卻造成「已有防護」的錯覺。

**傷害機制**
這是三個痛點中最貴的：主對話每多讀 1000 行無關代碼，後續每一輪對話都要重複為它付 token；而自我驗證讓錯誤代碼帶著「已驗證」標籤進 commit，錯誤被發現時 context 早已污染，弱模型會在錯誤的代碼上原地重試而非換路徑。

**物理級阻斷方案**
1. ✅ [C-model-dispatch.md](C-model-dispatch.md)：量化的「指揮官不下場」門檻 + 派工三件套 + 重試上限 2 輪。
2. ✅ [D-judgment-checklist.md](D-judgment-checklist.md)：完成定義一律是「可貼上執行的指令 + 預期輸出」，禁止「測試理論上會過」。
3. ✅ [E-dispatch-templates.md](E-dispatch-templates.md)：驗收 subagent 模板強制 fresh-context read-back + 實跑。
4. ⬜ 建議 User：`~/.claude/rules/python/` 要嘛併入會被載入的位置（如專案 skill 或 CLAUDE.md 路由），要嘛刪除，不要留假防護。

## 次要問題清單（低優先，順手處理即可）

| 問題 | 位置 | 建議 |
|---|---|---|
| 一次性 permission 殘留（如 `cp /c/Users/ERIC/Downloads/00_overview.md ...`） | `.claude/settings.local.json` | 下次進去時順手刪 |
| 工作樹長期不乾淨（tsconfig.json 修改、yuanta_test_connection.py 未追蹤） | repo root | 每個任務結束時 commit 或 stash，髒樹會污染所有 diff-based 工具（/code-review、/ship） |
| PostToolUse hook 每次 Write/Edit 都打 hermes 通知 | `~/.claude/settings.json` | async 無阻塞，可留；若通知太吵改成只留 Stop |
| CLAUDE.md「已知陷阱」與 data-pipeline skill 內容重複 | 兩處 | 已在 CLAUDE.md 重寫時收斂（交付項 B 即 CLAUDE.md 本身，無獨立 B 檔）：CLAUDE.md 留一行指針，細節在 skill |

## 誠實條款：這套 Harness 的能力極限

拆解 + 隔離驗證能把弱模型逼近高階品質的領域：**有明確對錯的工作**——API 行為、資料正確性、測試通過、型別錯誤、效能數字。這些都能寫成可執行的驗收指令。

**注定失敗、無法用制度補救的領域**：
- 模糊的商業美感／UI 品味決策（「這個排版好不好看」「這文案順不順」）
- 沒有先例的架構取捨（「該不該引入新框架」這種十年影響的決策）
- 需求本身矛盾時的優先級裁決

**弱模型遇到極限時的標準應對**（違反此標準 = 違規）：
1. **不得自行拍板**。禁句：「我認為這樣比較美觀所以改了」。
2. 產出 **2–3 個具體選項**，每個附：截圖或代碼片段、一句話 trade-off、自己的傾向（可以有傾向，不能有決定）。
3. 用 AskUserQuestion 或在回覆末尾明確列出選項等 User 裁決。
4. 若 User 不在（自主模式）：選**改動最小、最可逆**的選項，並在回報中用「⚠️ 品味決策，未經確認」標記。
5. 查不到的事實標註「未查證」，**禁止編造**（外部 API 行為、費率、限制一律以實測或官方文件為準，寫進 pitfalls.md 時註明來源）。
