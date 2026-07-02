> ⚠️ 2026-06 歸檔:內容多處過時(Next 15→16、PostgreSQL 已移除、AI 已改 DeepSeek),長青部分已併入根 CLAUDE.md。
# AGENTS.md — Claude Code 開發規範

## 專案背景
Taiwan AI Stock Radar — 台股波段量化交易系統
目前進度：Sprint 5（SSE 串流 + 停損保護 + Broker 抽象層）進行中

## 技術堆疊
- 前端：Next.js 15 + TypeScript + TailwindCSS + ShadCN UI
- 後端：FastAPI + SQLAlchemy
- 資料庫：PostgreSQL + Redis + SQLite（三級快取）
- AI：Claude API claude-sonnet-4-6
- 部署：Docker Compose
- 桌面：Tauri（Sprint 5 加入）

## 開發規則
- 所有技術指標在收盤後背景預算，寫入 stock_indicators_daily
- API 端點只做 SELECT，不即時計算
- Claude API 結果快取至 Redis，TTL 到隔日 09:00
- 每個功能完成後 git commit
- 不直接 commit .env 檔案
- 改超過 3 個檔案前先確認
- 不修改已有函數邏輯，只新增；有衝突先問再動

## 快取策略（三級）
- L1 進程內存：熱快取（30分鐘 TTL）
- L2 SQLite：冷快取（歷史，永久存儲）
- L3 Redis：當日快取（TTL 到隔日 09:00）

## 風控規則（絕對不能違反）
- 單筆損失上限：總資產 2%
- 單股持有上限：總資產 10%
- AI 評分 < 70 不自動下單
- 台指期結算前 2 天禁止自動下單
- 當日虧損 > 5% 自動停止交易

## 已知陷阱
- TWSE MIS 每 5 秒限制 3 次，超過封 IP
- FinMind 免費版 600 次/hr
- TradingView 台股代號格式：TWSE:2330，需清洗
- Docker 記憶體：postgres 2g / fastapi 512m / redis 256m
- 元大 API CA 憑證每年需更新
- uvicorn --reload 在 Windows 有時不偵測檔案變更，需手動重啟

## Commit 格式
feat(sprint5): SSE 行情串流
feat(sprint5): 停損雙層保護 StopLossGuard
feat(sprint5): BrokerBase 抽象層
feat(sprint5): 兩段式下單確認 UI
feat(sprint5): 三級快取架構
feat(sprint5): K線形態識別27種
feat(sprint5): Tauri 桌面殼
feat(sprint6): Self Audit 自審計
feat(sprint6): 主力意圖識別台股版
