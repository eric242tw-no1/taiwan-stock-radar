"use client";
import { useEffect, useRef, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";


function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return isMobile;
}

const API = "";

// ── 型別 ───────────────────────────────────────────────────
interface Quote {
  symbol: string; name: string; exchange: string;
  price: number; prev_close: number; open: number; high: number; low: number;
  change: number; change_pct: number; volume: number;
  vol_ratio: number | null; update_time: string; market_status: string;
}
interface Indicator {
  ticker: string; trade_date: string; close: number; volume: number;
  rsi14: number; macd: number; macd_signal: number; macd_hist: number;
  k: number; d: number; atr14: number;
  ma20?: number; ma20_bias?: number; bias_pct?: number;
}
interface OhlcBar { time: string; open: number; high: number; low: number; close: number; volume: number; }
interface ChipLatest { foreign: number; trust: number; dealer: number; date: string; }
interface ChipDaily  { date: string; foreign: number; trust: number; dealer: number; }
interface Margin { date: string; margin_balance: number; margin_change: number; short_balance: number; short_change: number; short_ratio: number; }
interface ChipData { symbol: string; latest: ChipLatest; daily: ChipDaily[]; margin: Margin; }

// ── 常數 ────────────────────────────────────────────────────
const QUICK_PICKS = [
  { code: "2330", name: "台積電" }, { code: "2317", name: "鴻海" },
  { code: "2454", name: "聯發科" }, { code: "0050", name: "元大50" },
  { code: "2308", name: "台達電" }, { code: "2382", name: "廣達"   },
];
const PERIODS: { label: string; value: string; yf: string }[] = [
  { label: "日K", value: "1d", yf: "90d"  },
  { label: "週K", value: "1wk", yf: "1y"  },
  { label: "月K", value: "1mo", yf: "5y"  },
];
const MA_OPTIONS = [
  { label: "MA5",  days: 5,  color: "#f5d020" },
  { label: "MA20", days: 20, color: "#3d7eff" },
  { label: "MA60", days: 60, color: "#cc44ff" },
];

// ── 工具函數 ─────────────────────────────────────────────────
function rsiColor(v: number) {
  return v >= 70 ? "#ff4d4d" : v <= 30 ? "#00c076" : "#f5a623";
}
function rsiLabel(v: number) {
  if (v >= 80) return "超買";
  if (v >= 70) return "偏高";
  if (v <= 20) return "超賣";
  if (v <= 30) return "偏低";
  return "中性";
}

// ── 論壇情緒型別 ─────────────────────────────────────────────
interface SentimentData {
  symbol: string;
  source: string;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  total_posts: number;
  sentiment_score: number;
  label: string;
  updated_at: string;
}

// ── AI 分析型別 ───────────────────────────────────────────────
interface AiPanelist {
  name: string; score: number; verdict: "看多" | "中性" | "看空";
  hits: string[]; warnings: string[]; misses: string[]; comment: string;
}
interface AiIcMemo {
  bull: { prob: number; target: number; assumption: string; trigger?: string };
  base: { prob: number; target: number; assumption: string };
  bear: { prob: number; target: number; assumption: string };
  expected_value: number; risk_reward: number;
}
interface AiResult {
  score: number;
  action: "買進" | "持有" | "觀望" | "減倉" | "賣出";
  ideal_entry: number; alt_entry: number;
  stop_loss: number; take_profit: number;
  summary: string;
  panel: AiPanelist[];
  panel_summary: { bullish: number; neutral: number; bearish: number };
  ic_memo: AiIcMemo;
  debate: { bull_points: string[]; bear_points: string[]; verdict: string } | null;
  key_risks: string[];
  source?: string; _cached?: boolean;
}

// ── AI 評分引擎（rule-based fallback）────────────────────────
interface ScoreSet {
  tech: number; chip: number; fundamental: number;
  macro: number; risk: number; composite: number;
}
function scoreLabel(s: number): string {
  if (s >= 75) return "偏多";
  if (s >= 55) return "中性偏多";
  if (s >= 45) return "中性";
  if (s >= 30) return "中性偏空";
  return "偏空";
}
function scoreColor(s: number): string {
  if (s >= 75) return "#ff4d4d";
  if (s >= 55) return "#f5a623";
  if (s >= 45) return "#8888aa";
  if (s >= 30) return "#3d7eff";
  return "#00c076";
}

