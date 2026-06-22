# 07 排程架構與 AI Agents（Change B）

## 架構概覽

```
APScheduler (in-process)
  ├── 08:30 Mon-Fri  → MorningBriefAgent  → Claude API → daily_ai_report (DB)
  ├── 09:05 Mon-Fri  → ChipFetch + AnomalyAgent (首次)
  ├── 09:10-13:20 ×10min Mon-Fri → AnomalyAgent → Telegram
  ├── 13:35 Mon-Fri  → score_symbol.delay() × N + AccountSnapshot
  ├── 14:35 Mon-Fri  → FinMind chip fetch
  ├── 15:05 Mon-Fri  → Indicator calc
  ├── 15:10 Mon-Fri  → Sector fetch
  ├── 15:15 Mon-Fri  → Gov funds + Correlation
  ├── 16:30 Mon-Fri  → Self Audit
  └── Sat 10:00      → TDCC fetch

Celery Worker (Redis broker)
  ├── score_symbol(symbol)   — AI scoring per stock
  ├── run_screener(params)   — full screener scan
  └── run_backtest(params)   — backtest execution

Flower (port 5555)          — worker health & task monitoring
```

## 新增 API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/reports/morning-brief` | 今日晨報（或指定日期） |
| GET | `/api/market/sector-rotation` | 產業輪動排行（Redis cache） |
| POST | `/api/screener/run` | 非同步選股（回傳 task_id） |
| POST | `/api/backtest/run` | 非同步回測（回傳 task_id） |
| GET | `/api/tasks/{task_id}/status` | Celery task 狀態查詢 |

## 新增資料表

```sql
CREATE TABLE daily_ai_report (
    id          SERIAL PRIMARY KEY,
    date        DATE  NOT NULL UNIQUE,
    report_json JSONB NOT NULL,
    sent_at     TIMESTAMP
);
```

## 啟動

```bash
docker-compose up -d --build
# Flower UI: http://localhost:5555
```

## 異常偵測條件

- 跳空 > 3%（開盤 vs 前收）
- 爆量 > 3× 20日均量
- 漲停 / 跌停（±10%）

觸發時推播 Telegram 通知。

## 產業輪動分數

```
composite_score = 0.5 × mom4w + 0.3 × mom8w + 0.2 × mom13w
```

快取於 Redis（key: `sector_rotation`，TTL: 7 天）。每週六 TDCC job 後可手動重算。
