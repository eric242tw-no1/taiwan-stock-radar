-- Taiwan AI Stock Radar — SQLite Schema (all tables, IF NOT EXISTS = idempotent)

CREATE TABLE IF NOT EXISTS stocks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol   TEXT UNIQUE NOT NULL,
    name     TEXT,
    industry TEXT
);

CREATE TABLE IF NOT EXISTS daily_price (
    symbol TEXT,
    date   TEXT,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS chip_data (
    symbol         TEXT,
    date           TEXT,
    foreign_buy    INTEGER,
    investment_buy INTEGER,
    dealer_buy     INTEGER,
    margin         INTEGER,
    short_interest INTEGER,
    borrow_shares  INTEGER,
    return_shares  INTEGER,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS futures_data (
    date                 TEXT PRIMARY KEY,
    foreign_net_position INTEGER,
    pcr                  REAL,
    open_interest        INTEGER,
    settlement_date      TEXT,
    days_to_settlement   INTEGER
);

CREATE TABLE IF NOT EXISTS stock_indicators_daily (
    ticker      TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    close       REAL,
    volume      INTEGER,
    rsi14       REAL,
    macd        REAL,
    macd_signal REAL,
    macd_hist   REAL,
    k           REAL,
    d           REAL,
    atr14       REAL,
    ma20        REAL,
    ma20_bias   REAL,
    bias_pct    REAL,
    updated_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, trade_date)
);

CREATE TABLE IF NOT EXISTS macro_correlation (
    symbol    TEXT,
    date      TEXT,
    corr_sox  REAL,
    corr_scfi REAL,
    corr_dxy  REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS large_holders_weekly (
    symbol            TEXT,
    week_end_date     TEXT,
    holders_over_400  INTEGER,
    percent_over_400  REAL,
    holders_over_1000 INTEGER,
    percent_over_1000 REAL,
    PRIMARY KEY (symbol, week_end_date)
);

CREATE TABLE IF NOT EXISTS branch_chip_daily (
    symbol      TEXT,
    date        TEXT,
    branch_name TEXT,
    buy_volume  INTEGER,
    sell_volume INTEGER,
    net_volume  INTEGER,
    PRIMARY KEY (symbol, date, branch_name)
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT,
    event_type   TEXT,
    event_date   TEXT,
    description  TEXT,
    alert_days   INTEGER,
    alert_level  TEXT,
    hist_avg_chg REAL
);

CREATE TABLE IF NOT EXISTS factor_scan_daily (
    symbol       TEXT,
    date         TEXT,
    liquidity_ok INTEGER,
    trend_ok     INTEGER,
    momentum_ok  INTEGER,
    chip_ok      INTEGER,
    factor_score REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT,
    name       TEXT,
    added_date TEXT,
    note       TEXT,
    is_active  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT,
    name       TEXT,
    ai_score   INTEGER,
    suggestion TEXT,
    ai_summary TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviewer_rules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reviewer_name TEXT,
    style         TEXT,
    rules         TEXT,
    weight        REAL
);

CREATE TABLE IF NOT EXISTS reviewer_results (
    symbol        TEXT,
    date          TEXT,
    reviewer_name TEXT,
    score         INTEGER,
    verdict       TEXT,
    triggered     TEXT,
    summary       TEXT,
    PRIMARY KEY (symbol, date, reviewer_name)
);

CREATE TABLE IF NOT EXISTS ic_memo (
    symbol           TEXT,
    date             TEXT,
    bull_price       REAL,
    bull_prob        REAL,
    bull_assumption  TEXT,
    base_price       REAL,
    base_prob        REAL,
    base_assumption  TEXT,
    bear_price       REAL,
    bear_prob        REAL,
    bear_assumption  TEXT,
    expected_value   REAL,
    risk_reward      REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS tv_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id     TEXT,
    symbol          TEXT NOT NULL,
    target_position INTEGER NOT NULL,
    actual_position INTEGER NOT NULL DEFAULT 0,
    diff            INTEGER NOT NULL DEFAULT 0,
    dedup_key       TEXT UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending',
    ai_confidence   REAL,
    reentry_action  TEXT,
    executed_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tv_signal_id    INTEGER REFERENCES tv_signals(id),
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL,
    quantity        INTEGER NOT NULL,
    price           REAL,
    status          TEXT NOT NULL DEFAULT 'pending',
    broker_order_id TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL UNIQUE,
    total_value  REAL NOT NULL,
    cash         REAL NOT NULL,
    daily_pnl    REAL NOT NULL DEFAULT 0,
    margin_usage REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT,
    mode       TEXT,
    is_active  INTEGER DEFAULT 1,
    parameters TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategy_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id     INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    version         TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    parameters      TEXT NOT NULL DEFAULT '{}',
    is_active       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trade_journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('buy','sell')),
    quantity    INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price  REAL,
    entry_at    TEXT NOT NULL DEFAULT (datetime('now')),
    exit_at     TEXT,
    strategy    TEXT,
    emotion     TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    nodes_json  TEXT NOT NULL DEFAULT '[]',
    edges_json  TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT,
    period_start TEXT,
    period_end   TEXT,
    win_rate     REAL,
    total_return REAL,
    max_drawdown REAL,
    trades       TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pairs_config (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_long  TEXT,
    symbol_short TEXT,
    corr_60d     REAL,
    spread_mean  REAL,
    spread_std   REAL,
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS us_market_cache (
    symbol     TEXT PRIMARY KEY,
    price      REAL,
    change_pct REAL,
    vix_level  TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_ai_report (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    report_json TEXT NOT NULL,
    sent_at     TEXT
);

CREATE TABLE IF NOT EXISTS stock_pool (
    symbol     TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL,
    name       TEXT NOT NULL DEFAULT '',
    qty        INTEGER NOT NULL,
    cost       REAL NOT NULL,
    buy_date   TEXT,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS macro_indicators (
    date           TEXT PRIMARY KEY,
    tw_us_corr_30d REAL,
    tw_us_corr_60d REAL,
    tw_us_corr_90d REAL,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS earnings_calendar (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT,
    name        TEXT,
    event_type  TEXT NOT NULL,  -- dividend / rights / investor_conference / earnings
    event_date  TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message    TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_read    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_audit (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol             TEXT NOT NULL,
    predicted_direction TEXT NOT NULL,  -- up / down / neutral
    target_price       REAL,
    confidence         REAL,
    predicted_at       TEXT NOT NULL DEFAULT (datetime('now')),
    actual_close       REAL,
    is_correct         INTEGER,         -- 1=correct 0=wrong NULL=pending
    audited_at         TEXT
);

CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Default system config
INSERT OR IGNORE INTO system_config (key, value) VALUES
    ('trading_mode',         'manual'),
    ('auto_order_min_score', '70'),
    ('max_position_pct',     '10'),
    ('daily_loss_limit_pct', '5'),
    ('tv_webhook_enabled',   'false');

-- Default strategies
INSERT OR IGNORE INTO strategies (id, name, mode, is_active, parameters) VALUES
    (1, '波段技術分析', 'swing_technical', 1, '{"rsi_oversold": 30, "rsi_overbought": 70}'),
    (2, '事件驅動',    'event_driven',    0, '{"days_before": 5}'),
    (3, '趨勢跟隨',    'trend_follow',    0, '{"breakout_pct": 5}');

-- Default stock pool
INSERT OR IGNORE INTO stock_pool (symbol, name) VALUES
    ('2330', '台積電'),
    ('2317', '鴻海'),
    ('2454', '聯發科'),
    ('2412', '中華電'),
    ('0050', '元大台灣50'),
    ('2308', '台達電'),
    ('2881', '富邦金'),
    ('2382', '廣達');
