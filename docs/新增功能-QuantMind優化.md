# Taiwan AI Stock Radar — Feature Update v2

> **給 Claude Code 的指令**：請依序讀取本文件，完整實作以下所有功能模組，並在每個 Task 完成後回報狀態。執行前請先確認現有專案結構，避免覆蓋既有邏輯。

---

## 執行前置確認

```bash
# 確認專案根目錄結構
ls -la
# 確認現有 docker-compose.yml 服務清單
cat docker-compose.yml
# 確認 FastAPI 主入口
find . -name "main.py" | head -5
# 確認 Next.js pages 或 app 目錄
ls frontend/src/app 2>/dev/null || ls frontend/pages 2>/dev/null
```

---

## Task 1 — 輕量 Pandas 向量化回測引擎

**目標**：為 Agent 產生的訊號提供歷史驗證能力。

**新增檔案**：`backend/services/backtest/engine.py`

```python
"""
Vectorized backtest engine for Taiwan stock signals.
輸入訊號清單，計算持有 N 日的績效指標。
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from datetime import date


@dataclass
class BacktestResult:
    total_trades: int
    win_rate: float           # 勝率 0~1
    avg_return: float         # 平均報酬率
    sharpe_ratio: float       # Sharpe Ratio（年化）
    max_drawdown: float       # 最大回撤（負值）
    total_return: float       # 累積報酬率
    profit_factor: float      # 獲利因子


class SignalBacktester:
    """
    接受訊號清單 + 價格 DataFrame，回傳績效指標。
    
    signals: List of dict with keys:
        - stock_id: str (e.g. "2330")
        - entry_date: date
        - direction: "long" | "short"
    
    price_df: DataFrame with MultiIndex (date, stock_id), column "close"
    holding_days: 持有天數，預設 [5, 10, 20]
    """

    def __init__(self, price_df: pd.DataFrame):
        self.price_df = price_df

    def run(
        self,
        signals: List[dict],
        holding_days: int = 10,
        transaction_cost: float = 0.001425 + 0.003,  # 手續費 + 交易稅
    ) -> BacktestResult:
        returns = []
        for sig in signals:
            sid = sig["stock_id"]
            entry = pd.Timestamp(sig["entry_date"])
            direction = sig.get("direction", "long")
            try:
                prices = self.price_df.xs(sid, level="stock_id")["close"].sort_index()
                if entry not in prices.index:
                    entry = prices.index[prices.index.searchsorted(entry)]
                exit_idx = prices.index.searchsorted(entry) + holding_days
                if exit_idx >= len(prices):
                    continue
                exit_price = prices.iloc[exit_idx]
                entry_price = prices.loc[entry]
                raw_return = (exit_price - entry_price) / entry_price
                if direction == "short":
                    raw_return = -raw_return
                net_return = raw_return - transaction_cost * 2
                returns.append(net_return)
            except (KeyError, IndexError):
                continue

        if not returns:
            return BacktestResult(0, 0, 0, 0, 0, 0, 0)

        r = np.array(returns)
        wins = r[r > 0]
        losses = r[r <= 0]
        cum = np.cumprod(1 + r)
        rolling_max = np.maximum.accumulate(cum)
        drawdowns = (cum - rolling_max) / rolling_max

        profit_factor = (
            float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")
        )
        # 年化：假設持有 holding_days，每年 250 交易日
        ann_factor = 250 / holding_days
        sharpe = (r.mean() / r.std() * np.sqrt(ann_factor)) if r.std() > 0 else 0

        return BacktestResult(
            total_trades=len(returns),
            win_rate=float(len(wins) / len(returns)),
            avg_return=float(r.mean()),
            sharpe_ratio=float(sharpe),
            max_drawdown=float(drawdowns.min()),
            total_return=float(cum[-1] - 1),
            profit_factor=profit_factor,
        )
```

**新增 API endpoint** — 在現有 `backend/main.py` 或 router 中加入：