function computeScores(
  ind: Indicator | null,
  chip: ChipData | null,
  quote: Quote | null,
): ScoreSet {
  // ── 技術面 ──────────────────────────────────────────────────
  let tech = 50;
  if (ind) {
    // RSI
    const rsi = ind.rsi14;
    if (rsi >= 50 && rsi < 70)      tech += 15;
    else if (rsi >= 70 && rsi < 80) tech += 5;
    else if (rsi >= 80)             tech -= 15;
    else if (rsi > 30 && rsi < 50)  tech -= 5;
    else if (rsi <= 30 && rsi > 20) tech += 10; // 超賣反彈
    else if (rsi <= 20)             tech += 5;

    // MACD
    if (ind.macd_hist > 0) tech += 15;
    else                   tech -= 10;

    // MACD 金叉（macd 由負轉正）
    if (ind.macd > 0 && ind.macd_signal > 0 && ind.macd > ind.macd_signal) tech += 5;

    // KD
    if (ind.k > ind.d && ind.k < 80)    tech += 8;  // 黃金交叉且未超買
    else if (ind.k < ind.d && ind.k > 20) tech -= 8; // 死亡交叉且未超賣
    if (ind.k >= 80)                    tech -= 5;
    if (ind.k <= 20)                    tech += 5;
  }
  tech = Math.min(95, Math.max(5, tech));

  // ── 籌碼面 ──────────────────────────────────────────────────
  let chipScore = 50;
  if (chip) {
    const { latest, margin } = chip;
    // 外資（最重要）：單位是股，除以1000為張
    const foreignLots = latest.foreign / 1000;
    if (foreignLots > 5000)       chipScore += 20;
    else if (foreignLots > 1000)  chipScore += 12;
    else if (foreignLots > 0)     chipScore += 5;
    else if (foreignLots < -5000) chipScore -= 20;
    else if (foreignLots < -1000) chipScore -= 12;
    else                          chipScore -= 5;

    // 投信
    const trustLots = latest.trust / 1000;
    if (trustLots > 500)  chipScore += 8;
    else if (trustLots > 0) chipScore += 3;
    else if (trustLots < -500) chipScore -= 8;
    else chipScore -= 2;

    // 自營
    const dealerLots = latest.dealer / 1000;
    if (dealerLots > 0) chipScore += 3;
    else chipScore -= 2;

    // 融資：增加 = 散戶追高 = 偏負面；減少 = 偏正面
    if (margin.margin_change < -200)    chipScore += 6;
    else if (margin.margin_change < 0)  chipScore += 3;
    else if (margin.margin_change > 200) chipScore -= 5;

    // 融券（空單）：增加 = 看空；但高空單有軋空潛力
    if (margin.short_ratio > 20)        chipScore += 5; // 高空單 = 潛在軋空
    else if (margin.short_ratio > 10)   chipScore -= 3;
    else if (margin.short_ratio < 3)    chipScore += 3; // 幾乎沒人放空 = 信心強
  }
  chipScore = Math.min(95, Math.max(5, chipScore));

  // ── 基本面（無財報資料，用 ATR穩定度 + 成交量趨勢估算）────
  let fundamental = 55; // 預設中性偏正
  if (ind) {
    const atrPct = ind.close > 0 ? (ind.atr14 / ind.close) * 100 : 0;
    // ATR% 越小 = 波動越穩定 = 基本面支撐強
    if (atrPct < 1)       fundamental += 10;
    else if (atrPct < 2)  fundamental += 5;
    else if (atrPct > 5)  fundamental -= 10;
    else if (atrPct > 3)  fundamental -= 5;
  }
  fundamental = Math.min(75, Math.max(35, fundamental)); // 無財報 → 限縮區間

  // ── 宏觀（無即時宏觀資料，固定中性）────────────────────────
  const macro = 50;

  // ── 風控 ────────────────────────────────────────────────────
  let risk = 70; // 越高 = 風險越低（越安全）
  if (ind) {
    const atrPct = ind.close > 0 ? (ind.atr14 / ind.close) * 100 : 3;
    // 波動度
    if (atrPct > 5)       risk -= 25;
    else if (atrPct > 3)  risk -= 15;
    else if (atrPct > 2)  risk -= 8;
    else if (atrPct < 1)  risk += 10;

    // RSI 極端
    if (ind.rsi14 > 80 || ind.rsi14 < 20) risk -= 10;
  }
  if (quote) {
    // 單日大跌/大漲 = 風險提升
    const absPct = Math.abs(quote.change_pct);
    if (absPct > 6) risk -= 15;
    else if (absPct > 3) risk -= 8;
  }
  if (chip) {
    if (chip.margin.short_ratio > 15) risk -= 5;
  }
  risk = Math.min(95, Math.max(5, risk));

  // ── 綜合（加權平均）────────────────────────────────────────
  const composite = Math.round(
    tech * 0.30 + chipScore * 0.30 + fundamental * 0.15 +
    macro * 0.10 + risk * 0.15
  );

  return { tech, chip: chipScore, fundamental, macro, risk, composite };
}

// ── 共用元件 ─────────────────────────────────────────────────
function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 8, padding: 12 }}>
      {title && <div style={{ fontSize: 17, color: "#8888aa", marginBottom: 10, fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase" }}>{title}</div>}
      {children}
    </div>
  );
}

function MetricRow({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid #1a1a2a" }}>
      <div>
        <div style={{ fontSize: 18, color: "#8888aa" }}>{label}</div>
        {sub && <div style={{ fontSize: 18, color: "#555570", marginTop: 1 }}>{sub}</div>}
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, color: color ?? "#e8e8f0" }}>{value}</div>
    </div>
  );
}

// ── 指標計算函數 ────────────────────────────────────────────
type TimeVal = { time: `${number}-${number}-${number}`; value: number };

function calcMA(bars: OhlcBar[], n: number): TimeVal[] {
  return bars.map((_, i) => {
    if (i < n - 1) return null;
    const avg = bars.slice(i - n + 1, i + 1).reduce((s, b) => s + b.close, 0) / n;
    return { time: bars[i].time as `${number}-${number}-${number}`, value: Math.round(avg * 100) / 100 };
  }).filter(Boolean) as TimeVal[];
}

function calcBB(bars: OhlcBar[], n = 20, mult = 2): { mid: TimeVal[]; upper: TimeVal[]; lower: TimeVal[] } {
  const mid: TimeVal[] = [], upper: TimeVal[] = [], lower: TimeVal[] = [];
  for (let i = n - 1; i < bars.length; i++) {
    const slice = bars.slice(i - n + 1, i + 1).map(b => b.close);
    const avg = slice.reduce((s, v) => s + v, 0) / n;
    const std = Math.sqrt(slice.reduce((s, v) => s + (v - avg) ** 2, 0) / n);
    const t = bars[i].time as `${number}-${number}-${number}`;
    mid.push({ time: t, value: Math.round(avg * 100) / 100 });
    upper.push({ time: t, value: Math.round((avg + mult * std) * 100) / 100 });
    lower.push({ time: t, value: Math.round((avg - mult * std) * 100) / 100 });
  }
  return { mid, upper, lower };
}

function calcRSI(bars: OhlcBar[], n = 14): TimeVal[] {
  const result: TimeVal[] = [];
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < bars.length; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    if (i <= n) {
      avgGain += Math.max(diff, 0) / n;
      avgLoss += Math.max(-diff, 0) / n;
      if (i === n) result.push({ time: bars[i].time as `${number}-${number}-${number}`, value: 100 - 100 / (1 + avgGain / (avgLoss || 0.0001)) });
    } else {
      avgGain = (avgGain * (n - 1) + Math.max(diff, 0)) / n;
      avgLoss = (avgLoss * (n - 1) + Math.max(-diff, 0)) / n;
      result.push({ time: bars[i].time as `${number}-${number}-${number}`, value: Math.round((100 - 100 / (1 + avgGain / (avgLoss || 0.0001))) * 100) / 100 });
    }
  }
  return result;
}

function calcMACD(bars: OhlcBar[]): { macd: TimeVal[]; signal: TimeVal[]; hist: { time: `${number}-${number}-${number}`; value: number; color: string }[] } {
  const ema = (data: number[], n: number) => {
    const k = 2 / (n + 1), result: number[] = [];
    let e = data[0];
    for (const v of data) { e = v * k + e * (1 - k); result.push(e); }
    return result;
  };
  const closes = bars.map(b => b.close);
  const ema12 = ema(closes, 12), ema26 = ema(closes, 26);
  const macdLine = ema12.map((v, i) => v - ema26[i]);
  const signalLine = ema(macdLine, 9);
  const macd: TimeVal[] = [], signal: TimeVal[] = [];
  const hist: { time: `${number}-${number}-${number}`; value: number; color: string }[] = [];
  bars.forEach((b, i) => {
    if (i < 25) return;
    const t = b.time as `${number}-${number}-${number}`;
    const m = Math.round(macdLine[i] * 100) / 100;
    const s = Math.round(signalLine[i] * 100) / 100;
    const h = Math.round((m - s) * 100) / 100;
    macd.push({ time: t, value: m });
    signal.push({ time: t, value: s });
    hist.push({ time: t, value: h, color: h >= 0 ? "#ff4d4d" : "#00c076" });
  });
  return { macd, signal, hist };
}

