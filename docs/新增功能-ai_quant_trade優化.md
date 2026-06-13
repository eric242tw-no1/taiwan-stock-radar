# 新增功能規劃 — 借鑒 ai_quant_trade 優化

> **參考來源**：[charliedream1/ai_quant_trade](https://github.com/charliedream1/ai_quant_trade)
> **建立日期**：2026-06-12
> **適用系統**：Taiwan AI Stock Radar

---

## 一、優化總覽

| 優先級 | 模組 | 說明 | 預估工作量 |
|:---:|---|---|:---:|
| 🔴 高 | Factor Engine — 技術面 | pandas-ta 通用技術因子 | 3 天 |
| 🔴 高 | Factor Engine — 籌碼面 | 台股三大法人 / 融資融券 | 5 天 |
| 🟡 中 | 回測框架整合 | Backtrader / VectorBT | 7 天 |
| 🟡 中 | 情緒分析模組 | 新聞 NLP / FinBERT | 7 天 |
| 🟢 低 | Alpha101 因子參考 | 移植適合台股的因子公式 | 依需求 |

---

## 二、Factor Engine（優先執行）

### 2-1 架構設計

```
TWSE / FinMind API
        │
        ▼
  原始 OHLCV 資料
        │
        ▼
┌─────────────────────┐
│    factor_engine    │
│  ┌───────────────┐  │
│  │  技術面層      │  │  ← pandas-ta / stockstats
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │  籌碼面層      │  │  ← FinMind 台股專屬 API
│  └───────────────┘  │
└─────────────────────┘
        │
        ▼
  因子 DataFrame（標準化輸出）
        │
        ▼
  六 Agent Context（Claude API）
```

### 2-2 目錄結構

```
backend/
└── app/
    └── factor_engine/
        ├── __init__.py
        ├── technical.py       # 技術面因子（pandas-ta）
        ├── chips.py           # 籌碼面因子（三大法人、融資）
        ├── alpha101.py        # Alpha101 精選因子（後期）
        └── output_formatter.py  # 統一輸出格式 → Agent 用
```

### 2-3 技術面因子清單

| 類別 | 因子名稱 | 說明 |
|---|---|---|
| 趨勢 | MA5 / MA20 / MA60 | 短中長期均線 |
| 趨勢 | EMA12 / EMA26 | 指數移動平均 |
| 動能 | MACD / Signal / Histogram | 趨勢動能 |
| 強弱 | RSI(14) | 超買超賣判斷 |
| 震盪 | KD（K9 / D9） | 台股最常用指標 |
| 波動 | Bollinger Bands（上中下軌） | 波動區間 |
| 成交量 | OBV | 量價關係 |
| 成交量 | Volume MA5 / MA20 | 量能趨勢 |

### 2-4 籌碼面因子清單（台股專屬）

| 類別 | 因子名稱 | 資料來源 |
|---|---|---|
| 法人動向 | 外資買賣超（日） | FinMind `TaiwanStockInstitutionalInvestorsBuySell` |
| 法人動向 | 投信買賣超（日） | 同上 |
| 法人動向 | 自營商買賣超（日） | 同上 |
| 法人動向 | 三大法人合計買賣超 | 計算欄位 |
| 法人動向 | 外資連續買超天數 | 計算欄位 |
| 融資融券 | 融資餘額 / 融資增減 | FinMind `TaiwanStockMarginPurchaseShortSale` |
| 融資融券 | 融券餘額 / 券資比 | 同上 |
| 籌碼集中 | 主力買賣超（前 15 大） | FinMind `TaiwanStockTradingDailyReport` |
| 持股結構 | 大股東持股比例變化 | TWSE 公開資訊觀測站 |

### 2-5 輸出格式規範

```python
# 統一輸出格式，餵給 Agent 的 context
{
  "stock_id": "2330",
  "date": "2026-06-12",
  "technical": {
    "ma5": 945.2,
    "ma20": 932.1,
    "ma60": 910.5,
    "rsi14": 62.3,
    "macd": 8.5,
    "k9": 71.2,
    "d9": 65.8,
    "bb_upper": 968.0,
    "bb_lower": 896.0,
    "obv_trend": "up"
  },
  "chips": {
    "foreign_net": 12500,        # 外資買超張數
    "foreign_consecutive": 3,    # 外資連續買超天數
    "trust_net": -200,           # 投信買賣超
    "margin_balance": 45230,     # 融資餘額（張）
    "margin_change": -1200,      # 融資增減
    "short_ratio": 0.032         # 券資比
  }
}
```

---

## 三、回測框架整合

### 3-1 建議工具

| 工具 | 優點 | 缺點 | 建議用途 |
|---|---|---|---|
| **VectorBT** | 速度極快、向量化運算 | 學習曲線稍陡 | 快速策略驗證 |
| **Backtrader** | 功能完整、社群豐富 | 速度較慢 | 精細回測 |

### 3-2 回測目標指標

- 年化報酬率
- 最大回撤（Max Drawdown）
- 夏普率（Sharpe Ratio）
- 勝率（Win Rate）— 目標 55–62%
- 盈虧比（Profit/Loss Ratio）— 目標 2:1

### 3-3 整合位置

```
backend/
└── app/
    └── backtest/
        ├── engine.py          # 回測引擎封裝
        ├── metrics.py         # 績效指標計算
        └── report_generator.py  # 輸出報告 → 前端顯示
```

---

## 四、情緒分析模組

### 4-1 資料來源

| 來源 | 內容 | 取得方式 |
|---|---|---|
| 鉅亨網 / 工商時報 | 台股新聞 | 爬蟲 |
| PTT Stock 版 | 散戶情緒 | Pushshift / 爬蟲 |
| Yahoo Finance TW | 個股新聞 | FinMind / RSS |
| 重大訊息公告 | 法說會 / 財報 | TWSE 公開資訊觀測站 |

### 4-2 模型選擇

- **短期**：`FinBERT`（金融領域預訓練）或 Claude API 直接摘要
- **長期**：考慮 Unsloth 微調台股中文情緒模型（參考 ai_quant_trade 做法）

### 4-3 輸出格式

```python
{
  "stock_id": "2330",
  "sentiment_score": 0.72,      # 0~1，越高越正面
  "sentiment_label": "bullish", # bullish / neutral / bearish
  "news_count": 5,              # 今日相關新聞數量
  "key_events": ["法說會正面展望", "外資調升目標價"]
}
```

---

## 五、Alpha101 精選因子（後期）

從 WorldQuant 101 個因子中，篩選適合台股波段操作的因子：

| 因子編號 | 公式概念 | 適用場景 |
|---|---|---|
| Alpha#1 | 量價背離 | 反轉訊號 |
| Alpha#12 | 成交量符號 × 價格變化 | 趨勢確認 |
| Alpha#20 | 開高低收的相對關係 | 當日強弱 |
| Alpha#101 | 開收差 / 高低差 | 波動特徵 |

> ⚠️ 注意：部分 Alpha101 因子為 A股設計，需驗證在台股的有效性後再採用。

---

## 六、與六 Agent 架構的整合方式

```
factor_engine 輸出
        │
        ├──→ 技術面 Agent     ← technical 因子
        ├──→ 籌碼面 Agent     ← chips 因子
        ├──→ 情緒面 Agent     ← sentiment 輸出
        ├──→ 風控 Agent       ← 所有因子綜合
        ├──→ 魔鬼代言人 Agent  ← 挑戰所有信號
        └──→ 決策整合 Agent   ← 最終買賣建議
```

---

## 七、執行時程建議

```
Week 1：Factor Engine 技術面層（pandas-ta 安裝 + technical.py）
Week 2：Factor Engine 籌碼面層（FinMind API + chips.py）
Week 3：output_formatter + 接入六 Agent context
Week 4：VectorBT 回測框架骨架
Week 5-6：情緒分析模組（新聞爬蟲 + FinBERT）
Week 7+：Alpha101 精選因子移植與驗證
```

---

## 八、安裝依賴

```bash
# 技術面因子
pip install pandas-ta
pip install stockstats

# 回測框架
pip install vectorbt
pip install backtrader

# NLP 情緒分析
pip install transformers
pip install torch

# 資料來源
pip install finmind
```

---

*本文件隨開發進度持續更新*
