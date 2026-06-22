# Spec: Risk Manager

## Purpose

集中管理倉位風險，提供 AI 審查前的預先過濾，並對外暴露 REST API 供其他模組呼叫。

## Requirements

### RiskDecision Dataclass
```python
@dataclass
class RiskDecision:
    action: str           # "approve" | "reduce" | "reject"
    position_size: int    # 建議張數
    stop_loss: float      # 停損價
    take_profit: float    # 停利價
    confidence: float     # 0.0–1.0
    reason: str           # 說明
```

### RiskManager 方法
- `check_position_size(symbol, size, capital)` → 單股倉位不超過總資金 20%
- `check_max_drawdown(account)` → 帳戶當日虧損超過 5% 停止所有新倉
- `check_correlation_risk(symbol, portfolio)` → 相關性 > 0.8 的股票不同時持有

### API Endpoint
- `GET /api/risk/assessment/{symbol}` → 回傳 `RiskDecision` JSON
- `GET /api/risk/watching` → 現有 endpoint，維持不變

### 解耦要求
- `stop_loss_guard.py` 停損邏輯改為呼叫 `RiskManager.check_position_size()`
- Webhook Devil's Advocate 呼叫 `RiskManager.check_max_drawdown()` 前置檢查
