# 主力意圖分析 Spec

## Purpose

依籌碼集中度、成交量、均線、外資投信動向，判斷個股目前主力意圖所處的四個階段之一。

## Requirements

### Requirement: 主力意圖四階段分析
系統 SHALL 依籌碼集中度、成交量、均線、外資投信動向，判斷個股目前主力意圖所處的四個階段之一，並加入每股分析結果。

四階段定義：
- **吸籌**：TDCC 集中度連升 ≥ 3 日 AND 量比 < 0.8
- **拉抬**：收盤 > MA20 AND（外資買超 OR 投信買超）AND 量比 > 1.5
- **出貨**：連縮量（量比 < 0.7 連續 2 日）AND TDCC 集中度下降
- **打壓**：連續 2 日跌停 OR 外資連賣 ≥ 5 日

#### Scenario: 判斷為吸籌階段
- **WHEN** 呼叫 `GET /api/stock/2330/indicators`，TDCC 集中度連升 3 日且量比 0.65
- **THEN** 回應包含 `"market_maker_intent": {"phase": "吸籌", "confidence": 0.78, "signals": ["TDCC集中度連升3日", "量比0.65低於均量"]}`

#### Scenario: 無明顯意圖時返回 unknown
- **WHEN** 籌碼與技術指標不符合任何階段條件
- **THEN** 回應包含 `"market_maker_intent": {"phase": "未知", "confidence": 0, "signals": []}`