function calcOBV(bars: OhlcBar[]): TimeVal[] {
  let obv = 0;
  return bars.map((b, i) => {
    if (i > 0) {
      if (b.close > bars[i - 1].close) obv += b.volume;
      else if (b.close < bars[i - 1].close) obv -= b.volume;
    }
    return { time: b.time as `${number}-${number}-${number}`, value: obv };
  });
}

// ── 子圖設定 ──────────────────────────────────────────────
const SUB_INDICATORS = [
  { key: "bb",   label: "布林" },
  { key: "vol",  label: "成交量" },
  { key: "rsi",  label: "RSI" },
  { key: "macd", label: "MACD" },
  { key: "obv",  label: "OBV" },
];

// ── K 線圖 ──────────────────────────────────────────────────
function CandleChart({ bars, maEnabled, subEnabled }: {
  bars: OhlcBar[];
  maEnabled: Set<number>;
  subEnabled: Set<string>;
}) {
  const mainRef = useRef<HTMLDivElement>(null);
  const volRef  = useRef<HTMLDivElement>(null);
  const rsiRef  = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const obvRef  = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mainRef.current || bars.length === 0) return;
    const charts: { remove?: () => void }[] = [];

    import("lightweight-charts").then((lc) => {
      const { createChart, CandlestickSeries, LineSeries, HistogramSeries } = lc as {
        createChart: typeof import("lightweight-charts").createChart;
        CandlestickSeries: typeof import("lightweight-charts").CandlestickSeries;
        LineSeries: typeof import("lightweight-charts").LineSeries;
        HistogramSeries: typeof import("lightweight-charts").HistogramSeries;
      };

      const chartOpts = (el: HTMLDivElement, height: number, hideTime = true) => {
        el.innerHTML = "";
        const w = el.getBoundingClientRect().width || el.offsetWidth || 700;
        return createChart(el, {
          width: w, height,
          layout: { background: { color: "#111118" }, textColor: "#8888aa" },
          grid: { vertLines: { color: "#1a1a2a" }, horzLines: { color: "#1a1a2a" } },
          crosshair: { mode: 1 },
          timeScale: { borderColor: "#2a2a3a", timeVisible: !hideTime, visible: !hideTime },
          rightPriceScale: { borderColor: "#2a2a3a" },
        });
      };

      // ── 主圖 ──────────────────────────────────────────────
      if (!mainRef.current) return;
      const main = chartOpts(mainRef.current, 300, true);
      charts.push(main);

      const candle = main.addSeries(CandlestickSeries, {
        upColor: "#ff4d4d", downColor: "#00c076",
        borderUpColor: "#ff4d4d", borderDownColor: "#00c076",
        wickUpColor: "#ff4d4d", wickDownColor: "#00c076",
      });
      candle.setData(bars.map(b => ({
        time: b.time as `${number}-${number}-${number}`,
        open: b.open, high: b.high, low: b.low, close: b.close,
      })));

      // MA 均線
      MA_OPTIONS.forEach(({ days, color }) => {
        if (!maEnabled.has(days)) return;
        const s = main.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(calcMA(bars, days));
      });

      // 布林通道
      if (subEnabled.has("bb")) {
        const bb = calcBB(bars);
        const bbOpts = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false };
        main.addSeries(LineSeries, { ...bbOpts, color: "#3d7eff" }).setData(bb.upper);
        main.addSeries(LineSeries, { ...bbOpts, color: "#3d7eff" }).setData(bb.mid);
        main.addSeries(LineSeries, { ...bbOpts, color: "#3d7eff" }).setData(bb.lower);
      }

      main.timeScale().fitContent();

      // ── 子圖同步輔助 ──────────────────────────────────────
      const subCharts: ReturnType<typeof createChart>[] = [];

      const makeSub = (ref: React.RefObject<HTMLDivElement | null>, height: number, isLast: boolean) => {
        if (!ref.current) return null;
        const c = chartOpts(ref.current, height, !isLast);
        (c as unknown as { applyOptions: (o: object) => void }).applyOptions({
          timeScale: { borderColor: "#2a2a3a", timeVisible: isLast, visible: isLast },
          leftPriceScale: { visible: false },
        });
        charts.push(c);
        subCharts.push(c);
        return c;
      };

      // 計算啟用的子圖並決定哪個是最後一個（顯示時間軸）
      const enabledSubs = ["vol", "rsi", "macd", "obv"].filter(k => subEnabled.has(k));
      const lastSub = enabledSubs[enabledSubs.length - 1];

      // ── 成交量 ──────────────────────────────────────────
      if (subEnabled.has("vol") && volRef.current) {
        const c = makeSub(volRef, 80, lastSub === "vol");
        if (c) {
          const vs = c.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false });
          vs.setData(bars.map(b => ({
            time: b.time as `${number}-${number}-${number}`,
            value: b.volume,
            color: b.close >= b.open ? "#ff4d4d66" : "#00c07666",
          })));
        }
      }

      // ── RSI ────────────────────────────────────────────
      if (subEnabled.has("rsi") && rsiRef.current) {
        const c = makeSub(rsiRef, 100, lastSub === "rsi");
        if (c) {
          c.addSeries(LineSeries, { color: "#8888aa", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false })
            .setData(bars.map(b => ({ time: b.time as `${number}-${number}-${number}`, value: 70 })));
          c.addSeries(LineSeries, { color: "#8888aa", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false })
            .setData(bars.map(b => ({ time: b.time as `${number}-${number}-${number}`, value: 30 })));
          c.addSeries(LineSeries, { color: "#f5a623", lineWidth: 2 as const, priceLineVisible: false, lastValueVisible: true })
            .setData(calcRSI(bars));
        }
      }

      // ── MACD ───────────────────────────────────────────
      if (subEnabled.has("macd") && macdRef.current) {
        const c = makeSub(macdRef, 100, lastSub === "macd");
        if (c) {
          const { macd, signal, hist } = calcMACD(bars);
          c.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }).setData(hist);
          c.addSeries(LineSeries, { color: "#3d7eff", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false }).setData(macd);
          c.addSeries(LineSeries, { color: "#ff4d4d", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false }).setData(signal);
        }
      }

      // ── OBV ────────────────────────────────────────────
      if (subEnabled.has("obv") && obvRef.current) {
        const c = makeSub(obvRef, 100, lastSub === "obv");
        if (c) {
          c.addSeries(LineSeries, { color: "#cc44ff", lineWidth: 2 as const, priceLineVisible: false, lastValueVisible: true })
            .setData(calcOBV(bars));
        }
      }

      // (十字準線跨圖同步需 v5 pane API，暫略)

      // ── 同步時間軸縮放/平移 ───────────────────────────
      main.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return;
        subCharts.forEach(c => c.timeScale().setVisibleLogicalRange(range));
      });
      subCharts.forEach(sub => {
        sub.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (!range) return;
          main.timeScale().setVisibleLogicalRange(range);
          subCharts.forEach(c => { if (c !== sub) c.timeScale().setVisibleLogicalRange(range); });
        });
      });
    });

    return () => { charts.forEach(c => c.remove?.()); };
  }, [bars, maEnabled, subEnabled]);

  const showVol  = subEnabled.has("vol");
  const showRSI  = subEnabled.has("rsi");
  const showMACD = subEnabled.has("macd");
  const showOBV  = subEnabled.has("obv");

  return (
    <div style={{ width: "100%" }}>
      <div ref={mainRef} style={{ width: "100%", height: 300 }} />
      {showVol  && <div style={{ borderTop: "1px solid #1a1a2a" }}><div style={{ fontSize: 10, color: "#555570", padding: "2px 4px" }}>VOL</div><div ref={volRef} style={{ width: "100%", height: 80 }} /></div>}
      {showRSI  && <div style={{ borderTop: "1px solid #1a1a2a" }}><div style={{ fontSize: 10, color: "#555570", padding: "2px 4px" }}>RSI(14)</div><div ref={rsiRef} style={{ width: "100%", height: 100 }} /></div>}
      {showMACD && <div style={{ borderTop: "1px solid #1a1a2a" }}><div style={{ fontSize: 10, color: "#555570", padding: "2px 4px" }}>MACD(12,26,9)</div><div ref={macdRef} style={{ width: "100%", height: 100 }} /></div>}
      {showOBV  && <div style={{ borderTop: "1px solid #1a1a2a" }}><div style={{ fontSize: 10, color: "#555570", padding: "2px 4px" }}>OBV</div><div ref={obvRef} style={{ width: "100%", height: 100 }} /></div>}
    </div>
  );
}

