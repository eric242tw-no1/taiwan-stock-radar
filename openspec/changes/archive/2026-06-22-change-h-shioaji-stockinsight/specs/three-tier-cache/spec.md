## ADDED Requirements

### Requirement: 三級快取服務
系統 SHALL 實作 `CacheService`，依序查詢 L1（記憶體，TTL 5s）→ L2（Redis，TTL 60s）→ L3（SQLite，TTL 300s），命中即返回，未命中才呼叫原始 API 並同步回寫三層。

#### Scenario: L1 命中直接返回（0.006s）
- **WHEN** 同一 key 在 5 秒內第二次被請求
- **THEN** 從記憶體 dict 返回，不查詢 Redis 或 SQLite

#### Scenario: L1 miss L2 命中（< 1ms）
- **WHEN** L1 TTL 已過，但 L2 Redis 仍有效
- **THEN** 從 Redis 返回並回寫 L1

#### Scenario: 全部 miss 時呼叫原始 API
- **WHEN** 三層快取均未命中
- **THEN** 呼叫原始資料來源，將結果同步寫入 L1 + L2 + L3

#### Scenario: 套用於 quote、indicators、chip 三個 endpoint
- **WHEN** 呼叫 `/api/stock/{symbol}/quote`、`/api/market/indicators/{symbol}`、`/api/stock/{symbol}/chip`
- **THEN** 均透過 CacheService 處理，回應時間 < 50ms（L2 命中時）
