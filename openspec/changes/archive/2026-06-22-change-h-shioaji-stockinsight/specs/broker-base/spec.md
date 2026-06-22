## ADDED Requirements

### Requirement: BrokerBase 抽象類別
系統 SHALL 定義 `BrokerBase` ABC，強制所有券商實作 `place_order`、`cancel_order`、`get_positions`、`subscribe_tick` 四個方法，確保上層邏輯與券商無關。

#### Scenario: 未實作抽象方法時拋出錯誤
- **WHEN** 建立未完整實作 BrokerBase 的子類別
- **THEN** 實例化時拋出 `TypeError`

#### Scenario: 切換券商不需修改上層邏輯
- **WHEN** 環境變數 `BROKER=sinopac`
- **THEN** 系統注入 `SinopacBroker`；當 `BROKER=yuanta` 時注入 `YuantaBroker`；兩者均可執行 `place_order`

### Requirement: SinopacBroker（Shioaji）實作
系統 SHALL 提供 `SinopacBroker` 實作 BrokerBase，使用永豐金 Shioaji Python SDK 執行下單與訂閱 Tick。

#### Scenario: Shioaji 未登入時 fallback 降級
- **WHEN** `SINOPAC_ACCOUNT` 未設定或登入失敗
- **THEN** 系統自動 fallback 至 `YuantaBroker`，並記錄警告日誌
