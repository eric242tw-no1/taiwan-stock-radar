# Taiwan AI Stock Radar — 06 TradingView + 元大 API
> Phase 2 串接時使用

## TradingView Webhook 串接

### 前提
需升級 TradingView Plus 以上（$24.95/月）
Phase 1 先用 AI 替代，升級後無縫切換

### Pine Script Alert 格式
在 TradingView Alert → Message 填入：
```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": {{close}},
  "indicator": "MACD_CROSS",
  "timeframe": "{{interval}}",
  "timestamp": "{{time}}"
}
```

### 常用觸發條件
```pine
// MACD 黃金交叉
[macdLine, signalLine, _] = ta.macd(close, 12, 26, 9)
if ta.crossover(macdLine, signalLine)
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"MACD_CROSS","price":' + str.tostring(close) + '}')

// RSI 超賣
rsi = ta.rsi(close, 14)
if ta.crossover(rsi, 30)
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"RSI_OVERSOLD","price":' + str.tostring(close) + '}')

// 突破 MA20 帶量
sma20 = ta.sma(close, 20)
if close > sma20 and volume > ta.sma(volume,5) * 1.5
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"MA20_BREAKOUT","price":' + str.tostring(close) + '}')
```

### FastAPI Webhook 端點
```python
@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    body = await request.body()
    # 驗證簽名防偽造
    signature = request.headers.get("X-TV-Signature", "")
    expected = hmac.new(TV_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401)

    signal = json.loads(body)
    symbol = signal['symbol'].replace("TWSE:","").replace("TW:","")

    # 寫入 Redis + 推播前端 WebSocket
    redis_client.lpush("tv_signals", json.dumps(signal))
    await websocket_manager.broadcast({"type": "tv_signal", "data": signal})
    return {"status": "received"}
```

### AI 替代模式（Phase 1）
```python
def simulate_tv_signals(symbol: str, df: pd.DataFrame) -> list:
    signals = []
    macd = ta.macd(df['close'])
    if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1] and \
       macd['MACD_12_26_9'].iloc[-2] <= macd['MACDs_12_26_9'].iloc[-2]:
        signals.append({"symbol": symbol, "action": "BUY",
                        "indicator": "MACD_CROSS", "source": "ai_substitute"})
    rsi = ta.rsi(df['close'], length=14)
    if rsi.iloc[-1] > 30 and rsi.iloc[-2] <= 30:
        signals.append({"symbol": symbol, "action": "BUY",
                        "indicator": "RSI_OVERSOLD", "source": "ai_substitute"})
    return signals
```

---

## 元大 API 自動下單

### 申請流程
```
1. 確認已有元大證券帳戶
2. 官網 → 數位服務 → API 交易 → 申請開發者資格
3. 下載元大 API SDK（Windows 版）
4. 取得憑證與 API 金鑰
5. WSL2 設定憑證路徑
6. 模擬帳戶測試 ≥ 1 個月
7. 確認勝率 > 55% + 最大回撤 < 10% 才進真實帳戶
```

### API 功能清單
| 功能 | 說明 |
|------|------|
| get_account_balance() | 可用資金、總資產 |
| get_positions() | 持股清單、損益 |
| get_quote(symbol) | 現價、五檔掛單 |
| place_order(type='market', side='buy') | 市價買進 |
| place_order(type='limit', price=X) | 限價買進 |
| place_order(type='stop', stop_price=X) | 停損單 |
| cancel_order(order_id) | 取消委託 |
| get_orders() | 今日委託清單 |

### Claude Code Tool Use 架構
```python
tools = [
    {"name": "get_quote", "description": "查詢台股即時報價",
     "input_schema": {"type": "object", "properties": {
         "symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "get_position", "description": "查詢目前持倉",
     "input_schema": {"type": "object", "properties": {
         "symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "check_risk", "description": "執行六層風控審查",
     "input_schema": {"type": "object", "properties": {
         "symbol": {"type": "string"},
         "action": {"type": "string", "enum": ["buy","sell"]},
         "quantity": {"type": "integer"},
         "price": {"type": "number"}}, "required": ["symbol","action","quantity","price"]}},
    {"name": "place_order", "description": "呼叫元大 API 執行下單",
     "input_schema": {"type": "object", "properties": {
         "symbol": {"type": "string"},
         "action": {"type": "string", "enum": ["buy","sell"]},
         "order_type": {"type": "string", "enum": ["market","limit","stop"]},
         "quantity": {"type": "integer"},
         "price": {"type": "number"}}, "required": ["symbol","action","order_type","quantity"]}},
    {"name": "send_notify", "description": "發送 Telegram 通知",
     "input_schema": {"type": "object", "properties": {
         "message": {"type": "string"}}, "required": ["message"]}}
]

def run_trading_agent(signal: dict, ai_context: dict):
    messages = [{"role": "user", "content": f"""
        收到交易信號，請依序執行：
        1. 查詢 {signal['symbol']} 即時報價
        2. 查詢目前持倉
        3. 執行風控審查
        4. 風控通過才下單
        5. 發送 Telegram 通知

        信號：{signal}
        AI 分析：{ai_context}

        風控規則：
        - 單筆損失上限：總資產 2%
        - 停損：買入價 × (1 - 2.5 × ATR/price)
        - 單股持有上限：總資產 10%
        - AI 評分 < 70 不自動下單
    """}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
    return response
```

