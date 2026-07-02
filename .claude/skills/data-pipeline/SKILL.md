---
name: data-pipeline
description: 回填或除錯資料管線(技術指標、AI 評分、財報日曆、籌碼、歷史價)。當頁面顯示空資料、外部 API 回 400/401/402、需要手動觸發資料抓取、或評估 FinMind/TWSE 資料源時使用。
---

# 資料管線與外部 API

## 資料 → 觸發方式
| 資料 | 存放 | 手動觸發 | 排程 |
|---|---|---|---|
| 技術指標 RSI/MA | stock_indicators_daily | `POST /api/market/indicators/refresh` | 平日 15:05 |
| AI 評分 | Redis `ai:score:*` | 容器內對 get_pool() 迴圈跑 `get_ai_analysis(sym)` | 平日 13:35 |
| 財報日曆(除權息) | earnings_calendar | 容器內 `fetch_and_store_calendar()`(TWSE 免費源) | 每日 08:00 |
| 籌碼/外資 | chip_data | `fetch_chip_summary()`(FinMind,常 402) | 平日 14:35 |
| 歷史價 | daily_price | FinMind(常 402);候選改 yfinance/TWSE | — |

範圍 = 股票池(`GET /api/stock-pool`),預設僅 8 檔。日曆有 sentinel 機制:重抓前先 `DELETE FROM earnings_calendar` 讓 _is_fresh 失效。

## 外部 API 限制(實測結論)
- **FinMind 免費 register 等級**:除權息/法說 dataset 無權限(HTTP 400 "update your user level",非額度問題);其餘 dataset 額度易 402(隔日重置)
- **TWSE OpenAPI**(免費、無 token):除權息預告 `/v1/exchangeReport/TWT48U_ALL`(民國日期,`1150709`→2026-07-09);全市場行情 `STOCK_DAY_ALL`;端點目錄 `/v1/swagger.json`
- **TWSE MIS 即時**:每 5 秒限 3 次,超過封 IP
- **DeepSeek**:`https://api.deepseek.com`,key 在 root .env(注意 env 兩層載入,見 skill dev-env)
- **Gemini(截圖辨識)**:認證用 `?key=` query 參數(非 Bearer);免費額度逐模型計算,2.5-flash 易 429 時換 2.5-flash-lite;**OPENAI_API_KEY 必須留空**,否則程式優先拿它打 OpenRouter 必 401;失敗自動降級 Groq
- **元大 YuantaSparkAPI**:pythonnet + .NET DLL,UAT/PROD 皆需 IP 白名單;`YUANTA_SIMULATION=true` 預設模擬

## 空資料排查順序
1. 直打後端 API(`curl :8000/api/...`)區分前端問題 vs 後端問題
2. 查表筆數:`docker exec taiwan-stock-radar-fastapi-1 python -c "import sqlite3; c=sqlite3.connect('/app/data/stockradar.db'); print(c.execute('SELECT COUNT(*) FROM <表名>').fetchone())"`
3. 手動觸發上表對應動作
4. `docker logs` 找 400/401/402,對照上面限制表判斷是 key、權限還是額度問題
5. 注意:force-recreate 會建全新空 DB(volume 內),所有表要重新灌