```python
from backend.services.backtest.engine import SignalBacktester, BacktestResult
from pydantic import BaseModel

class BacktestRequest(BaseModel):
    signals: list
    holding_days: int = 10

@router.post("/backtest/run", response_model=dict)
async def run_backtest(req: BacktestRequest):
    """執行回測，signals 格式見 SignalBacktester docstring"""
    # TODO: 從 FinMind 或本地快取載入 price_df
    # price_df = await load_price_dataframe(req.signals)
    # backtester = SignalBacktester(price_df)
    # result = backtester.run(req.signals, req.holding_days)
    # return dataclasses.asdict(result)
    raise NotImplementedError("請先整合 price_df 資料來源")
```

---

## Task 2 — 獨立 RiskManager 模組

**目標**：將風控邏輯從 Agent prompt 抽離，統一管理。

**新增檔案**：`backend/services/risk/manager.py`

```python
"""
RiskManager — 統一風控裁定模組。
所有 Agent 最終建議在執行前必須通過此模組驗證。
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    adjusted_size: Optional[float] = None  # 調整後建議倉位（0~1）


class RiskManager:
    def __init__(
        self,
        max_single_position: float = 0.10,   # 單一持股最大倉位 10%
        max_total_position: float = 0.80,    # 總持倉上限 80%
        stop_loss_pct: float = -0.08,        # 停損線 -8%
        max_buy_drop: float = -0.03,         # 買入時最大跌幅 -3%（Max Buy Drop）
        blacklist: list = None,
    ):
        self.max_single_position = max_single_position
        self.max_total_position = max_total_position
        self.stop_loss_pct = stop_loss_pct
        self.max_buy_drop = max_buy_drop
        self.blacklist = set(blacklist or [])

    def evaluate(
        self,
        stock_id: str,
        direction: str,          # "buy" | "sell"
        proposed_size: float,    # 建議倉位比例 0~1
        current_pnl_pct: float = 0.0,   # 當前持倉損益 %
        current_total_position: float = 0.0,  # 目前總持倉比例
        intraday_change_pct: float = 0.0,     # 當日漲跌幅
    ) -> RiskDecision:

        # 黑名單檢查
        if stock_id in self.blacklist:
            return RiskDecision(False, f"{stock_id} 在黑名單中，拒絕執行")

        # 停損觸發
        if direction == "sell" and current_pnl_pct <= self.stop_loss_pct:
            return RiskDecision(True, f"停損觸發：損益 {current_pnl_pct:.1%}，強制出場")

        # 買入時單日跌幅保護
        if direction == "buy" and intraday_change_pct <= self.max_buy_drop:
            return RiskDecision(
                False,
                f"買入保護：{stock_id} 當日跌幅 {intraday_change_pct:.1%} 超過閾值"
            )

        # 總倉位上限
        if direction == "buy":
            if current_total_position + proposed_size > self.max_total_position:
                adjusted = max(0.0, self.max_total_position - current_total_position)
                if adjusted < 0.01:
                    return RiskDecision(False, f"總倉位已達上限 {self.max_total_position:.0%}")
                logger.warning(f"倉位壓縮：{proposed_size:.1%} → {adjusted:.1%}")
                return RiskDecision(True, f"倉位壓縮至 {adjusted:.1%}", adjusted_size=adjusted)

        # 單一持股上限
        if proposed_size > self.max_single_position:
            return RiskDecision(
                True,
                f"單一持股壓縮：{proposed_size:.1%} → {self.max_single_position:.1%}",
                adjusted_size=self.max_single_position,
            )

        return RiskDecision(True, "通過風控審查", adjusted_size=proposed_size)

    def add_to_blacklist(self, stock_id: str):
        self.blacklist.add(stock_id)
        logger.info(f"已加入黑名單：{stock_id}")

    def remove_from_blacklist(self, stock_id: str):
        self.blacklist.discard(stock_id)
```

**在 Agent pipeline 中整合**（找到現有 Agent 執行邏輯並加入）：

