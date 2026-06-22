## 1. DB Migration

- [x] 1.1 新增 daily_ai_report table（date UNIQUE, report_json JSONB, sent_at TIMESTAMP）至 backend/schema.sql
- [x] 1.2 在 backend/services/webhook_tables.py（或新建 db_migrations.py）加入 ensure_daily_ai_report_table()，app 啟動時呼叫

## 2. Celery 基礎設施

- [x] 2.1 在 requirements.txt 加入 celery[redis]>=5.3 與 flower>=2.0
- [x] 2.2 新增 backend/celery_app.py：設定 broker=Redis、result_backend=Redis、task serializer=json
- [x] 2.3 在 docker-compose.yml 加入 celery-worker service（image 同 fastapi，command: celery -A celery_app worker）
- [x] 2.4 在 docker-compose.yml 加入 flower service（port 5555，depends_on celery-worker）
- [x] 2.5 更新啟動批次檔（啟動開發環境.bat）列出 flower port 5555

## 3. Morning Brief Agent

- [x] 3.1 新增 backend/agents/morning_brief_agent.py：async generate_morning_brief() 函數
- [x] 3.2 实作內容聚合：呼叫 market overview、screener top-5、alert count
- [x] 3.3 呼叫 Claude API 產生繁體中文摘要（asyncio.timeout 30s）
- [x] 3.4 寫入 daily_ai_report（UPSERT on conflict date do nothing）
- [x] 3.5 新增 backend/routers/reports.py：GET /api/reports/morning-brief endpoint
- [x] 3.6 在 backend/main.py 的 router includes 加入 reports router

## 4. Sector Rotation Agent

- [x] 4.1 新增 backend/agents/sector_rotation_agent.py：compute_sector_rotation() 函數
- [x] 4.2 定義 11 個 GICS 產業與 TWSE 產業代碼對應表（dict）
- [x] 4.3 實作 4/8/13 週報酬率計算（使用現有 OHLCV 資料）
- [x] 4.4 計算 composite_score = 0.5×mom4w + 0.3×mom8w + 0.2×mom13w，排序後 cache 至 Redis（key: sector_rotation，TTL 7 天）
- [x] 4.5 在 backend/routers/market.py 加入 GET /api/market/sector-rotation endpoint（讀 Redis cache）

## 5. Market Anomaly Agent

- [x] 5.1 新增 backend/agents/market_anomaly_agent.py：async scan_anomalies() 函數
- [x] 5.2 實作 gap >3% 偵測（open vs previous close）
- [x] 5.3 實作 volume >3× 20日均量 偵測
- [x] 5.4 實作漲跌停偵測（price == limit_up or limit_down）
- [x] 5.5 發現異常時呼叫 utils/telegram.send_message() 推播
- [x] 5.6 加入交易時間檢查（09:00–13:30 台灣時間，否則直接 return）

## 6. APScheduler 整合

- [x] 6.1 在 backend/main.py 加入 APScheduler cron：08:30 週一～週五 → morning_brief_agent.generate_morning_brief()
- [x] 6.2 加入 cron：09:05 週一～週五 → chip fetch + scan_anomalies() 首次執行
- [x] 6.3 加入 cron：09:10–13:20 每 10 分鐘 週一～週五 → scan_anomalies()
- [x] 6.4 加入 cron：13:35 週一～週五 → factor scan + AI batch scoring（呼叫 Celery task.delay）+ account snapshot（已有）
- [x] 6.5 確認現有 15:15 correlation job 與 週六 TDCC job 仍正常運作
- [x] 6.6 所有 job 加入 misfire_grace_time=300（5 分鐘容錯）

## 7. Celery Tasks 遷移

- [x] 7.1 在 backend/celery_app.py 新增 @app.task score_symbol(symbol: str) → 呼叫現有 ai_engine 邏輯
- [x] 7.2 在 backend/celery_app.py 新增 @app.task run_screener() → 呼叫現有 screener_agent 邏輯
- [x] 7.3 在 backend/celery_app.py 新增 @app.task run_backtest(params: dict) → 呼叫現有 backtest engine
- [x] 7.4 修改 screener router：POST /api/screener/run 改呼叫 run_screener.delay()，回傳 task_id
- [x] 7.5 修改 backtest router：POST /api/backtest/run 改呼叫 run_backtest.delay()，回傳 task_id
- [x] 7.6 新增 GET /api/tasks/{task_id}/status endpoint（讀 Celery result backend）

## 8. 文件與測試

- [x] 8.1 更新 docs/06_tradingview_yuanta.md 或新增 docs/07_scheduling_agents.md 說明排程架構
- [x] 8.2 新增 backend/tests/test_morning_brief.py（mock Claude API，測試 UPSERT dedup）
- [x] 8.3 新增 backend/tests/test_anomaly_agent.py（測試三種異常條件觸發）
- [x] 8.4 手動測試：docker-compose up，確認 Flower 在 localhost:5555 可存取（需人工執行）
