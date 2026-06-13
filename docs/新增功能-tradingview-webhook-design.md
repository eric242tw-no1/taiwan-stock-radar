# TradingView Webhook 接收設計重點

> 適用於 Taiwan AI Stock Radar — FastAPI Webhook Endpoint 設計參考
> 來源整理：《把TradingView策略接到實盤：從折騰到省心》

---

## 核心設計原則：跟持倉狀態，不跟動作

### ❌ 舊思路（動作導向）
```
TV 發送：「買入 1000 股 2330」
→ 系統執行買入
→ 問題：中途斷線、信號遺漏 → 持倉錯亂，無法自動修復
```

### ✅ 新思路（狀態導向）
```
TV 發送：「2330 目前應持有 1000 股」
→ 系統查詢實際持倉 → 計算 diff → 執行補差
→ 優點：任何時刻收到信號都能自動同步，斷線不怕
```

---

## Webhook Payload 設計建議

```json
{
  "symbol": "2330",
  "target_position": 1000,
  "strategy_id": "momentum_v2",
  "timeframe": "1D",
  "price_close": "{{close}}",
  "timestamp": "{{timenow}}"
}
```

| 欄位 | 說明 | TradingView 變數 |
|------|------|-----------------|
| `symbol` | 股票代號 | `{{ticker}}` |
| `target_position` | 目標持股張數（0 = 空倉） | `{{strategy.position_size}}` |
| `strategy_id` | 策略識別碼（固定字串） | — |
| `price_close` | 觸發當下收盤價（供記錄用） | `{{close}}` |
| `timestamp` | 信號觸發時間 | `{{timenow}}` |

> `target_position` 正數 = 多單，負數 = 空單（台股通常為 0 或正值），0 = 全部出清

---

## FastAPI Endpoint 處理邏輯

```python
@router.post("/webhook/tradingview")
async def tradingview_webhook(payload: TVPayload, db: Session = Depends(get_db)):

    # 1. 驗證 secret token（TV 不簽名，需自行實作）
    verify_secret(payload)

    # 2. 查詢目前實際持倉
    current_position = await get_current_position(payload.symbol)

    # 3. 計算 diff
    delta = payload.target_position - current_position

    if delta == 0:
        return {"status": "no_action", "reason": "position already matched"}

    # 4. 送進 Devil's Advocate Agent 審核
    agent_decision = await devil_advocate_agent.review({
        "symbol": payload.symbol,
        "action": "buy" if delta > 0 else "sell",
        "quantity": abs(delta),
        "target_position": payload.target_position,
        "strategy_id": payload.strategy_id,
    })

    if not agent_decision.approved:
        return {"status": "rejected", "reason": agent_decision.reason}

    # 5. 送出委託
    order = await yuanta_api.place_order(
        symbol=payload.symbol,
        side="buy" if delta > 0 else "sell",
        quantity=abs(delta),
    )

    # 6. 寫入 PostgreSQL 記錄
    await log_signal(db, payload, delta, order)

    return {"status": "executed", "order_id": order.id}
```

---

## 冪等性設計（Idempotency）

狀態導向的核心優勢，確保重複收到同一信號不會重複下單：

```python
# 收到信號前先確認持倉是否已匹配
if current_position == target_position:
    return {"status": "no_action"}

# 也可用 Redis 做 dedup（防 TV 重複發送）
redis_key = f"tv_signal:{payload.strategy_id}:{payload.symbol}:{payload.timestamp}"
if await redis.exists(redis_key):
    return {"status": "duplicate_ignored"}
await redis.setex(redis_key, 60, "1")  # 60 秒 TTL
```

---

## TradingView 端設定注意事項

1. **需要 Pro 以上方案**，免費版無 Webhook 功能
2. **必須開啟兩步驗證（2FA）**，TV 強制要求
3. **Webhook URL** 填入你的 FastAPI 公開端點：
   ```
   https://your-domain.com/webhook/tradingview
   ```
4. **Message 格式**（在 Alert 的 Message 欄位填入 JSON）：
   ```
   {"symbol":"{{ticker}}","target_position":{{strategy.position_size}},"strategy_id":"momentum_v2","price_close":{{close}},"timestamp":"{{timenow}}"}
   ```
5. **信號延遲約 2–3 秒**，台股收盤後觸發為主，一般夠用
6. **先小量測試**：確認信號能收到 → 持倉能查詢 → 委託能送出

---

## 與六大 Agent 架構的整合點

```
TradingView Alert
      │
      ▼
POST /webhook/tradingview   ← FastAPI 接收
      │
      ├─ 驗證 + dedup（Redis）
      ├─ 查詢持倉 diff
      │
      ▼
Signal Agent              ← 解析信號意圖
      │
      ▼
Devil's Advocate Agent    ← 審核風險（核心把關）
      │
      ├─ 通過 → Execution Agent → 元大 API 下單
      └─ 拒絕 → 記錄 + Telegram 通知
```

---

## 相較於 FMZ 跨平台跟單的差異

| 項目 | FMZ 跨平台跟單 | 自架 FastAPI（本專案）|
|------|--------------|----------------------|
| 目標市場 | 幣圈（幣安/OKX）| 台股（元大 API）|
| AI Agent 整合 | ❌ | ✅ Claude API |
| 風控自訂 | 有限（內建參數）| 完全自訂 |
| 費用 | FMZ 平台費 | 僅 VPS 費 |
| 狀態同步邏輯 | ✅ 內建 | ✅ 需自行實作（本文件）|