```python
from backend.services.risk.manager import RiskManager

risk_manager = RiskManager()  # 可從 config 初始化參數

# Agent 產生建議後，執行前插入：
decision = risk_manager.evaluate(
    stock_id=agent_output.stock_id,
    direction=agent_output.direction,
    proposed_size=agent_output.position_size,
    current_pnl_pct=current_holding_pnl,
    current_total_position=portfolio_total_position,
    intraday_change_pct=market_data.change_pct,
)
if not decision.approved:
    logger.warning(f"風控拒絕：{decision.reason}")
    # 不執行，寫入 rejected_signals 表
else:
    final_size = decision.adjusted_size or agent_output.position_size
    # 繼續執行訂單
```

---

## Task 3 — Prompt 策略版本化（strategy_versions 表）

**目標**：讓 Agent prompt 可版本化管理，支援 A/B 測試。

**新增 DB Migration** — `db/migrations/add_strategy_versions.sql`：

```sql
CREATE TABLE IF NOT EXISTS strategy_versions (
    id              SERIAL PRIMARY KEY,
    agent_name      VARCHAR(64) NOT NULL,       -- e.g. "trend_agent", "devils_advocate"
    version         VARCHAR(32) NOT NULL,       -- e.g. "v1.2"
    system_prompt   TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT FALSE,
    win_rate        NUMERIC(5,4),               -- 回測勝率（更新自回測結果）
    sharpe_ratio    NUMERIC(6,4),
    total_trades    INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    activated_at    TIMESTAMPTZ,
    notes           TEXT
);

CREATE UNIQUE INDEX idx_strategy_versions_active
    ON strategy_versions(agent_name) WHERE is_active = TRUE;

-- 切換生產版本的 stored procedure
CREATE OR REPLACE FUNCTION activate_strategy_version(p_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE strategy_versions sv
    SET is_active = FALSE
    FROM strategy_versions sv2
    WHERE sv.agent_name = sv2.agent_name AND sv2.id = p_id;

    UPDATE strategy_versions
    SET is_active = TRUE, activated_at = NOW()
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;
```

**新增 API endpoint**：

```python
@router.get("/strategy-versions/{agent_name}")
async def list_versions(agent_name: str, db=Depends(get_db)):
    """列出指定 Agent 的所有版本"""
    ...

@router.post("/strategy-versions/{version_id}/activate")
async def activate_version(version_id: int, db=Depends(get_db)):
    """切換生產版本"""
    await db.execute("SELECT activate_strategy_version($1)", version_id)
    return {"status": "activated"}
```

---

## Task 4 — WebSocket 即時訊號推送

**目標**：Agent 產生訊號後即時推送到 Dashboard，無需輪詢。

**新增檔案**：`backend/services/stream/ws_manager.py`

```python
"""WebSocket 連線管理 + Redis Pub/Sub 橋接"""
import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
CHANNEL = "radar:signals"


class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self.active -= dead


ws_manager = WSManager()


async def redis_subscriber(redis_url: str):
    """監聽 Redis channel，有新訊號就廣播到所有 WS 連線"""
    r = await aioredis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL)
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                await ws_manager.broadcast(data)
            except Exception as e:
                logger.error(f"WS broadcast error: {e}")
```

**在 FastAPI app 啟動時掛載**（`main.py`）：

```python
from backend.services.stream.ws_manager import ws_manager, redis_subscriber
import asyncio

@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_subscriber(settings.REDIS_URL))

@app.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except Exception:
        ws_manager.disconnect(websocket)
```

**Agent pipeline 產生訊號後發布到 Redis**：

```python
import redis, json

r = redis.from_url(settings.REDIS_URL)
r.publish("radar:signals", json.dumps({
    "type": "new_signal",
    "stock_id": signal.stock_id,
    "direction": signal.direction,
    "confidence": signal.confidence,
    "timestamp": signal.created_at.isoformat(),
}))
```

**前端 Next.js** — 在 Dashboard 組件加入 WS hook：

