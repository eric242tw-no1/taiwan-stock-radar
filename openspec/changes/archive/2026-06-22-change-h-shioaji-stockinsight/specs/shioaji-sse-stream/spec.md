## ADDED Requirements

### Requirement: Shioaji Tick 訂閱 SSE 串流
系統 SHALL 透過 Shioaji subscribe 訂閱個股即時 Tick，並透過 `/api/stream/signals` SSE endpoint 推送到前端，延遲目標 < 100ms。

#### Scenario: 訂閱後前端收到即時 Tick
- **WHEN** 前端建立 SSE 連線至 `/api/stream/signals?symbol=2330`
- **THEN** 每次 Shioaji Tick 更新時，前端收到含 `price`、`volume`、`timestamp` 的 JSON event

#### Scenario: Shioaji 未連線時降級為輪詢
- **WHEN** Shioaji 連線不可用
- **THEN** SSE 串流改為每 5 秒輪詢 TWSE MIS，前端行為不變
