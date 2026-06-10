# Taiwan AI Stock Radar — 01 資料庫設計
> Sprint 1 建立 Schema 時使用

## 完整 Schema（backend/schema.sql）

```sql
-- 1. 股票基本資料
CREATE TABLE IF NOT EXISTS stocks (
    id        SERIAL PRIMARY KEY,
    symbol    VARCHAR(10) UNIQUE NOT NULL,
    name      VARCHAR(50),
    industry  VARCHAR(50)
);

-- 2. 每日行情
CREATE TABLE IF NOT EXISTS daily_price (
    symbol  VARCHAR(10),
    date    DATE,
    open    NUMERIC,
    high    NUMERIC,
    low     NUMERIC,
    close   NUMERIC,
    volume  BIGINT,
    PRIMARY KEY (symbol, date)
);

-- 3. 籌碼資料
CREATE TABLE IF NOT EXISTS chip_data (
    symbol         VARCHAR(10),
    date           DATE,
    foreign_buy    BIGINT,
    investment_buy BIGINT,
    dealer_buy     BIGINT,
    margin         BIGINT,
    short_interest BIGINT,
    borrow_shares  BIGINT,
    return_shares  BIGINT,
    PRIMARY KEY (symbol, date)
);

-- 4. 期貨選擇權
CREATE TABLE IF NOT EXISTS futures_data (
    date                 DATE PRIMARY KEY,
    foreign_net_position BIGINT,
    pcr                  NUMERIC,
    open_interest        BIGINT,
    settlement_date      DATE,
    days_to_settlement   INT
);

-- 5. 預算指標（每日收盤後寫入，前端只 SELECT）
CREATE TABLE IF NOT EXISTS stock_indicators_daily (
    symbol          VARCHAR(10),
    date            DATE,
    ma20_bias       NUMERIC,
    bias_percentile NUMERIC,
    is_overheat     BOOLEAN,
    atr_14          NUMERIC,
    rolling_beta_60 NUMERIC,
    rsi_14          NUMERIC,
    macd_signal     VARCHAR(20),
    kd_k            NUMERIC,
    kd_d            NUMERIC,
    PRIMARY KEY (symbol, date)
);

-- 6. 宏觀連動係數
CREATE TABLE IF NOT EXISTS macro_correlation (
    symbol    VARCHAR(10),
    date      DATE,
    corr_sox  NUMERIC,
    corr_scfi NUMERIC,
    corr_dxy  NUMERIC,
    PRIMARY KEY (symbol, date)
);

-- 7. 大戶集保（週更）
CREATE TABLE IF NOT EXISTS large_holders_weekly (
    symbol             VARCHAR(10),
    week_end_date      DATE,
    holders_over_400   INT,
    percent_over_400   NUMERIC,
    holders_over_1000  INT,
    percent_over_1000  NUMERIC,
    PRIMARY KEY (symbol, week_end_date)
);

-- 8. 券商分點
CREATE TABLE IF NOT EXISTS branch_chip_daily (
    symbol      VARCHAR(10),
    date        DATE,
    branch_name VARCHAR(50),
    buy_volume  BIGINT,
    sell_volume BIGINT,
    net_volume  BIGINT,
    PRIMARY KEY (symbol, date, branch_name)
);

-- 9. 重要行事曆
CREATE TABLE IF NOT EXISTS calendar_events (
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(10),
    event_type   VARCHAR(30),
    event_date   DATE,
    description  TEXT,
    alert_days   INT,
    alert_level  VARCHAR(10),
    hist_avg_chg NUMERIC
);

-- 10. 因子掃描結果
CREATE TABLE IF NOT EXISTS factor_scan_daily (
    symbol       VARCHAR(10),
    date         DATE,
    liquidity_ok BOOLEAN,
    trend_ok     BOOLEAN,
    momentum_ok  BOOLEAN,
    chip_ok      BOOLEAN,
    factor_score NUMERIC,
    PRIMARY KEY (symbol, date)
);

-- 11. 自選股池
CREATE TABLE IF NOT EXISTS watchlist (
    id         SERIAL PRIMARY KEY,
    symbol     VARCHAR(10),
    name       VARCHAR(50),
    added_date DATE,
    note       TEXT,
    is_active  BOOLEAN DEFAULT TRUE
);

-- 12. 每日 AI 報告（Redis 快取 + DB 持久化）
CREATE TABLE IF NOT EXISTS daily_ai_report (
    symbol            VARCHAR(10),
    date              DATE,
    ai_score          INT,
    suggestion        VARCHAR(20),
    entry_ideal       NUMERIC,
    entry_secondary   NUMERIC,
    stop_loss         NUMERIC,
    take_profit       NUMERIC,
    summary           TEXT,
    key_points        JSONB,
    cached_at         TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 13. 分析記錄
CREATE TABLE IF NOT EXISTS analysis_history (
    id         SERIAL PRIMARY KEY,
    symbol     VARCHAR(10),
    name       VARCHAR(50),
    ai_score   INT,
    suggestion VARCHAR(20),
    ai_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 14. 評審規則
CREATE TABLE IF NOT EXISTS reviewer_rules (
    id            SERIAL PRIMARY KEY,
    reviewer_name VARCHAR(30),
    style         VARCHAR(20),
    rules         JSONB,
    weight        NUMERIC
);

-- 15. 評審結果
CREATE TABLE IF NOT EXISTS reviewer_results (
    symbol        VARCHAR(10),
    date          DATE,
    reviewer_name VARCHAR(30),
    score         INT,
    verdict       VARCHAR(10),
    triggered     JSONB,
    summary       TEXT,
    PRIMARY KEY (symbol, date, reviewer_name)
);

-- 16. IC 備忘錄（三情景）
CREATE TABLE IF NOT EXISTS ic_memo (
    symbol           VARCHAR(10),
    date             DATE,
    bull_price       NUMERIC,
    bull_prob        NUMERIC,
    bull_assumption  TEXT,
    base_price       NUMERIC,
    base_prob        NUMERIC,
    base_assumption  TEXT,
    bear_price       NUMERIC,
    bear_prob        NUMERIC,
    bear_assumption  TEXT,
    expected_value   NUMERIC,
    risk_reward      NUMERIC,
    PRIMARY KEY (symbol, date)
);

-- 17. TradingView 信號
CREATE TABLE IF NOT EXISTS tv_signals (
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(10),
    action       VARCHAR(10),
    price        NUMERIC,
    indicator    VARCHAR(50),
    timeframe    VARCHAR(10),
    source       VARCHAR(20),
    triggered_at TIMESTAMP,
    processed    BOOLEAN DEFAULT FALSE,
    order_id     VARCHAR(50)
);

-- 18. 委託記錄
CREATE TABLE IF NOT EXISTS orders (
    id                 SERIAL PRIMARY KEY,
    symbol             VARCHAR(10),
    action             VARCHAR(10),
    order_type         VARCHAR(10),
    quantity           INT,
    price              NUMERIC,
    filled_price       NUMERIC,
    filled_qty         INT,
    status             VARCHAR(20),
    signal_source      VARCHAR(20),
    ai_score           INT,
    risk_checked       BOOLEAN,
    yuanta_order_id    VARCHAR(50),
    stop_loss_price    NUMERIC,
    take_profit_price  NUMERIC,
    created_at         TIMESTAMP DEFAULT NOW(),
    filled_at          TIMESTAMP
);

-- 19. 帳戶快照
CREATE TABLE IF NOT EXISTS account_snapshots (
    date           DATE PRIMARY KEY,
    total_assets   NUMERIC,
    cash           NUMERIC,
    position_value NUMERIC,
    daily_pnl      NUMERIC,
    total_pnl      NUMERIC,
    win_rate       NUMERIC
);

-- 20. 系統設定
CREATE TABLE IF NOT EXISTS system_config (
    key        VARCHAR(50) PRIMARY KEY,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 21. 回測結果
CREATE TABLE IF NOT EXISTS backtest_results (
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(10),
    period_start DATE,
    period_end   DATE,
    win_rate     NUMERIC,
    total_return NUMERIC,
    max_drawdown NUMERIC,
    trades       JSONB,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- 22. 策略設定
CREATE TABLE IF NOT EXISTS strategies (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(50),
    mode       VARCHAR(30),
    is_active  BOOLEAN DEFAULT TRUE,
    parameters JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 23. 配對對沖設定
CREATE TABLE IF NOT EXISTS pairs_config (
    id           SERIAL PRIMARY KEY,
    symbol_long  VARCHAR(10),
    symbol_short VARCHAR(10),
    corr_60d     NUMERIC,
    spread_mean  NUMERIC,
    spread_std   NUMERIC,
    updated_at   TIMESTAMP
);

-- 預設系統設定
INSERT INTO system_config VALUES
  ('trading_mode', 'manual', NOW()),
  ('auto_order_min_score', '70', NOW()),
  ('max_position_pct', '10', NOW()),
  ('daily_loss_limit_pct', '5', NOW()),
  ('tv_webhook_enabled', 'false', NOW())
ON CONFLICT (key) DO NOTHING;
```

## Docker Compose 設定

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    ports:
      - "5432:5432"
    mem_limit: 2g

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    mem_limit: 256m

  fastapi:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    mem_limit: 512m

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - fastapi
    mem_limit: 512m

volumes:
  postgres_data:
```

## .env.example

```
ANTHROPIC_API_KEY=your_key_here
POSTGRES_DB=stockradar
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379
FINMIND_TOKEN=your_token_here
TV_WEBHOOK_SECRET=your_secret_here
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id
```