```typescript
// hooks/useSignalStream.ts
import { useEffect, useState } from "react"

export function useSignalStream() {
  const [signals, setSignals] = useState<Signal[]>([])
  useEffect(() => {
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/ws/signals`)
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === "new_signal") {
        setSignals(prev => [data, ...prev].slice(0, 50))
      }
    }
    return () => ws.close()
  }, [])
  return signals
}
```

---

## Task 5 — 績效分析頁（Advanced Analysis）

**目標**：在 Dashboard 新增策略績效分析頁。

**新增後端 API**：`backend/api/analytics.py`

```python
@router.get("/analytics/performance-summary")
async def performance_summary(days: int = 30, db=Depends(get_db)):
    """
    回傳最近 N 天：
    - 每日勝率趨勢
    - 各 Agent 訊號貢獻度
    - 對比加權指數超額報酬 alpha
    """
    ...

@router.get("/analytics/agent-contribution")  
async def agent_contribution(db=Depends(get_db)):
    """各 Agent 的訊號勝率與平均報酬貢獻"""
    ...
```

**前端新增頁面**：`frontend/src/app/analytics/page.tsx`（或 `pages/analytics.tsx`）
- 日勝率折線圖（recharts LineChart）
- Agent 貢獻度橫條圖
- Alpha vs 加權指數比較圖
- 最大回撤時序圖

---

## Task 6 — Celery 非同步 Agent Pipeline

**目標**：Agent 6 個串行呼叫改為非同步任務，避免 API timeout。

**新增** `backend/tasks/agent_pipeline.py`：

```python
from celery import Celery
import os

