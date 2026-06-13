# TradingView Alert Message 範本（Change D）

> 複製以下 JSON 到 TradingView Alert → Message 欄位。
> 將 `YOUR_SECRET` 替換為 `backend/.env` 中的 `TV_WEBHOOK_SECRET` 值。

---

## 基本格式

```json
{
  "strategy_id": "swing_v1",
  "symbol": "{{ticker}}",
  "secret": "YOUR_SECRET",
  "target_position": 1000,
  "timestamp": {{timenow}}
}
```

---

## 常見情境

### 買入 1 張（1000 股）
```json
{
  "strategy_id": "swing_v1",
  "symbol": "{{ticker}}",
  "secret": "YOUR_SECRET",
  "target_position": 1000,
  "timestamp": {{timenow}}
}
```

### 加碼到 2 張（2000 股）
```json
{
  "strategy_id": "swing_v1",
  "symbol": "{{ticker}}",
  "secret": "YOUR_SECRET",
  "target_position": 2000,
  "timestamp": {{timenow}}
}
```

### 全部出場（target = 0）
```json
{
  "strategy_id": "swing_v1",
  "symbol": "{{ticker}}",
  "secret": "YOUR_SECRET",
  "target_position": 0,
  "timestamp": {{timenow}}
}
```

### 減碼到 1 張
```json
{
  "strategy_id": "swing_v1",
  "symbol": "{{ticker}}",
  "secret": "YOUR_SECRET",
  "target_position": 1000,
  "timestamp": {{timenow}}
}
```

---

## Pine Script 整合範例

### MACD 黃金交叉進場 / 死亡交叉出場

```pine
//@version=5
strategy("MACD Webhook", overlay=true)

[macdLine, signalLine, _] = ta.macd(close, 12, 26, 9)
crossUp   = ta.crossover(macdLine, signalLine)
crossDown = ta.crossunder(macdLine, signalLine)

if crossUp
    strategy.entry("Long", strategy.long)
    alert('{"strategy_id":"macd_v1","symbol":"{{ticker}}","secret":"YOUR_SECRET","target_position":1000,"timestamp":' + str.tostring(timenow) + '}',
          alert.freq_once_per_bar)

if crossDown
    strategy.close("Long")
    alert('{"strategy_id":"macd_v1","symbol":"{{ticker}}","secret":"YOUR_SECRET","target_position":0,"timestamp":' + str.tostring(timenow) + '}',
          alert.freq_once_per_bar)
```

### RSI 超賣反彈

```pine
//@version=5
strategy("RSI Webhook", overlay=true)

rsi = ta.rsi(close, 14)
entry = ta.crossover(rsi, 30)
exit  = ta.crossunder(rsi, 70)

if entry
    alert('{"strategy_id":"rsi_v1","symbol":"{{ticker}}","secret":"YOUR_SECRET","target_position":1000,"timestamp":' + str.tostring(timenow) + '}',
          alert.freq_once_per_bar)

if exit
    alert('{"strategy_id":"rsi_v1","symbol":"{{ticker}}","secret":"YOUR_SECRET","target_position":0,"timestamp":' + str.tostring(timenow) + '}',
          alert.freq_once_per_bar)
```

---

## Webhook URL 設定

| 環境 | URL |
|------|-----|
| 本機開發 | `http://localhost:8000/api/webhook/tradingview` |
| ngrok 穿透 | `https://<your-ngrok-id>.ngrok-free.dev/api/webhook/tradingview` |
| 正式部署 | `https://<your-domain>/api/webhook/tradingview` |

> TradingView 需要 HTTPS，本機開發請使用 ngrok。

---

## 錯誤排查

| 錯誤碼 | 原因 | 解法 |
|--------|------|------|
| `403` | secret 不符 | 確認 `.env` 的 `TV_WEBHOOK_SECRET` 與 Alert message 一致 |
| `422` | 欄位缺少或型別錯誤 | 確認 `target_position` 為整數、`timestamp` 使用 `{{timenow}}` |
| `200 deduped` | 60 秒內重複信號 | 正常行為，Redis dedup 保護 |
| `200 rejected` | AI 信心不足或虧損超限 | 查看 Telegram 通知了解原因 |
| `200 no_change` | 目標倉位與現有倉位相同 | 正常行為，無需下單 |
