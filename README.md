# Taiwan AI Stock Radar

多代理人（Multi-Agent）架構的台股交易分析系統，結合基本面、技術面、籌碼面與新聞情緒分析，透過多空辯論機制產生交易決策，並可串接券商 API 進行實單下單。

## 專案目標

- 打造一套專屬於**台股市場**的量化交易輔助系統，而非直接移植美股工具
- 以多代理人（Multi-Agent）架構模擬「多方 vs 空方」辯論，讓交易決策更貼近真實研究員討論的過程
- 整合台股在地資料源（FinMind、twstock），降低對海外資料源的依賴
- 支援券商實單下單（元大證券 API），讓分析結果能真正落地執行
- 保持系統模組化，方便未來擴充新的代理人（如新聞情緒分析代理人）

## 核心特色

- **六大決策代理人**：分別從不同面向（如基本面、技術面、籌碼面等）產出觀點，並透過多空辯論機制整合出最終建議
- **即將加入：新聞情緒分析代理人（第七代理人）**：以 FinMind 的 TaiwanStockNews 資料集作為主要新聞來源，使用 Claude Haiku 進行情緒評分
- **實單下單**：透過元大證券 API 串接，將系統建議轉換為實際委託
- **在地化資料源**：FinMind、twstock 作為台股資料主要來源

## 技術架構

| 層級 | 技術 |
|------|------|
| 前端 | Next.js 15 |
| 後端 | FastAPI |
| 資料庫 | PostgreSQL |
| 快取 / 訊息 | Redis |
| 券商串接 | 元大證券 API |
| 資料源 | FinMind、twstock |

## 目錄結構（規劃中）

```
taiwan-ai-stock-radar/
├── frontend/          # Next.js 15 前端
├── backend/           # FastAPI 後端
│   ├── agents/        # 六大決策代理人 + 情緒分析代理人
│   ├── data/          # FinMind / twstock 資料存取層
│   ├── broker/        # 元大證券 API 串接
│   └── main.py
├── docs/              # 專案文件、架構說明
├── ROADMAP.md
├── LICENSE
└── README.md
```

## 開發狀態

專案目前處於早期開發階段，核心架構與代理人邏輯持續迭代中。詳細規劃請參考 [ROADMAP.md](./ROADMAP.md)。

## 授權

本專案採用 [MIT License](./LICENSE)。