celery_app = Celery(
    "radar",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

@celery_app.task(bind=True, max_retries=2)
def run_agent_pipeline(self, stock_ids: list, date: str):
    """
    非同步執行 6 Agent 決策 pipeline。
    完成後發布到 Redis channel，觸發 Telegram 通知。
    """
    try:
        # 依序呼叫各 Agent（含 Devil's Advocate）
        results = execute_full_pipeline(stock_ids, date)
        # 發布訊號
        publish_signals_to_redis(results)
        # Telegram 通知
        send_telegram_notification(f"✅ Agent Pipeline 完成：{len(results)} 個訊號")
        return results
    except Exception as exc:
        send_telegram_notification(f"❌ Pipeline 失敗：{exc}")
        raise self.retry(exc=exc, countdown=60)
```

**`docker-compose.yml` 新增 Celery worker 服務**：

```yaml
  celery_worker:
    build: .
    command: celery -A backend.tasks.agent_pipeline worker --loglevel=info --concurrency=2
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - db
    volumes:
      - .:/app
```

---

## Task 7 — 元大持倉即時監控頁（左側欄新增）

**目標**：在左側 Nav 新增「持倉監控」頁，串接元大證券 API 即時顯示持倉狀況。

### 7a. 後端 — 元大持倉 API 整合

**新增**：`backend/services/yuanta/portfolio.py`

```python
"""
元大證券 API 持倉查詢服務。
API 文件參考：https://easywin.yuantafutures.com.tw/api/
"""
import httpx
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Position:
    stock_id: str
    stock_name: str
    quantity: int            # 持股張數
    avg_cost: float          # 平均成本
    current_price: float     # 現價
    market_value: float      # 市值
    unrealized_pnl: float    # 未實現損益
    unrealized_pnl_pct: float  # 損益率
    day_change: float        # 今日漲跌
    day_change_pct: float    # 今日漲跌幅


class YuantaPortfolioService:
    def __init__(self):
        self.base_url = os.getenv("YUANTA_API_URL", "")
        self.account = os.getenv("YUANTA_ACCOUNT", "")
        self.token = os.getenv("YUANTA_TOKEN", "")  # 由 yuanta SDK 取得

    async def get_positions(self) -> List[Position]:
        """取得當前所有持倉"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/v1/position",
                headers={"Authorization": f"Bearer {self.token}"},
                params={"account": self.account},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_position(p) for p in data.get("positions", [])]

    async def get_account_summary(self) -> dict:
        """取得帳戶總覽（總資產、可用資金、今日損益）"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/v1/account/summary",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

    def _parse_position(self, raw: dict) -> Position:
        qty = raw.get("qty", 0)
        avg = raw.get("avg_price", 0)
        cur = raw.get("close", 0)
        mv = qty * cur * 1000  # 1張 = 1000股
        pnl = (cur - avg) * qty * 1000
        pnl_pct = (cur - avg) / avg if avg else 0
        return Position(
            stock_id=raw.get("stock_no", ""),
            stock_name=raw.get("stock_name", ""),
            quantity=qty,
            avg_cost=avg,
            current_price=cur,
            market_value=mv,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            day_change=raw.get("change", 0),
            day_change_pct=raw.get("change_pct", 0),
        )
```

**新增 API endpoints**：`backend/api/portfolio.py`

```python
from fastapi import APIRouter, Depends
from backend.services.yuanta.portfolio import YuantaPortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
yuanta = YuantaPortfolioService()

@router.get("/positions")
async def get_positions():
    """取得元大持倉清單"""
    positions = await yuanta.get_positions()
    return {"positions": [p.__dict__ for p in positions]}

@router.get("/summary")
async def get_account_summary():
    """取得帳戶總覽"""
    return await yuanta.get_account_summary()

@router.websocket("/ws/positions")
async def ws_positions(websocket: WebSocket):
    """每 30 秒推送最新持倉（盤中）"""
    await websocket.accept()
    try:
        while True:
            positions = await yuanta.get_positions()
            await websocket.send_json({
                "type": "positions_update",
                "data": [p.__dict__ for p in positions],
                "updated_at": datetime.now().isoformat(),
            })
            await asyncio.sleep(30)
    except Exception:
        pass
```

### 7b. 前端 — 持倉監控頁面

**新增頁面**：`frontend/src/app/portfolio/page.tsx`

```tsx
"use client"
import { useEffect, useState } from "react"
import { useSignalStream } from "@/hooks/useSignalStream"

interface Position {
  stock_id: string
  stock_name: string
  quantity: number
  avg_cost: number
  current_price: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  day_change: number
  day_change_pct: number
}

export default function PortfolioPage() {
  const [positions, setPositions] = useState<Position[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [lastUpdated, setLastUpdated] = useState<string>("")
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    // WS 即時更新
    const ws = new WebSocket(
      `${process.env.NEXT_PUBLIC_WS_URL}/portfolio/ws/positions`
    )
    ws.onopen = () => setIsConnected(true)
    ws.onclose = () => setIsConnected(false)
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === "positions_update") {
        setPositions(msg.data)
        setLastUpdated(new Date(msg.updated_at).toLocaleTimeString("zh-TW"))
      }
    }
    // 初始載入 summary
    fetch("/api/portfolio/summary")
      .then((r) => r.json())
      .then(setSummary)
    return () => ws.close()
  }, [])

  const totalMV = positions.reduce((s, p) => s + p.market_value, 0)
  const totalPnL = positions.reduce((s, p) => s + p.unrealized_pnl, 0)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium text-gray-900 dark:text-white">
          元大持倉監控
        </h1>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-green-500" : "bg-gray-400"
            }`}
          />
          {isConnected ? `即時 · 更新 ${lastUpdated}` : "連線中斷"}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "持倉市值", value: `${(totalMV / 10000).toFixed(0)} 萬`, accent: false },
          { label: "未實現損益", value: `${totalPnL >= 0 ? "+" : ""}${(totalPnL / 10000).toFixed(1)} 萬`, accent: totalPnL >= 0 },
          { label: "持倉檔數", value: `${positions.length} 檔`, accent: false },
          {
            label: "整體損益率",
            value: `${totalMV > 0 ? ((totalPnL / (totalMV - totalPnL)) * 100).toFixed(2) : 0}%`,
            accent: totalPnL >= 0,
          },
        ].map((card) => (
          <div
            key={card.label}
            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4"
          >
            <p className="text-xs text-gray-500 mb-1">{card.label}</p>
            <p
              className={`text-xl font-medium ${
                card.accent === true
                  ? "text-red-500"
                  : card.accent === false && card.value.startsWith("-")
                  ? "text-green-500"
                  : "text-gray-900 dark:text-white"
              }`}
            >
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Positions Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700 text-xs text-gray-500">
              <th className="text-left px-4 py-3">股票</th>
              <th className="text-right px-4 py-3">張數</th>
              <th className="text-right px-4 py-3">均成本</th>
              <th className="text-right px-4 py-3">現價</th>
              <th className="text-right px-4 py-3">市值</th>
              <th className="text-right px-4 py-3">未實現損益</th>
              <th className="text-right px-4 py-3">今日漲跌</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-gray-400">
                  載入持倉中…
                </td>
              </tr>
            ) : (
              positions
                .sort((a, b) => b.market_value - a.market_value)
                .map((p) => (
                  <tr
                    key={p.stock_id}
                    className="border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-white">
                        {p.stock_id}
                      </div>
                      <div className="text-xs text-gray-400">{p.stock_name}</div>
                    </td>
                    <td className="px-4 py-3 text-right">{p.quantity}</td>
                    <td className="px-4 py-3 text-right">
                      {p.avg_cost.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {p.current_price.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">
                      {(p.market_value / 10000).toFixed(1)}萬
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-medium ${
                        p.unrealized_pnl >= 0
                          ? "text-red-500"
                          : "text-green-500"
                      }`}
                    >
                      {p.unrealized_pnl >= 0 ? "+" : ""}
                      {(p.unrealized_pnl / 1000).toFixed(1)}千
                      <span className="text-xs ml-1">
                        ({(p.unrealized_pnl_pct * 100).toFixed(2)}%)
                      </span>
                    </td>
                    <td
                      className={`px-4 py-3 text-right ${
                        p.day_change >= 0 ? "text-red-500" : "text-green-500"
                      }`}
                    >
                      {p.day_change >= 0 ? "▲" : "▼"}
                      {Math.abs(p.day_change_pct * 100).toFixed(2)}%
                    </td>
                  </tr>
                ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