### 六層風控
```python
class RiskManager:
    def check_all(self, symbol, action, quantity, price, account) -> bool:
        return all([
            # 1. 單筆損失 ≤ 總資產 2%
            quantity * 1000 * get_atr(symbol) * 2.5 <= account['total_assets'] * 0.02,
            # 2. 單股持有 ≤ 總資產 10%
            quantity * 1000 * price <= account['total_assets'] * 0.10,
            # 3. 當日虧損 ≤ 總資產 5%
            account['daily_pnl'] >= -(account['total_assets'] * 0.05),
            # 4. AI 評分 ≥ 70
            get_latest_ai_score(symbol) >= 70,
            # 5. 交易時間內（09:00-13:30）
            time(9,0) <= datetime.now(taiwan_tz).time() <= time(13,30),
            # 6. 台指期結算前 2 天禁止
            get_days_to_settlement() > 2
        ])
```

### 三種操作模式切換
```
模式一：純看盤（Phase 1）
  → 顯示 AI 建議，不連接元大 API

模式二：半自動（Phase 2）
  → AI 信號 → Telegram 推播 → 手機確認 → 下單

模式三：全自動（Phase 3）
  → AI 評分 ≥ 70 + 六層風控全過 → 自動下單
```

在 system_config 表切換：
```sql
UPDATE system_config SET value='semi_auto' WHERE key='trading_mode';
-- manual / semi_auto / full_auto
```

---

## 參考實作：fugle-tradingview-webhooks

> 來源：https://github.com/chunkai1312/fugle-tradingview-webhooks
> 定位：本系統執行層的參考架構，可直接借鑒 Fugle API 整合、Webhook 接收、LINE Notify 三塊。

### 與本系統的定位差異

| 維度 | chunkai1312/fugle-tradingview-webhooks | 本系統 |
|---|---|---|
| 執行層 | TradingView 訊號 → 直接下單 | AI 評分過濾 → 通過才下單 |
| 決策層 | 無（完全依賴 TradingView） | Claude AI 22維評分 + 六層風控 |
| 券商 API | **Fugle（富果）** | 元大（可雙軌並存） |
| 通知管道 | LINE Notify | Telegram（可加 LINE） |
| 技術棧 | NestJS + TypeScript | FastAPI + Python |
| 適合場景 | 純執行自動化 | AI 輔助決策 + 執行 |

### 可借鑒的程式碼段

#### 1. Fugle API 下單整合（替代元大 API）

Fugle API 申請較元大簡單，適合作為 Phase 2 的優先選擇：

```typescript
// 參考 fugle-tradingview-webhooks 的 Fugle 下單呼叫
import { FugleTrade } from '@fugle/trade'

const fugle = new FugleTrade({ configPath: './config.ini' })

async function placeOrder(symbol: string, action: 'Buy' | 'Sell', quantity: number, price?: number) {
  const order = await fugle.placeOrder({
    stockNo: symbol,
    buySell: action === 'Buy' ? 'B' : 'S',
    price: price ?? 0,        // 0 = 市價
    quantity,
    apCode: 'R',              // 整股
    priceFlag: price ? '0' : '4',  // 0=限價 4=市價
    bsFlag: 'R',              // 現股
    trade: 'S',               // 現股
  })
  return order
}
```

#### 2. LINE Notify 通知（補充 Telegram）

```typescript
// 發送 LINE Notify 訊息
async function sendLineNotify(token: string, message: string) {
  await fetch('https://notify-api.line.me/api/notify', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ message }),
  })
}
```

對應 Python 版（本系統使用）：
```python
import httpx

async def send_line_notify(token: str, message: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
        )
```

#### 3. IP 白名單保護 Webhook

```python
# FastAPI 版本的 TradingView IP 白名單
TRADINGVIEW_IPS = {
    "52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7"
}

@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    client_ip = request.client.host
    if client_ip not in TRADINGVIEW_IPS:
        raise HTTPException(status_code=403, detail="IP not allowed")
    # ... 後續處理
```

### Fugle vs 元大 API 比較

| 項目 | Fugle（富果）| 元大 |
|---|---|---|
| 申請難度 | 低（線上申請即可）| 高（需臨櫃 + 審核）|
| SDK 語言 | Node.js / Python | Windows DLL（需 WSL2）|
| 模擬環境 | ✅ 提供 | ✅ 提供 |
| 手續費 | 0.1425%（有折扣方案）| 依帳戶等級 |
| 適合階段 | Phase 2 優先試用 | Phase 3 正式量產 |

### 建議整合路徑

```
Phase 2（半自動）
  → Fugle API 優先（申請快、SDK 友善）
  → LINE Notify + Telegram 雙通知
  → 參考 fugle-tradingview-webhooks 的 NestJS 執行層，Python 側以 httpx 橋接

Phase 3（全自動）
  → 視帳戶資金規模決定是否切換元大 API
  → Fugle 單筆限額 100 萬，超過才需要元大
```
