# K 線形態識別 Spec

## Purpose

識別台股常見 K 線形態，將結果整合至個股技術指標 API 回應中。

## Requirements

### Requirement: 27 種 K 線形態識別
系統 SHALL 識別 27 種台股常見 K 線形態，結果加入 `GET /api/stock/{symbol}/indicators` 回應的 `patterns` 陣列欄位。

形態清單（單根 9 種、雙根 9 種、三根 9 種）：
- **單根**：錘子線、倒錘子、流星線、上吊線、十字星、長十字、墓碑十字、蜻蜓十字、紡錘線
- **雙根**：多頭吞噬、空頭吞噬、穿頭破腳、烏雲罩頂、母子線（多）、母子線（空）、平頂、平底、切入線
- **三根**：晨星、夜星、三白兵、三黑鴉、紅三兵、黑三兵、上升三法、下降三法、棄嬰

#### Scenario: 識別到形態時加入回應
- **WHEN** 呼叫 `GET /api/stock/2330/indicators`，最近 K 棒符合「錘子線」條件
- **THEN** 回應包含 `"patterns": [{"name": "錘子線", "type": "bullish", "confidence": 0.85}]`

#### Scenario: 無形態時返回空陣列
- **WHEN** 最近 K 棒不符合任何形態
- **THEN** 回應包含 `"patterns": []`

#### Scenario: 形態結果納入 L2 Redis 快取
- **WHEN** 同一股票 60 秒內再次請求 indicators
- **THEN** 直接從快取返回，不重新計算形態