### 7c. 左側 Nav 新增入口

找到現有側邊欄組件（通常在 `components/Sidebar.tsx` 或 `components/Layout.tsx`），
在「持倉監控」或相鄰位置新增：

```tsx
// 在現有 navItems 陣列中新增：
{
  label: "持倉監控",
  href: "/portfolio",
  icon: <IconChartBar size={18} />,   // 或使用現有 icon 組件
}
```

---

## 環境變數更新

**在 `.env` / `docker-compose.yml` 補充以下變數**：

```env
# 元大 API
YUANTA_API_URL=https://api.yuanta.com.tw   # 實際 URL 請查閱元大 API 文件
YUANTA_ACCOUNT=your_account_number
YUANTA_TOKEN=your_api_token

# WebSocket
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 完成確認清單

Claude Code 請在完成後逐項確認：

- [ ] Task 1：`backend/services/backtest/engine.py` 建立完成，`/backtest/run` endpoint 可呼叫
- [ ] Task 2：`backend/services/risk/manager.py` 建立完成，Agent pipeline 整合完成
- [ ] Task 3：`db/migrations/add_strategy_versions.sql` 執行完成，API endpoint 可用
- [ ] Task 4：WS `/ws/signals` endpoint 啟動，前端 hook 整合，Redis Pub/Sub 正常
- [ ] Task 5：`/analytics` 頁面可正常渲染
- [ ] Task 6：Celery worker 在 docker-compose 啟動正常，Agent pipeline 改為非同步
- [ ] Task 7：`/portfolio` 頁面可正常渲染，左側 Nav 有「持倉監控」入口，元大 API 測試連線

**如有任何步驟失敗，請報告具體錯誤並暫停，等待人工確認。**