// ── 主頁面 ──────────────────────────────────────────────────
function StockPageInner({ initialSymbol }: { initialSymbol: string }) {
  const isMobile = useIsMobile();
  const [symbol, setSymbol]     = useState(initialSymbol);
  const [input,  setInput]      = useState("");
  const [quote,  setQuote]      = useState<Quote | null>(null);
  const [ind,    setInd]        = useState<Indicator | null>(null);
  const [chip,   setChip]       = useState<ChipData | null>(null);
  const [bars,   setBars]       = useState<OhlcBar[]>([]);
  const [period, setPeriod]     = useState(PERIODS[0]);
  const [maEnabled, setMaEnabled] = useState<Set<number>>(new Set([5, 20]));
  const [subEnabled, setSubEnabled] = useState<Set<string>>(new Set(["vol", "rsi"]));
  const [loading, setLoading]   = useState(false);
  const [indErr,  setIndErr]    = useState("");
  const [aiResult, setAiResult] = useState<AiResult | null>(null);
  const [sentiment, setSentiment] = useState<{ ptt: SentimentData | null; cmoney: SentimentData | null } | null>(null);

  // ── 即時報價（10秒更新）────────────────────────────────
  const fetchQuote = useCallback(() => {
    fetch(`${API}/api/stock/${symbol}/quote`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setQuote(d))
      .catch(() => {});
  }, [symbol]);

  useEffect(() => {
    setQuote(null);
    fetchQuote();
    const id = setInterval(fetchQuote, 10_000);
    return () => clearInterval(id);
  }, [fetchQuote]);

  // ── 籌碼 ────────────────────────────────────────────────
  useEffect(() => {
    setChip(null);
    fetch(`${API}/api/stock/${symbol}/chip`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setChip(d))
      .catch(() => {});
  }, [symbol]);

  // ── 技術指標 ────────────────────────────────────────────
  useEffect(() => {
    setInd(null); setIndErr("");
    fetch(`${API}/api/market/indicators/${symbol}.TW`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setInd)
      .catch(() => setIndErr("等收盤後計算（每日15:05更新）"));
  }, [symbol]);

  // ── AI 深度分析（Claude API，快取至隔日 09:00）───────────
  useEffect(() => {
    setAiResult(null);
    fetch(`${API}/api/stock/${symbol}/ai-analysis`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d && d.source !== "rule_based" && d.score != null) {
          setAiResult(d as AiResult);
        }
      })
      .catch(() => {});
  }, [symbol]);

  // ── 論壇情緒（PTT + CMoney，30分鐘快取）──────────────────
  useEffect(() => {
    setSentiment(null);
    fetch(`${API}/api/stock/${symbol}/sentiment`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setSentiment({ ptt: d.ptt ?? null, cmoney: d.cmoney ?? null }))
      .catch(() => {});
  }, [symbol]);

  // ── OHLCV K 線 ─────────────────────────────────────────
  useEffect(() => {
    setLoading(true);
    setBars([]);
    fetch(`${API}/api/stock/${symbol}/ohlcv?period=${period.yf}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setBars(d.bars ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol, period]);

  function search() {
    const t = input.trim().replace(/\.TW$/i, "");
    if (t) { setSymbol(t.toUpperCase()); setInput(""); }
  }

  function toggleMa(days: number) {
    setMaEnabled(prev => {
      const next = new Set(prev);
      next.has(days) ? next.delete(days) : next.add(days);
      return next;
    });
  }

  // 非交易時間用 K 線最後一根收盤價作 fallback
  const lastBar = bars.length > 0 ? bars[bars.length - 1] : null;
  const displayPrice = quote?.price ?? lastBar?.close ?? 0;
  const displayName  = quote?.name ?? symbol;

  const up = (quote?.change ?? 0) >= 0;
  const chgColor = up ? "#ff4d4d" : "#00c076";
  const volRatioColor = !quote?.vol_ratio ? "#8888aa"
    : quote.vol_ratio >= 2 ? "#ff4d4d"
    : quote.vol_ratio >= 1.5 ? "#f5a623"
    : "#8888aa";

  const ruleScores = computeScores(ind, chip, quote);
  const hasAi  = aiResult !== null;
  const composite = hasAi ? aiResult.score : ruleScores.composite;
  const scoreSource = hasAi ? "Claude AI" : "規則計算";
  const hasData = ind !== null || chip !== null;
  const scoreDims = [
    { label: "技術", score: ind        ? ruleScores.tech        : null, color: "#3d7eff" },
    { label: "籌碼", score: chip       ? ruleScores.chip        : null, color: "#f5a623" },
    { label: "基本", score: ind        ? ruleScores.fundamental : null, color: "#cc44ff" },
    { label: "宏觀", score:              ruleScores.macro,               color: "#00c076" },
    { label: "風控", score: (ind||quote)? ruleScores.risk        : null, color: "#ff6b35" },
  ] as const;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%", boxSizing: "border-box", overflow: "hidden" }}>

      {/* ── 搜尋列 ── */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex" }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && search()}
            placeholder="輸入代號，如 2330"
            style={{
              background: "#111118", border: "1px solid #2a2a3a", borderRight: "none",
              borderRadius: "6px 0 0 6px", padding: "7px 12px",
              color: "#e8e8f0", fontSize: 17, outline: "none", width: 180,
            }}
          />
          <button onClick={search} style={{
            background: "#00c076", border: "none", borderRadius: "0 6px 6px 0",
            padding: "7px 14px", color: "#000", fontWeight: 700, cursor: "pointer", fontSize: 17,
          }}>查詢</button>
        </div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {QUICK_PICKS.map(p => (
            <button key={p.code} onClick={() => setSymbol(p.code)} style={{
              background: symbol === p.code ? "#1a2a1a" : "#111118",
              border: `1px solid ${symbol === p.code ? "#00c076" : "#2a2a3a"}`,
              borderRadius: 5, padding: "4px 9px", cursor: "pointer",
              color: symbol === p.code ? "#00c076" : "#8888aa", fontSize: 18,
            }}>{p.code} {p.name}</button>
          ))}
        </div>
      </div>

      {/* ── Hero 全寬 ── */}
        {/* Hero Card */}
        <div style={{
          background: "linear-gradient(135deg, #0d1020 0%, #111118 100%)",
          border: "1px solid #2a2a3a", borderRadius: 10, padding: "12px 16px 12px 12px",
          display: "flex", alignItems: "center", gap: 20, overflow: "hidden", minWidth: 0,
        }}>
          {/* 名稱 + 狀態 */}
          <div style={{ minWidth: 100 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: "#3d7eff" }}>{quote?.symbol ?? symbol}</span>
              <span style={{ fontSize: 15, color: "#c8c8d8" }}>{displayName}</span>
              {quote?.exchange && (
                <span style={{ fontSize: 12, color: "#555570", padding: "1px 5px", border: "1px solid #2a2a3a", borderRadius: 3 }}>
                  {quote.exchange}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: "#555570", marginTop: 3 }}>
              {quote ? `${quote.market_status} ｜ ${quote.update_time || "--:--"}` : (lastBar ? `收盤 ｜ ${lastBar.time}` : "載入中...")}
            </div>
          </div>

          {/* 大價格 */}
          <div>
            <div style={{ fontSize: 40, fontWeight: 700, color: "#e8e8f0", letterSpacing: -2, lineHeight: 1 }}>
              {displayPrice > 0 ? displayPrice.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "---"}
            </div>
            {quote && (
              <div style={{ fontSize: 16, fontWeight: 600, color: chgColor, marginTop: 4 }}>
                {up ? "▲" : "▼"} {Math.abs(quote.change).toFixed(2)} &nbsp;
                ({up ? "+" : ""}{quote.change_pct.toFixed(2)}%)
              </div>
            )}
          </div>

          {/* OHLC + 成交量 */}
          {(() => {
            const ohlc = quote
              ? [{ l: "開盤", v: quote.open }, { l: "最高", v: quote.high }, { l: "最低", v: quote.low }, { l: "昨收", v: quote.prev_close }]
              : lastBar
              ? [{ l: "開盤", v: lastBar.open }, { l: "最高", v: lastBar.high }, { l: "最低", v: lastBar.low }, { l: "收盤", v: lastBar.close }]
              : [];
            return ohlc.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 18px" }}>
                {ohlc.map(({ l, v }) => (
                  <div key={l} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span style={{ fontSize: 12, color: "#555570" }}>{l}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#c8c8d8" }}>{v > 0 ? v.toFixed(2) : "---"}</span>
                  </div>
                ))}
              </div>
            ) : null;
          })()}

          {/* 成交量 */}
          {quote && quote.volume > 0 && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, color: "#555570" }}>成交量</div>
              <div style={{ fontSize: 18, fontWeight: 600, color: "#e8e8f0" }}>{quote.volume.toLocaleString()} 張</div>
              {quote.vol_ratio && (
                <div style={{ fontSize: 12, color: volRatioColor }}>量比 {quote.vol_ratio}x</div>
              )}
            </div>
          )}
        </div>

      {/* ── 主體：K 線 + 右側面板 ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : "1fr 260px",
        gap: 10, width: "100%",
      }}>

        {/* K 線圖 */}
        <div style={{ minWidth: 0, overflow: "hidden" }}>
        <Card>
          {/* 控制列 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            {/* 週期 */}
            <div style={{ display: "flex", gap: 4 }}>
              {PERIODS.map(p => (
                <button key={p.value} onClick={() => setPeriod(p)} style={{
                  background: period.value === p.value ? "#1a2a1a" : "transparent",
                  border: `1px solid ${period.value === p.value ? "#00c076" : "#2a2a3a"}`,
                  borderRadius: 4, padding: "3px 10px", cursor: "pointer",
                  color: period.value === p.value ? "#00c076" : "#8888aa", fontSize: 18,
                }}>{p.label}</button>
              ))}
            </div>
            {/* 均線 + 子指標 */}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {MA_OPTIONS.map(({ label, days, color }) => (
                <button key={days} onClick={() => toggleMa(days)} style={{
                  background: maEnabled.has(days) ? `${color}22` : "transparent",
                  border: `1px solid ${maEnabled.has(days) ? color : "#2a2a3a"}`,
                  borderRadius: 4, padding: "3px 8px", cursor: "pointer",
                  color: maEnabled.has(days) ? color : "#555570", fontSize: 17,
                }}>{label}</button>
              ))}
              <div style={{ width: 1, background: "#2a2a3a", margin: "0 2px" }} />
              {SUB_INDICATORS.map(({ key, label }) => {
                const active = subEnabled.has(key);
                return (
                  <button key={key} onClick={() => setSubEnabled(prev => {
                    const next = new Set(prev);
                    next.has(key) ? next.delete(key) : next.add(key);
                    return next;
                  })} style={{
                    background: active ? "#1a1a2e" : "transparent",
                    border: `1px solid ${active ? "#3d7eff" : "#2a2a3a"}`,
                    borderRadius: 4, padding: "3px 8px", cursor: "pointer",
                    color: active ? "#3d7eff" : "#555570", fontSize: 17,
                  }}>{label}</button>
                );
              })}
            </div>
          </div>

          {loading && <div style={{ color: "#555570", fontSize: 18, marginBottom: 6 }}>載入K線...</div>}
          {bars.length > 0
            ? <CandleChart bars={bars} maEnabled={maEnabled} subEnabled={subEnabled} />
            : !loading && (
              <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "#555570", fontSize: 17 }}>
                無K線資料
              </div>
            )
          }
        </Card>
        </div>

        {/* 右側面板 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

          {/* AI Score 卡片 */}
          <div style={{
            background: "#0d0d18", border: `1px solid ${hasAi ? "#00c07633" : "#2a2a3a"}`, borderRadius: 8, padding: "14px 16px",
            display: "flex", flexDirection: "column", alignItems: "center",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: "#555570", letterSpacing: 1, textTransform: "uppercase" }}>AI 綜合評分</div>
              <span style={{
                fontSize: 9, padding: "1px 5px", borderRadius: 3,
                background: hasAi ? "#1a2a1a" : "#1a1a2a",
                color: hasAi ? "#00c076" : "#555570",
                border: `1px solid ${hasAi ? "#00c07644" : "#2a2a3a"}`,
              }}>{scoreSource}</span>
            </div>

            {/* 圓形評分 */}
            <div style={{
              width: 96, height: 96, borderRadius: "50%", position: "relative",
              background: hasData ? `conic-gradient(${scoreColor(composite)} 0% ${composite}%, #1a1a2a ${composite}% 100%)` : "#1a1a2a",
              boxShadow: hasData ? `0 0 22px ${scoreColor(composite)}44` : "none",
            }}>
              <div style={{
                position: "absolute", inset: 7, borderRadius: "50%", background: "#0d0d18",
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: hasData ? scoreColor(composite) : "#333350", lineHeight: 1 }}>
                  {hasData ? composite : "--"}
                </div>
                <div style={{ fontSize: 10, color: "#555570" }}>/ 100</div>
              </div>
            </div>

            {/* 操作建議標籤 */}
            <div style={{ margin: "8px 0 10px", display: "flex", gap: 6, alignItems: "center" }}>
              {hasAi ? (
                <span style={{
                  fontSize: 13, fontWeight: 800, padding: "3px 12px", borderRadius: 5,
                  background: { "買進":"#1a3a1a","強勢做多":"#1a3a1a","持有":"#1a2a2a","觀望":"#1a1a2a","減倉":"#2a1a1a","賣出":"#3a0000" }[aiResult.action] ?? "#1a1a2a",
                  color: { "買進":"#00c076","強勢做多":"#00ff88","持有":"#3d7eff","觀望":"#8888aa","減倉":"#f5a623","賣出":"#ff4d4d" }[aiResult.action] ?? "#8888aa",
                  border: `1px solid currentColor`,
                }}>
                  {aiResult.action}
                </span>
              ) : (
                <span style={{ fontSize: 12, fontWeight: 600, color: hasData ? scoreColor(composite) : "#333350" }}>
                  {hasData ? scoreLabel(composite) : "載入中"}
                </span>
              )}
            </div>

            {/* 維度分數條 */}
            <div style={{ width: "100%" }}>
              {scoreDims.map(({ label, score, color }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14, color: "#666680", width: 32 }}>{label}</span>
                  <div style={{ flex: 1, height: 4, background: "#1a1a2a", borderRadius: 2 }}>
                    <div style={{
                      height: "100%", borderRadius: 2,
                      background: score !== null ? `linear-gradient(90deg, ${color}88, ${color})` : "#252535",
                      width: score !== null ? `${score}%` : "20%",
                      opacity: score !== null ? 1 : 0.3,
                      transition: "width 0.5s ease",
                    }} />
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: score !== null ? color : "#333350", width: 24, textAlign: "right" }}>
                    {score !== null ? score : "--"}
                  </span>
                </div>
              ))}
            </div>

            {/* AI 進出場價位 */}
            {hasAi && (
              <div style={{ marginTop: 10, width: "100%", borderTop: "1px solid #1a1a2a", paddingTop: 10 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {[
                    { label: "理想進場", val: aiResult.ideal_entry, color: "#00c076" },
                    { label: "次佳進場", val: aiResult.alt_entry,   color: "#3d7eff" },
                    { label: "停損",     val: aiResult.stop_loss,   color: "#ff4d4d" },
                    { label: "目標價",   val: aiResult.take_profit, color: "#f5a623" },
                  ].map(({ label, val, color }) => (
                    <div key={label} style={{ background: "#111118", borderRadius: 5, padding: "5px 8px" }}>
                      <div style={{ fontSize: 10, color: "#555570" }}>{label}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color, fontFamily: "monospace" }}>
                        {val ? val.toLocaleString() : "---"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI summary */}
            {hasAi && aiResult.summary && (
              <div style={{ marginTop: 10, width: "100%", borderTop: "1px solid #1a1a2a", paddingTop: 8 }}>
                <div style={{ fontSize: 11, color: "#8888aa", lineHeight: 1.7 }}>{aiResult.summary}</div>
              </div>
            )}

            {!hasAi && (
              <div style={{ marginTop: 8, fontSize: 10, color: "#444460", textAlign: "center" }}>
                設定 ANTHROPIC_API_KEY 啟用 Claude 深度分析
              </div>
            )}
          </div>

          {/* 論壇情緒 */}
          {sentiment && (sentiment.ptt || sentiment.cmoney) && (
            <Card title="論壇情緒（散戶觀點）">
              {[
                { key: "ptt", label: "PTT Stock 板", data: sentiment.ptt },
                { key: "cmoney", label: "CMoney 討論區", data: sentiment.cmoney },
              ].map(({ key, label, data }) =>
                data ? (
                  <div key={key} style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 11, color: "#555570", marginBottom: 6 }}>{label}</div>
                    {[
                      { name: "看漲", count: data.bullish_count, color: "#ff4d4d" },
                      { name: "看跌", count: data.bearish_count, color: "#00c076" },
                      { name: "中性", count: data.neutral_count, color: "#555570" },
                    ].map(bar => (
                      <div key={bar.name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: "#8888aa", width: 28 }}>{bar.name}</span>
                        <div style={{ flex: 1, height: 6, background: "#1a1a2a", borderRadius: 3 }}>
                          <div style={{
                            height: "100%", borderRadius: 3, background: bar.color,
                            width: data.total_posts > 0 ? `${(bar.count / data.total_posts) * 100}%` : "0%",
                            transition: "width 0.4s",
                          }} />
                        </div>
                        <span style={{ fontSize: 11, color: bar.color, width: 32, textAlign: "right" }}>
                          {data.total_posts > 0 ? `${Math.round((bar.count / data.total_posts) * 100)}%` : "—"}
                        </span>
                      </div>
                    ))}
                    <div style={{ fontSize: 11, color: "#555570", marginTop: 4 }}>
                      共 {data.total_posts} 篇討論・情緒：
                      <span style={{ color: data.sentiment_score > 0.1 ? "#ff4d4d" : data.sentiment_score < -0.1 ? "#00c076" : "#8888aa", fontWeight: 700 }}>
                        {data.label}
                      </span>
                    </div>
                  </div>
                ) : null
              )}
              <div style={{ fontSize: 10, color: "#444460", marginTop: 4 }}>關鍵字規則法・30分鐘更新</div>
            </Card>
          )}

          {/* 技術指標 */}
          <Card title="技術指標">
            {ind ? (
              <>
                <MetricRow label="收盤價" value={`$${ind.close.toLocaleString()}`} />
                <MetricRow
                  label="RSI (14)" sub={rsiLabel(ind.rsi14)}
                  value={ind.rsi14.toFixed(1)} color={rsiColor(ind.rsi14)}
                />
                <div style={{ margin: "3px 0 7px", height: 3, background: "#1a1a2a", borderRadius: 2 }}>
                  <div style={{ height: "100%", borderRadius: 2, background: rsiColor(ind.rsi14), width: `${ind.rsi14}%`, transition: "width 0.4s" }} />
                </div>
                <MetricRow label="MACD" sub={ind.macd_hist >= 0 ? "金叉" : "死叉"}
                  value={ind.macd.toFixed(2)} color={ind.macd_hist >= 0 ? "#00c076" : "#ff4d4d"} />
                <MetricRow label="Signal" value={ind.macd_signal.toFixed(2)} color="#f5a623" />
                <MetricRow label="Hist"
                  value={(ind.macd_hist >= 0 ? "+" : "") + ind.macd_hist.toFixed(2)}
                  color={ind.macd_hist >= 0 ? "#00c076" : "#ff4d4d"} />
                <MetricRow label="K" sub={ind.k >= 80 ? "高檔" : ind.k <= 20 ? "低檔" : "中性"}
                  value={ind.k.toFixed(1)}
                  color={ind.k >= 80 ? "#ff4d4d" : ind.k <= 20 ? "#00c076" : "#e8e8f0"} />
                <MetricRow label="D" value={ind.d.toFixed(1)} color="#8888aa" />
                <MetricRow label="ATR (14)" sub="日均波幅" value={ind.atr14.toFixed(1)} color="#8888aa" />
                {ind.ma20 != null && (
                  <MetricRow label="MA20" sub="20日均線" value={`$${ind.ma20.toLocaleString()}`} color="#3d7eff" />
                )}
                {ind.ma20_bias != null && (() => {
                  const bias = ind.ma20_bias!;
                  const pct  = ind.bias_pct ?? 50;
                  const biasColor = bias > 10 ? "#ff4d4d" : bias < -5 ? "#00c076" : "#f5a623";
                  const pctLabel  = pct >= 85 ? "過熱" : pct >= 70 ? "偏高" : pct <= 15 ? "過冷" : pct <= 30 ? "偏低" : "中性";
                  const pctColor  = pct >= 85 ? "#ff4d4d" : pct >= 70 ? "#f5a623" : pct <= 15 ? "#00c076" : pct <= 30 ? "#4dd0e1" : "#8888aa";
                  return (
                    <>
                      <MetricRow
                        label="MA20 乖離率"
                        sub={`偏離均線`}
                        value={(bias >= 0 ? "+" : "") + bias.toFixed(2) + "%"}
                        color={biasColor}
                      />
                      <div style={{ margin: "2px 0 8px", display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ flex: 1, height: 3, background: "#1a1a2a", borderRadius: 2, position: "relative" }}>
                          <div style={{ position: "absolute", left: 0, top: 0, height: "100%", borderRadius: 2, background: pctColor, width: `${pct}%`, transition: "width 0.4s" }} />
                          <div style={{ position: "absolute", left: "50%", top: -1, width: 1, height: 5, background: "#444460" }} />
                        </div>
                        <span style={{ fontSize: 11, color: pctColor, whiteSpace: "nowrap" }}>
                          {pct.toFixed(0)}百分位 · {pctLabel}
                        </span>
                      </div>
                    </>
                  );
                })()}
                <div style={{ marginTop: 8, fontSize: 18, color: "#444460" }}>
                  資料日期：{ind.trade_date}｜每日15:05更新
                </div>
              </>
            ) : (
              <div style={{ color: "#555570", fontSize: 18, padding: "8px 0" }}>
                {indErr || "載入中..."}
              </div>
            )}
          </Card>

          {/* 籌碼面板 */}
          <Card title="籌碼面板">
            {chip ? (() => {
              const { latest, margin } = chip;
              const fmt = (n: number) => {
                const lots = Math.round(n / 1000);
                return (lots >= 0 ? "+" : "") + lots.toLocaleString() + " 張";
              };
              const instRows = [
                { label: "外資", value: latest.foreign, color: latest.foreign >= 0 ? "#ff4d4d" : "#00c076" },
                { label: "投信", value: latest.trust,   color: latest.trust   >= 0 ? "#ff4d4d" : "#00c076" },
                { label: "自營", value: latest.dealer,  color: latest.dealer  >= 0 ? "#ff4d4d" : "#00c076" },
              ];
              return (
                <>
                  <div style={{ fontSize: 11, color: "#555570", marginBottom: 6 }}>三大法人（{latest.date}）</div>
                  {instRows.map(r => (
                    <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #1a1a2a" }}>
                      <span style={{ fontSize: 13, color: "#8888aa" }}>{r.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: r.color }}>{fmt(r.value)}</span>
                    </div>
                  ))}

                  <div style={{ fontSize: 11, color: "#555570", margin: "10px 0 6px" }}>融資融券（{margin.date}）</div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #1a1a2a" }}>
                    <span style={{ fontSize: 13, color: "#8888aa" }}>融資餘額</span>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "#e8e8f0" }}>{margin.margin_balance.toLocaleString()} 張</span>
                      <span style={{ fontSize: 11, color: margin.margin_change >= 0 ? "#ff4d4d" : "#00c076", marginLeft: 6 }}>
                        {margin.margin_change >= 0 ? "▲" : "▼"}{Math.abs(margin.margin_change)}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #1a1a2a" }}>
                    <span style={{ fontSize: 13, color: "#8888aa" }}>融券餘額</span>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "#e8e8f0" }}>{margin.short_balance.toLocaleString()} 張</span>
                      <span style={{ fontSize: 11, color: margin.short_change >= 0 ? "#ff4d4d" : "#00c076", marginLeft: 6 }}>
                        {margin.short_change >= 0 ? "▲" : "▼"}{Math.abs(margin.short_change)}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                    <span style={{ fontSize: 13, color: "#8888aa" }}>券資比</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: margin.short_ratio > 15 ? "#ff4d4d" : "#8888aa" }}>
                      {margin.short_ratio.toFixed(1)}%
                    </span>
                  </div>
                </>
              );
            })() : (
              <div style={{ color: "#555570", fontSize: 13, padding: "8px 0" }}>載入中...</div>
            )}
          </Card>

        </div>
      </div>

      {/* ── AI 深度分析（評審團 + IC備忘錄）── */}
      {hasAi && (
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 10 }}>

          {/* 評審團 */}
          <Card title={`AI 評審團（${aiResult.panel_summary.bullish}多 ${aiResult.panel_summary.neutral}中 ${aiResult.panel_summary.bearish}空）`}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {aiResult.panel.map(p => {
                const vc = p.verdict === "看多" ? "#ff4d4d" : p.verdict === "看空" ? "#00c076" : "#8888aa";
                return (
                  <div key={p.name} style={{ background: "#0d0d15", borderRadius: 6, padding: "8px 10px", border: `1px solid ${vc}22` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "#c8c8d8" }}>{p.name}</span>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: vc, padding: "1px 6px", border: `1px solid ${vc}44`, borderRadius: 3 }}>{p.verdict}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(p.score) }}>{p.score}</span>
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: "#8888aa", lineHeight: 1.5 }}>{p.comment}</div>
                    {p.hits.length > 0 && (
                      <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {p.hits.map((h, i) => <span key={i} style={{ fontSize: 10, color: "#ff4d4d", background: "#3d000022", padding: "1px 5px", borderRadius: 3 }}>✓ {h}</span>)}
                      </div>
                    )}
                    {p.misses.length > 0 && (
                      <div style={{ marginTop: 3, display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {p.misses.map((m, i) => <span key={i} style={{ fontSize: 10, color: "#555570", background: "#1a1a2a", padding: "1px 5px", borderRadius: 3 }}>✗ {m}</span>)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>

          {/* IC 備忘錄 + 辯論 + 風險 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Card title="IC 投委會備忘錄">
              {[
                { key: "bull" as const, label: "多頭情景", color: "#ff4d4d" },
                { key: "base" as const, label: "基本情景", color: "#f5a623" },
                { key: "bear" as const, label: "空頭情景", color: "#00c076" },
              ].map(({ key, label, color }) => {
                const s = aiResult.ic_memo[key];
                return (
                  <div key={key} style={{ marginBottom: 10, borderLeft: `3px solid ${color}`, paddingLeft: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ fontSize: 12, color, fontWeight: 700 }}>{label}</span>
                      <span style={{ fontSize: 12, color: "#8888aa" }}>機率 {s.prob}% ｜ 目標 <span style={{ color, fontWeight: 700 }}>{s.target}</span></span>
                    </div>
                    <div style={{ fontSize: 11, color: "#8888aa", lineHeight: 1.5 }}>{s.assumption}</div>
                    {"trigger" in s && s.trigger && (
                      <div style={{ fontSize: 10, color: "#555570", marginTop: 2 }}>觸發：{s.trigger}</div>
                    )}
                  </div>
                );
              })}
              <div style={{ borderTop: "1px solid #1a1a2a", paddingTop: 8, display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, color: "#8888aa" }}>期望值 <span style={{ color: "#f5a623", fontWeight: 700 }}>{aiResult.ic_memo.expected_value}</span></span>
                <span style={{ fontSize: 12, color: "#8888aa" }}>風報比 <span style={{ color: "#3d7eff", fontWeight: 700 }}>{aiResult.ic_memo.risk_reward?.toFixed(2)}</span></span>
              </div>
            </Card>

            {aiResult.debate && (
              <Card title="多空辯論">
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#ff4d4d", fontWeight: 700, marginBottom: 4 }}>看多論點</div>
                  {aiResult.debate.bull_points.map((p, i) => <div key={i} style={{ fontSize: 11, color: "#8888aa", marginBottom: 3 }}>▲ {p}</div>)}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#00c076", fontWeight: 700, marginBottom: 4 }}>看空論點</div>
                  {aiResult.debate.bear_points.map((p, i) => <div key={i} style={{ fontSize: 11, color: "#8888aa", marginBottom: 3 }}>▼ {p}</div>)}
                </div>
                <div style={{ borderTop: "1px solid #1a1a2a", paddingTop: 8, fontSize: 11, color: "#c8c8d8" }}>⚖️ {aiResult.debate.verdict}</div>
              </Card>
            )}

            <Card title="主要風險">
              {aiResult.key_risks.map((r, i) => (
                <div key={i} style={{ fontSize: 12, color: "#8888aa", padding: "5px 0", borderBottom: "1px solid #1a1a2a" }}>
                  ⚠️ {r}
                </div>
              ))}
            </Card>
          </div>

        </div>
      )}

      {/* ── 相關個股 ── */}
      <Card title="同類股">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {QUICK_PICKS.filter(p => p.code !== symbol).map(p => (
            <button key={p.code} onClick={() => setSymbol(p.code)} style={{
              background: "#0d0d15", border: "1px solid #2a2a3a", borderRadius: 6,
              padding: "8px 14px", cursor: "pointer", textAlign: "left",
            }}>
              <div style={{ fontSize: 17, color: "#3d7eff", fontWeight: 600 }}>{p.code}</div>
              <div style={{ fontSize: 17, color: "#8888aa" }}>{p.name}</div>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}

function StockPageWrapper() {
  const searchParams = useSearchParams();
  const s = searchParams.get("s") || "2330";
  // key={s} 確保每次股票代碼變化都完整 remount，不受 Next.js 快取影響
  return <StockPageInner key={s} initialSymbol={s} />;
}

export default function StockPage() {
  return (
    <Suspense fallback={null}>
      <StockPageWrapper />
    </Suspense>
  );
}
