"use client";
import { useEffect, useRef, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAppContext } from "@/contexts/AppContext";
import AtrStopModal from "@/components/AtrStopModal";
import { openTvInBrowser } from "@/components/TradingViewModal";


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
  patterns?: string[];
  market_maker_intent?: { phase: string; confidence: number; signals: string[] };
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

// ── AI 深度分析型別（Change E）────────────────────────────────
interface UziReviewer {
  name: string; role: string; score: number; verdict: string; reasoning: string;
}
interface UziResult {
  symbol: string; weighted_score: number; reviewers: UziReviewer[];
  consensus: string; generated_at?: string;
}
interface IcScenario {
  probability: number; target_price: number;
  key_assumptions: string[];
}
interface IcMemoResult {
  symbol: string;
  scenarios: { bull: IcScenario; base: IcScenario; bear: IcScenario };
  expected_value: number;
  current_price?: number;
  source?: string;
  generated_at?: string;
}
interface DebateArgument { title: string; argument: string; evidence: string; }
interface DebateArbiter { verdict: string; confidence: number; rationale: string; key_risk: string; }
interface DebateResult {
  symbol: string;
  bull_arguments: DebateArgument[];
  bear_arguments: DebateArgument[];
  arbiter: DebateArbiter;
  timestamp?: string;
}
type AiTab = "uzi" | "ic" | "debate";

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
  if (s >= 45) return "var(--c-text-dim)";
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
    <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14, boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }}>
      {title && <div style={{ fontSize: 17, color: "var(--c-text-dim)", marginBottom: 10, fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase" }}>{title}</div>}
      {children}
    </div>
  );
}

function MetricRow({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid var(--c-border)" }}>
      <div>
        <div style={{ fontSize: 18, color: "var(--c-text-dim)" }}>{label}</div>
        {sub && <div style={{ fontSize: 18, color: "var(--c-text-dim)", marginTop: 1 }}>{sub}</div>}
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, color: color ?? "var(--c-text)" }}>{value}</div>
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
function CandleChart({ bars, maEnabled, subEnabled, theme }: {
  bars: OhlcBar[];
  maEnabled: Set<number>;
  subEnabled: Set<string>;
  theme: string;
}) {
  const chartBg   = theme === "dark" ? "#0d1117" : "#ffffff";
  const chartGrid = theme === "dark" ? "#1e2d45" : "#c5d4e8";
  const chartText = theme === "dark" ? "#8888aa" : "#6080a0";
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
          // attributionLogo: 關掉角落的 TradingView logo（連到 TV 首頁易誤點；看個股線圖用工具列 📈 TV 按鈕）
          layout: { background: { color: chartBg }, textColor: chartText, attributionLogo: false },
          grid: { vertLines: { color: chartGrid }, horzLines: { color: chartGrid } },
          crosshair: { mode: 1 },
          timeScale: { borderColor: "var(--c-border)", timeVisible: !hideTime, visible: !hideTime },
          rightPriceScale: { borderColor: "var(--c-border)" },
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
          timeScale: { borderColor: "var(--c-border)", timeVisible: isLast, visible: isLast },
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
          c.addSeries(LineSeries, { color: "var(--c-text-dim)", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false })
            .setData(bars.map(b => ({ time: b.time as `${number}-${number}-${number}`, value: 70 })));
          c.addSeries(LineSeries, { color: "var(--c-text-dim)", lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false })
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
  }, [bars, maEnabled, subEnabled, theme]);

  const showVol  = subEnabled.has("vol");
  const showRSI  = subEnabled.has("rsi");
  const showMACD = subEnabled.has("macd");
  const showOBV  = subEnabled.has("obv");

  return (
    <div style={{ width: "100%" }}>
      <div ref={mainRef} style={{ width: "100%", height: 300 }} />
      {showVol  && <div style={{ borderTop: "1px solid var(--c-border)" }}><div style={{ fontSize: 10, color: "var(--c-text-dim)", padding: "2px 4px" }}>VOL</div><div ref={volRef} style={{ width: "100%", height: 80 }} /></div>}
      {showRSI  && <div style={{ borderTop: "1px solid var(--c-border)" }}><div style={{ fontSize: 10, color: "var(--c-text-dim)", padding: "2px 4px" }}>RSI(14)</div><div ref={rsiRef} style={{ width: "100%", height: 100 }} /></div>}
      {showMACD && <div style={{ borderTop: "1px solid var(--c-border)" }}><div style={{ fontSize: 10, color: "var(--c-text-dim)", padding: "2px 4px" }}>MACD(12,26,9)</div><div ref={macdRef} style={{ width: "100%", height: 100 }} /></div>}
      {showOBV  && <div style={{ borderTop: "1px solid var(--c-border)" }}><div style={{ fontSize: 10, color: "var(--c-text-dim)", padding: "2px 4px" }}>OBV</div><div ref={obvRef} style={{ width: "100%", height: 100 }} /></div>}
    </div>
  );
}

// ── 主頁面 ──────────────────────────────────────────────────
function StockPageInner({ initialSymbol }: { initialSymbol: string }) {
  const { theme } = useAppContext();
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
  const [showAtrModal, setShowAtrModal] = useState(false);

  // AI 深度分析 Tab（Change E）
  const [activeAiTab, setActiveAiTab] = useState<AiTab | null>(null);
  const [uziData, setUziData] = useState<UziResult | null>(null);
  const [uziLoading, setUziLoading] = useState(false);
  const [uziError, setUziError] = useState("");
  const [icData, setIcData] = useState<IcMemoResult | null>(null);
  const [icLoading, setIcLoading] = useState(false);
  const [icError, setIcError] = useState("");
  const [debateData, setDebateData] = useState<DebateResult | null>(null);
  const [debateLoading, setDebateLoading] = useState(false);
  const [debateError, setDebateError] = useState("");
  const [debateSlow, setDebateSlow] = useState(false);
  const debateAbortRef = useRef<AbortController | null>(null);

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

  // ── AI Tab：換 symbol 清除快取並取消進行中的辯論請求 ────────
  useEffect(() => {
    if (debateAbortRef.current) {
      debateAbortRef.current.abort();
      debateAbortRef.current = null;
    }
    setActiveAiTab(null);
    setUziData(null); setUziLoading(false); setUziError("");
    setIcData(null);  setIcLoading(false);  setIcError("");
    setDebateData(null); setDebateLoading(false); setDebateError(""); setDebateSlow(false);
  }, [symbol]);

  const fetchUzi = useCallback(async () => {
    if (uziData || uziLoading) return;
    setUziLoading(true); setUziError("");
    try {
      const r = await fetch(`${API}/api/analysis/uzi/${symbol}`, { method: "POST" });
      if (!r.ok) throw new Error(r.statusText);
      setUziData(await r.json());
    } catch { setUziError("UZI 分析失敗，請重試"); }
    finally { setUziLoading(false); }
  }, [symbol, uziData, uziLoading]);

  const fetchIcMemo = useCallback(async () => {
    if (icData || icLoading) return;
    setIcLoading(true); setIcError("");
    try {
      const r = await fetch(`${API}/api/analysis/ic-memo/${symbol}`);
      if (!r.ok) throw new Error(r.statusText);
      setIcData(await r.json());
    } catch { setIcError("IC 備忘錄生成失敗，請重試"); }
    finally { setIcLoading(false); }
  }, [symbol, icData, icLoading]);

  const fetchDebate = useCallback(async () => {
    if (debateData || debateLoading) return;
    setDebateLoading(true); setDebateError(""); setDebateSlow(false);
    const ctrl = new AbortController();
    debateAbortRef.current = ctrl;
    const slowTimer = setTimeout(() => setDebateSlow(true), 30_000);
    try {
      const r = await fetch(`${API}/api/analysis/debate/${symbol}`, {
        method: "POST", signal: ctrl.signal,
        headers: { "Content-Type": "application/json" }, body: "{}",
      });
      if (!r.ok) throw new Error(r.statusText);
      setDebateData(await r.json());
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== "AbortError")
        setDebateError("辯論分析超時，請重試");
    } finally {
      clearTimeout(slowTimer);
      setDebateLoading(false); setDebateSlow(false);
      debateAbortRef.current = null;
    }
  }, [symbol, debateData, debateLoading]);

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
  const volRatioColor = !quote?.vol_ratio ? "var(--c-text-dim)"
    : quote.vol_ratio >= 2 ? "#ff4d4d"
    : quote.vol_ratio >= 1.5 ? "#f5a623"
    : "var(--c-text-dim)";

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
    <div style={{ display: "flex", flexDirection: "column", gap: 20, width: "100%", boxSizing: "border-box", overflow: "hidden" }}>

      {/* ── 搜尋列 ── */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex" }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && search()}
            placeholder="輸入代號，如 2330"
            style={{
              background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRight: "none",
              borderRadius: "6px 0 0 6px", padding: "7px 12px",
              color: "var(--c-text)", fontSize: 17, outline: "none", width: 180,
            }}
          />
          <button onClick={search} style={{
            background: "#00c076", border: "none", borderRadius: "0 6px 6px 0",
            padding: "7px 14px", color: "#000", fontWeight: 700, cursor: "pointer", fontSize: 17, transition: "all 0.15s ease",
          }}>查詢</button>
        </div>
        <button onClick={() => setShowAtrModal(true)} style={{
          padding: "6px 14px", borderRadius: 6, background: "transparent",
          border: "1px solid var(--c-border)", color: "var(--c-text-dim)",
          cursor: "pointer", fontSize: 14, transition: "all 0.15s ease",
        }}>📐 ATR停損</button>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {QUICK_PICKS.map(p => (
            <button key={p.code} onClick={() => setSymbol(p.code)} style={{
              background: symbol === p.code ? "var(--c-bg-deep)" : "var(--c-bg-card)",
              border: `1px solid ${symbol === p.code ? "#00c076" : "var(--c-border)"}`,
              borderRadius: 20, padding: "4px 12px", cursor: "pointer",
              color: symbol === p.code ? "#00c076" : "var(--c-text-dim)", fontSize: 18,
              transition: "all 0.15s ease",
            }}>{p.code} {p.name}</button>
          ))}
        </div>
      </div>

      {/* ── Hero 全寬 ── */}
        {/* Hero Card */}
        <div style={{
          background: "linear-gradient(135deg, var(--c-bg-main) 0%, var(--c-bg-card) 100%)",
          border: "1px solid var(--c-border)", borderRadius: 10, padding: "14px 18px 14px 14px",
          display: "flex", alignItems: "center", gap: 20, overflow: "hidden", minWidth: 0,
          boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
        }}>
          {/* 名稱 + 狀態 */}
          <div style={{ minWidth: 100 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: "#3d7eff" }}>{quote?.symbol ?? symbol}</span>
              <span style={{ fontSize: 15, color: "var(--c-text-mid)" }}>{displayName}</span>
              {quote?.exchange && (
                <span style={{ fontSize: 12, color: "var(--c-text-dim)", padding: "1px 5px", border: "1px solid var(--c-border)", borderRadius: 3 }}>
                  {quote.exchange}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginTop: 3 }}>
              {quote ? `${quote.market_status} ｜ ${quote.update_time || "--:--"}` : (lastBar ? `收盤 ｜ ${lastBar.time}` : "載入中...")}
            </div>
          </div>

          {/* 大價格 */}
          <div>
            <div style={{ fontSize: 40, fontWeight: 700, color: "var(--c-text)", letterSpacing: -2, lineHeight: 1 }}>
              {displayPrice > 0 ? displayPrice.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "---"}
            </div>
            {quote && (
              <div style={{ fontSize: 16, fontWeight: 600, color: chgColor, marginTop: 4 }}>
                {up ? "▲" : "▼"} {Math.abs(quote.change).toFixed(2)} &nbsp;
                ({up ? "+" : ""}{quote.change_pct.toFixed(2)}%)
              </div>
            )}
          </div>

          {/* OHLC + 成交量（手機隱藏）*/}
          {!isMobile && (() => {
            const ohlc = quote
              ? [{ l: "開盤", v: quote.open }, { l: "最高", v: quote.high }, { l: "最低", v: quote.low }, { l: "昨收", v: quote.prev_close }]
              : lastBar
              ? [{ l: "開盤", v: lastBar.open }, { l: "最高", v: lastBar.high }, { l: "最低", v: lastBar.low }, { l: "收盤", v: lastBar.close }]
              : [];
            return ohlc.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 18px" }}>
                {ohlc.map(({ l, v }) => (
                  <div key={l} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>{l}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--c-text-mid)" }}>{v > 0 ? v.toFixed(2) : "---"}</span>
                  </div>
                ))}
              </div>
            ) : null;
          })()}

          {/* 成交量（手機隱藏）*/}
          {!isMobile && quote && quote.volume > 0 && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)" }}>成交量</div>
              <div style={{ fontSize: 18, fontWeight: 600, color: "var(--c-text)" }}>{quote.volume.toLocaleString()} 張</div>
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
        gap: 12, width: "100%",
      }}>

        {/* K 線圖 */}
        <div style={{ minWidth: 0, overflow: "hidden" }}>
        <Card>
          {/* 控制列 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 10 }}>
            {/* 週期 */}
            <div style={{ display: "flex", gap: 4, background: "var(--c-bg-deep)", borderRadius: 8, padding: 3 }}>
              {PERIODS.map(p => (
                <button key={p.value} onClick={() => setPeriod(p)} style={{
                  background: period.value === p.value ? "var(--c-bg-card)" : "transparent",
                  border: "none", borderRadius: 6, padding: "5px 12px", cursor: "pointer", height: 32,
                  color: period.value === p.value ? "#00c076" : "var(--c-text-dim)", fontSize: 18,
                  boxShadow: period.value === p.value ? "0 1px 2px rgba(0,0,0,0.15)" : "none",
                  transition: "all 0.15s ease",
                }}>{p.label}</button>
              ))}
            </div>
            {/* 均線 + 子指標 */}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", background: "var(--c-bg-deep)", borderRadius: 8, padding: 3 }}>
              {MA_OPTIONS.map(({ label, days, color }) => (
                <button key={days} onClick={() => toggleMa(days)} style={{
                  background: maEnabled.has(days) ? `${color}22` : "transparent",
                  border: "none", borderRadius: 6, padding: "5px 10px", cursor: "pointer", height: 32,
                  color: maEnabled.has(days) ? color : "var(--c-text-dim)", fontSize: 17,
                  boxShadow: maEnabled.has(days) ? `inset 0 0 0 1px ${color}` : "none",
                  transition: "all 0.15s ease",
                }}>{label}</button>
              ))}
              {/* 台股資料不授權嵌入式 widget，直接開系統瀏覽器的 TradingView 完整版 */}
              <button onClick={() => openTvInBrowser(`TWSE:${symbol}`)} title="在 TradingView 查看" style={{
                background: "transparent", border: "none", borderRadius: 6, padding: "5px 10px", cursor: "pointer", height: 32,
                color: "#3d7eff", fontSize: 17, transition: "all 0.15s ease",
              }}>📈 TV</button>
              <div style={{ width: 1, background: "var(--c-border)", margin: "4px 2px" }} />
              {SUB_INDICATORS.map(({ key, label }) => {
                const active = subEnabled.has(key);
                return (
                  <button key={key} onClick={() => setSubEnabled(prev => {
                    const next = new Set(prev);
                    next.has(key) ? next.delete(key) : next.add(key);
                    return next;
                  })} style={{
                    background: active ? "var(--c-bg-card)" : "transparent",
                    border: "none", borderRadius: 6, padding: "5px 10px", cursor: "pointer", height: 32,
                    color: active ? "#3d7eff" : "var(--c-text-dim)", fontSize: 17,
                    boxShadow: active ? "0 1px 2px rgba(0,0,0,0.15)" : "none",
                    transition: "all 0.15s ease",
                  }}>{label}</button>
                );
              })}
            </div>
          </div>

          <div style={{ height: 1, background: "var(--c-border)", margin: "4px 0 10px", opacity: 0.5 }} />

          {loading && <div style={{ color: "var(--c-text-dim)", fontSize: 18, marginBottom: 6 }}>載入K線...</div>}
          {bars.length > 0
            ? <CandleChart bars={bars} maEnabled={maEnabled} subEnabled={subEnabled} theme={theme} />
            : !loading && (
              <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--c-text-dim)", fontSize: 17 }}>
                無K線資料
              </div>
            )
          }
        </Card>
        </div>

        {/* 右側面板 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

          {/* AI Score 卡片 */}
          <div style={{
            background: "var(--c-bg-main)", border: `1px solid ${hasAi ? "#00c07633" : "var(--c-border)"}`, borderRadius: 8, padding: "14px 16px",
            display: "flex", flexDirection: "column", alignItems: "center",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: "var(--c-text-dim)", letterSpacing: 1, textTransform: "uppercase" }}>AI 綜合評分</div>
              <span style={{
                fontSize: 9, padding: "1px 5px", borderRadius: 3,
                background: hasAi ? "var(--c-bg-deep)" : "var(--c-border)",
                color: hasAi ? "#00c076" : "var(--c-text-dim)",
                border: `1px solid ${hasAi ? "#00c07644" : "var(--c-border)"}`,
              }}>{scoreSource}</span>
            </div>

            {/* 圓形評分 */}
            <div style={{
              width: 96, height: 96, borderRadius: "50%", position: "relative",
              background: hasData ? `conic-gradient(${scoreColor(composite)} 0% ${composite}%, var(--c-border) ${composite}% 100%)` : "var(--c-border)",
              boxShadow: hasData ? `0 0 22px ${scoreColor(composite)}44` : "none",
            }}>
              <div style={{
                position: "absolute", inset: 7, borderRadius: "50%", background: "var(--c-bg-main)",
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: hasData ? scoreColor(composite) : "var(--c-text-dim)", lineHeight: 1 }}>
                  {hasData ? composite : "--"}
                </div>
                <div style={{ fontSize: 10, color: "var(--c-text-dim)" }}>/ 100</div>
              </div>
            </div>

            {/* 操作建議標籤 */}
            <div style={{ margin: "8px 0 10px", display: "flex", gap: 6, alignItems: "center" }}>
              {hasAi ? (
                <span style={{
                  fontSize: 13, fontWeight: 800, padding: "3px 12px", borderRadius: 5,
                  background: { "買進":"var(--c-bg-deep)","強勢做多":"var(--c-bg-deep)","持有":"var(--c-bg-deep)","觀望":"var(--c-border)","減倉":"var(--c-bg-deep)","賣出":"var(--c-bg-deep)" }[aiResult.action] ?? "var(--c-border)",
                  color: { "買進":"#00c076","強勢做多":"#00ff88","持有":"#3d7eff","觀望":"var(--c-text-dim)","減倉":"#f5a623","賣出":"#ff4d4d" }[aiResult.action] ?? "var(--c-text-dim)",
                  border: `1px solid currentColor`,
                }}>
                  {aiResult.action}
                </span>
              ) : (
                <span style={{ fontSize: 12, fontWeight: 600, color: hasData ? scoreColor(composite) : "var(--c-text-dim)" }}>
                  {hasData ? scoreLabel(composite) : "載入中"}
                </span>
              )}
            </div>

            {/* 維度分數條 */}
            <div style={{ width: "100%" }}>
              {scoreDims.map(({ label, score, color }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14, color: "#666680", width: 32 }}>{label}</span>
                  <div style={{ flex: 1, height: 4, background: "var(--c-border)", borderRadius: 2 }}>
                    <div style={{
                      height: "100%", borderRadius: 2,
                      background: score !== null ? `linear-gradient(90deg, ${color}88, ${color})` : "var(--c-bg-deep)",
                      width: score !== null ? `${score}%` : "20%",
                      opacity: score !== null ? 1 : 0.3,
                      transition: "width 0.5s ease",
                    }} />
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: score !== null ? color : "var(--c-text-dim)", width: 24, textAlign: "right" }}>
                    {score !== null ? score : "--"}
                  </span>
                </div>
              ))}
            </div>

            {/* AI 進出場價位 */}
            {hasAi && (
              <div style={{ marginTop: 10, width: "100%", borderTop: "1px solid var(--c-border)", paddingTop: 10 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {[
                    { label: "理想進場", val: aiResult.ideal_entry, color: "#00c076" },
                    { label: "次佳進場", val: aiResult.alt_entry,   color: "#3d7eff" },
                    { label: "停損",     val: aiResult.stop_loss,   color: "#ff4d4d" },
                    { label: "目標價",   val: aiResult.take_profit, color: "#f5a623" },
                  ].map(({ label, val, color }) => (
                    <div key={label} style={{ background: "var(--c-bg-card)", borderRadius: 5, padding: "5px 8px" }}>
                      <div style={{ fontSize: 10, color: "var(--c-text-dim)" }}>{label}</div>
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
              <div style={{ marginTop: 10, width: "100%", borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", lineHeight: 1.7 }}>{aiResult.summary}</div>
              </div>
            )}

            {!hasAi && (
              <div style={{ marginTop: 8, fontSize: 10, color: "var(--c-border)", textAlign: "center" }}>
                設定 ANTHROPIC_API_KEY 啟用 Claude 深度分析
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── AI 深度分析 Tabs（橫向滿版）── */}
          <div style={{ background: "var(--c-bg-main)", border: "1px solid var(--c-border)", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }}>
            {/* Tab 列 */}
            <div style={{ display: "flex", borderBottom: "1px solid var(--c-border)" }}>
              {([
                { key: "uzi" as AiTab,   label: "UZI 評審",   icon: "🧑‍⚖️" },
                { key: "ic"  as AiTab,   label: "IC 備忘錄",  icon: "📋" },
                { key: "debate" as AiTab, label: "多空辯論",   icon: "⚔️" },
              ] as { key: AiTab; label: string; icon: string }[]).map(({ key, label, icon }) => {
                const active = activeAiTab === key;
                return (
                  <button key={key} onClick={() => {
                    setActiveAiTab(key);
                    if (key === "uzi") fetchUzi();
                    if (key === "ic") fetchIcMemo();
                    if (key === "debate") fetchDebate();
                  }} style={{
                    flex: 1, padding: "12px 4px", border: "none", cursor: "pointer", fontSize: 16,
                    background: active ? "linear-gradient(180deg, #3d7eff22 0%, #3d7eff11 100%)" : "transparent",
                    color: active ? "#3d7eff" : "var(--c-text-dim)",
                    borderBottom: active ? "2px solid #3d7eff" : "2px solid transparent",
                    fontWeight: active ? 700 : 400, transition: "all 0.15s ease",
                    textShadow: active ? "0 0 8px #3d7eff33" : "none",
                  }}>
                    {icon} {label}
                  </button>
                );
              })}
            </div>

            {/* Tab 內容 */}
            <div style={{ padding: 12 }}>
              {activeAiTab === null && (
                <div style={{ fontSize: 15, color: "var(--c-text-dim)", textAlign: "center", padding: "16px 0" }}>
                  點擊上方 Tab 展開 AI 深度分析
                </div>
              )}

              {/* UZI 評審 */}
              {activeAiTab === "uzi" && (
                <div>
                  {uziLoading && <div style={{ fontSize: 13, color: "var(--c-text-dim)", textAlign: "center", padding: "20px 0" }}>🤖 Claude 評審中...</div>}
                  {uziError && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 12, color: "#ff4d4d", marginBottom: 8 }}>{uziError}</div>
                      <button onClick={() => { setUziData(null); setUziError(""); fetchUzi(); }} style={{ fontSize: 12, padding: "4px 12px", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 4, color: "var(--c-text)", cursor: "pointer", transition: "all 0.15s ease" }}>重試</button>
                    </div>
                  )}
                  {uziData && (
                    <>
                      <div style={{ textAlign: "center", marginBottom: 12 }}>
                        <div style={{ fontSize: 14, color: "var(--c-text-dim)" }}>加權總分</div>
                        <div style={{ fontSize: 36, fontWeight: 700, color: scoreColor(uziData.weighted_score) }}>{uziData.weighted_score}</div>
                        <div style={{ fontSize: 15, color: "var(--c-text-dim)" }}>{uziData.consensus}</div>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3, 1fr)", gap: 8 }}>
                        {uziData.reviewers?.map((r, i) => (
                          <div key={i} style={{ padding: "10px 12px", background: "var(--c-bg-deep)", borderRadius: 6, borderLeft: `3px solid ${r.score >= 70 ? "#00c076" : r.score >= 40 ? "#f5a623" : "#ff4d4d"}` }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                              <span style={{ fontSize: 15, fontWeight: 700 }}>{r.name}</span>
                              <span style={{ fontSize: 15, color: r.score >= 70 ? "#00c076" : r.score >= 40 ? "#f5a623" : "#ff4d4d", fontWeight: 700 }}>{r.score} / {r.verdict}</span>
                            </div>
                            <div style={{ fontSize: 14, color: "var(--c-text-dim)", lineHeight: 1.6 }}>{r.reasoning}</div>
                          </div>
                        ))}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--c-border)", marginTop: 8 }}>動能 35% / 價值 35% / 風控 30%</div>
                    </>
                  )}
                </div>
              )}

              {/* IC 備忘錄 */}
              {activeAiTab === "ic" && (
                <div>
                  {icLoading && <div style={{ fontSize: 13, color: "var(--c-text-dim)", textAlign: "center", padding: "20px 0" }}>🤖 生成 IC 備忘錄中...</div>}
                  {icError && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 12, color: "#ff4d4d", marginBottom: 8 }}>{icError}</div>
                      <button onClick={() => { setIcData(null); setIcError(""); fetchIcMemo(); }} style={{ fontSize: 12, padding: "4px 12px", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 4, color: "var(--c-text)", cursor: "pointer", transition: "all 0.15s ease" }}>重試</button>
                    </div>
                  )}
                  {icData && (
                    <>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--c-text-dim)", marginBottom: 8 }}>
                        <span>來源：{icData.source ?? "generated"}</span>
                        {icData.current_price && <span>現價：{icData.current_price}</span>}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3, 1fr)", gap: 8 }}>
                      {([
                        { key: "bull" as const, label: "🟢 看多情境", color: "#00c076", bg: "#00c07611" },
                        { key: "base" as const, label: "⬜ 基準情境", color: "var(--c-text-dim)", bg: "var(--c-bg-deep)" },
                        { key: "bear" as const, label: "🔴 看空情境", color: "#ff4d4d", bg: "#ff4d4d11" },
                      ] as { key: "bull" | "base" | "bear"; label: string; color: string; bg: string }[]).map(({ key, label, color, bg }) => {
                        const s = icData.scenarios?.[key];
                        if (!s) return null;
                        return (
                          <div key={key} style={{ padding: "10px 12px", background: bg, border: `1px solid ${color}44`, borderRadius: 6 }}>
                            <div style={{ fontSize: 15, fontWeight: 700, color, marginBottom: 6 }}>
                              {label} <span style={{ fontSize: 13, fontWeight: 400, color: "var(--c-text-dim)" }}>({Math.round(s.probability * 100)}%)</span>
                              <span style={{ float: "right", fontSize: 14 }}>目標 <b style={{ color }}>{s.target_price?.toLocaleString() ?? "—"}</b></span>
                            </div>
                            {s.key_assumptions?.map((a, i) => (
                              <div key={i} style={{ fontSize: 14, color: "var(--c-text-dim)", lineHeight: 1.6 }}>• {a}</div>
                            ))}
                          </div>
                        );
                      })}
                      </div>
                      <div style={{ fontSize: 14, color: "var(--c-text-dim)", marginTop: 8 }}>
                        期望值：<b>{icData.expected_value?.toLocaleString()}</b>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* 多空辯論 */}
              {activeAiTab === "debate" && (
                <div>
                  {debateLoading && (
                    <div style={{ textAlign: "center", padding: "20px 0" }}>
                      <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginBottom: 6 }}>🤖 多空辯論進行中...</div>
                      {debateSlow && <div style={{ fontSize: 11, color: "#f5a623" }}>AI 深度分析中，請稍候（可能需要 30-60 秒）</div>}
                    </div>
                  )}
                  {debateError && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 12, color: "#ff4d4d", marginBottom: 8 }}>{debateError}</div>
                      <button onClick={() => { setDebateData(null); setDebateError(""); fetchDebate(); }} style={{ fontSize: 12, padding: "4px 12px", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 4, color: "var(--c-text)", cursor: "pointer", transition: "all 0.15s ease" }}>重試</button>
                    </div>
                  )}
                  {debateData && (
                    <>
                      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, 1fr)", gap: 8 }}>
                      {([
                        { args: debateData.bull_arguments, label: "📈 多方論點", color: "#00c076", bg: "#00c07611" },
                        { args: debateData.bear_arguments, label: "📉 空方論點", color: "#ff4d4d", bg: "#ff4d4d11" },
                      ] as { args: DebateArgument[]; label: string; color: string; bg: string }[]).map(({ args, label, color, bg }) => (
                        <div key={label} style={{ padding: "10px 12px", background: bg, border: `1px solid ${color}44`, borderRadius: 6 }}>
                          <div style={{ fontSize: 15, fontWeight: 700, color, marginBottom: 8 }}>{label}</div>
                          {args?.map((a, i) => (
                            <div key={i} style={{ marginBottom: 8 }}>
                              <div style={{ fontSize: 14, fontWeight: 600, color }}>{a.title}</div>
                              <div style={{ fontSize: 14, color: "var(--c-text-dim)", lineHeight: 1.6 }}>{a.argument}</div>
                              {a.evidence && <div style={{ fontSize: 12, color: "var(--c-border)", marginTop: 3 }}>根據：{a.evidence}</div>}
                            </div>
                          ))}
                        </div>
                      ))}
                      </div>
                      <div style={{ marginTop: 8, padding: "10px 14px", background: "#3d7eff11", borderRadius: 6, border: "1px solid #3d7eff44" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                          <span style={{ fontSize: 15, fontWeight: 700, color: "#3d7eff" }}>⚖️ 仲裁結論</span>
                          <span style={{ fontSize: 14, color: "var(--c-text-dim)" }}>信心 {debateData.arbiter.confidence}%</span>
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
                          裁決：{debateData.arbiter.verdict === "bull" ? "看多" : debateData.arbiter.verdict === "bear" ? "看空" : "中性"}
                        </div>
                        <div style={{ fontSize: 14, color: "var(--c-text-dim)", lineHeight: 1.6 }}>{debateData.arbiter.rationale}</div>
                        {debateData.arbiter.key_risk && (
                          <div style={{ fontSize: 13, color: "#f5a623", marginTop: 6 }}>⚠️ 主要風險：{debateData.arbiter.key_risk}</div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

      {/* ── 資訊面板（2 欄 grid）── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
        gap: 10, width: "100%",
      }}>

          {/* 論壇情緒 */}
          {sentiment && (sentiment.ptt || sentiment.cmoney) && (
            <div>
            <Card title="論壇情緒（散戶觀點）">
              {[
                { key: "ptt", label: "PTT Stock 板", data: sentiment.ptt },
                { key: "cmoney", label: "CMoney 討論區", data: sentiment.cmoney },
              ].map(({ key, label, data }) =>
                data ? (
                  <div key={key} style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 6 }}>{label}</div>
                    {[
                      { name: "看漲", count: data.bullish_count, color: "#ff4d4d" },
                      { name: "看跌", count: data.bearish_count, color: "#00c076" },
                      { name: "中性", count: data.neutral_count, color: "var(--c-text-dim)" },
                    ].map(bar => (
                      <div key={bar.name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: "var(--c-text-dim)", width: 28 }}>{bar.name}</span>
                        <div style={{ flex: 1, height: 6, background: "var(--c-border)", borderRadius: 3 }}>
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
                    <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginTop: 4 }}>
                      共 {data.total_posts} 篇討論・情緒：
                      <span style={{ color: data.sentiment_score > 0.1 ? "#ff4d4d" : data.sentiment_score < -0.1 ? "#00c076" : "var(--c-text-dim)", fontWeight: 700 }}>
                        {data.label}
                      </span>
                    </div>
                  </div>
                ) : null
              )}
              <div style={{ fontSize: 10, color: "var(--c-border)", marginTop: 4 }}>關鍵字規則法・30分鐘更新</div>
            </Card>
            </div>
          )}

          {/* 技術指標 */}
          <div>
          <Card title="技術指標">
            {ind ? (
              <>
                <MetricRow label="收盤價" value={`$${ind.close.toLocaleString()}`} />
                <MetricRow
                  label="RSI (14)" sub={rsiLabel(ind.rsi14)}
                  value={ind.rsi14.toFixed(1)} color={rsiColor(ind.rsi14)}
                />
                <div style={{ margin: "3px 0 7px", height: 3, background: "var(--c-border)", borderRadius: 2 }}>
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
                  color={ind.k >= 80 ? "#ff4d4d" : ind.k <= 20 ? "#00c076" : "var(--c-text)"} />
                <MetricRow label="D" value={ind.d.toFixed(1)} color="var(--c-text-dim)" />
                <MetricRow label="ATR (14)" sub="日均波幅" value={ind.atr14.toFixed(1)} color="var(--c-text-dim)" />
                {ind.ma20 != null && (
                  <MetricRow label="MA20" sub="20日均線" value={`$${ind.ma20.toLocaleString()}`} color="#3d7eff" />
                )}
                {ind.ma20_bias != null && (() => {
                  const bias = ind.ma20_bias!;
                  const pct  = ind.bias_pct ?? 50;
                  const biasColor = bias > 10 ? "#ff4d4d" : bias < -5 ? "#00c076" : "#f5a623";
                  const pctLabel  = pct >= 85 ? "過熱" : pct >= 70 ? "偏高" : pct <= 15 ? "過冷" : pct <= 30 ? "偏低" : "中性";
                  const pctColor  = pct >= 85 ? "#ff4d4d" : pct >= 70 ? "#f5a623" : pct <= 15 ? "#00c076" : pct <= 30 ? "#4dd0e1" : "var(--c-text-dim)";
                  return (
                    <>
                      <MetricRow
                        label="MA20 乖離率"
                        sub={`偏離均線`}
                        value={(bias >= 0 ? "+" : "") + bias.toFixed(2) + "%"}
                        color={biasColor}
                      />
                      <div style={{ margin: "2px 0 8px", display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ flex: 1, height: 3, background: "var(--c-border)", borderRadius: 2, position: "relative" }}>
                          <div style={{ position: "absolute", left: 0, top: 0, height: "100%", borderRadius: 2, background: pctColor, width: `${pct}%`, transition: "width 0.4s" }} />
                          <div style={{ position: "absolute", left: "50%", top: -1, width: 1, height: 5, background: "var(--c-border)" }} />
                        </div>
                        <span style={{ fontSize: 11, color: pctColor, whiteSpace: "nowrap" }}>
                          {pct.toFixed(0)}百分位 · {pctLabel}
                        </span>
                      </div>
                    </>
                  );
                })()}
                {/* K 線形態 */}
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--c-border)" }}>
                  <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 6 }}>K 線形態</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                    {ind.patterns && ind.patterns.length > 0 ? ind.patterns.map((p, i) => (
                      <span key={i} style={{
                        fontSize: 11, padding: "2px 7px", borderRadius: 4,
                        background: "var(--c-bg-deep)", border: "1px solid #3d7eff55",
                        color: "#3d7eff", fontWeight: 600,
                      }}>{p}</span>
                    )) : (
                      <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>無明顯形態</span>
                    )}
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 18, color: "var(--c-border)" }}>
                  資料日期：{ind.trade_date}｜每日15:05更新
                </div>
              </>
            ) : (
              <div style={{ color: "var(--c-text-dim)", fontSize: 18, padding: "8px 0" }}>
                {indErr || "載入中..."}
              </div>
            )}
          </Card>
          </div>


          {/* 主力意圖卡片 */}
          {ind?.market_maker_intent && (
            <div>
            <Card title="主力意圖">
              {(() => {
                const mmi = ind.market_maker_intent!;
                const phaseColor: Record<string, string> = {
                  "吸籌": "#00c076", "拉抬": "#ff4d4d", "出貨": "#f5a623",
                  "打壓": "#3d7eff", "觀望": "var(--c-text-dim)",
                };
                const color = phaseColor[mmi.phase] ?? "var(--c-text-dim)";
                const confPct = Math.round(mmi.confidence * 100);
                return (
                  <>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span style={{
                        fontSize: 15, fontWeight: 800, padding: "3px 12px", borderRadius: 5,
                        background: "var(--c-bg-deep)", border: `1px solid ${color}66`, color,
                      }}>{mmi.phase}</span>
                      <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>信心度 {confPct}%</span>
                    </div>
                    <div style={{ height: 4, background: "var(--c-border)", borderRadius: 2, marginBottom: 8 }}>
                      <div style={{ height: "100%", borderRadius: 2, background: color, width: `${confPct}%`, transition: "width 0.4s" }} />
                    </div>
                    {mmi.signals.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {mmi.signals.map((s, i) => (
                          <div key={i} style={{ fontSize: 11, color: "var(--c-text-dim)" }}>• {s}</div>
                        ))}
                      </div>
                    )}
                  </>
                );
              })()}
            </Card>
            </div>
          )}
          {/* 籌碼面板 */}
          <div>
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
                  <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 6 }}>三大法人（{latest.date}）</div>
                  {instRows.map(r => (
                    <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--c-border)" }}>
                      <span style={{ fontSize: 13, color: "var(--c-text-dim)" }}>{r.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: r.color }}>{fmt(r.value)}</span>
                    </div>
                  ))}

                  <div style={{ fontSize: 11, color: "var(--c-text-dim)", margin: "10px 0 6px" }}>融資融券（{margin.date}）</div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--c-border)" }}>
                    <span style={{ fontSize: 13, color: "var(--c-text-dim)" }}>融資餘額</span>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "var(--c-text)" }}>{margin.margin_balance.toLocaleString()} 張</span>
                      <span style={{ fontSize: 11, color: margin.margin_change >= 0 ? "#ff4d4d" : "#00c076", marginLeft: 6 }}>
                        {margin.margin_change >= 0 ? "▲" : "▼"}{Math.abs(margin.margin_change)}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--c-border)" }}>
                    <span style={{ fontSize: 13, color: "var(--c-text-dim)" }}>融券餘額</span>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "var(--c-text)" }}>{margin.short_balance.toLocaleString()} 張</span>
                      <span style={{ fontSize: 11, color: margin.short_change >= 0 ? "#ff4d4d" : "#00c076", marginLeft: 6 }}>
                        {margin.short_change >= 0 ? "▲" : "▼"}{Math.abs(margin.short_change)}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                    <span style={{ fontSize: 13, color: "var(--c-text-dim)" }}>券資比</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: margin.short_ratio > 15 ? "#ff4d4d" : "var(--c-text-dim)" }}>
                      {margin.short_ratio.toFixed(1)}%
                    </span>
                  </div>
                </>
              );
            })() : (
              <div style={{ color: "var(--c-text-dim)", fontSize: 13, padding: "8px 0" }}>載入中...</div>
            )}
          </Card>
          </div>

      </div>
      {/* ── AI 深度分析（評審團 + IC備忘錄）── */}
      {hasAi && (
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 10 }}>

          {/* 評審團 */}
          <Card title={`AI 評審團（${aiResult.panel_summary?.bullish ?? 0}多 ${aiResult.panel_summary?.neutral ?? 0}中 ${aiResult.panel_summary?.bearish ?? 0}空）`}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {(aiResult.panel ?? []).map(p => {
                const vc = p.verdict === "看多" ? "#ff4d4d" : p.verdict === "看空" ? "#00c076" : "var(--c-text-dim)";
                // LLM 產出的欄位不保證齊全（實測缺過 misses），一律給預設空陣列
                const hits = p.hits ?? [];
                const misses = p.misses ?? [];
                return (
                  <div key={p.name} style={{ background: "var(--c-bg-main)", borderRadius: 6, padding: "8px 10px", border: `1px solid ${vc}22` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "var(--c-text-mid)" }}>{p.name}</span>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: vc, padding: "1px 6px", border: `1px solid ${vc}44`, borderRadius: 3 }}>{p.verdict}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(p.score) }}>{p.score}</span>
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--c-text-dim)", lineHeight: 1.5 }}>{p.comment}</div>
                    {hits.length > 0 && (
                      <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {hits.map((h, i) => <span key={i} style={{ fontSize: 10, color: "#ff4d4d", background: "#3d000022", padding: "1px 5px", borderRadius: 3 }}>✓ {h}</span>)}
                      </div>
                    )}
                    {misses.length > 0 && (
                      <div style={{ marginTop: 3, display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {misses.map((m, i) => <span key={i} style={{ fontSize: 10, color: "var(--c-text-dim)", background: "var(--c-border)", padding: "1px 5px", borderRadius: 3 }}>✗ {m}</span>)}
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
                      <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>機率 {s.prob}% ｜ 目標 <span style={{ color, fontWeight: 700 }}>{s.target}</span></span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--c-text-dim)", lineHeight: 1.5 }}>{s.assumption}</div>
                    {"trigger" in s && s.trigger && (
                      <div style={{ fontSize: 10, color: "var(--c-text-dim)", marginTop: 2 }}>觸發：{s.trigger}</div>
                    )}
                  </div>
                );
              })}
              <div style={{ borderTop: "1px solid var(--c-border)", paddingTop: 8, display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>期望值 <span style={{ color: "#f5a623", fontWeight: 700 }}>{aiResult.ic_memo.expected_value}</span></span>
                <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>風報比 <span style={{ color: "#3d7eff", fontWeight: 700 }}>{aiResult.ic_memo.risk_reward?.toFixed(2)}</span></span>
              </div>
            </Card>

            {aiResult.debate && (
              <Card title="多空辯論">
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#ff4d4d", fontWeight: 700, marginBottom: 4 }}>看多論點</div>
                  {aiResult.debate.bull_points.map((p, i) => <div key={i} style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 3 }}>▲ {p}</div>)}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#00c076", fontWeight: 700, marginBottom: 4 }}>看空論點</div>
                  {aiResult.debate.bear_points.map((p, i) => <div key={i} style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 3 }}>▼ {p}</div>)}
                </div>
                <div style={{ borderTop: "1px solid var(--c-border)", paddingTop: 8, fontSize: 11, color: "var(--c-text-mid)" }}>⚖️ {aiResult.debate.verdict}</div>
              </Card>
            )}

            <Card title="主要風險">
              {aiResult.key_risks.map((r, i) => (
                <div key={i} style={{ fontSize: 12, color: "var(--c-text-dim)", padding: "5px 0", borderBottom: "1px solid var(--c-border)" }}>
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
              background: "var(--c-bg-main)", border: "1px solid var(--c-border)", borderRadius: 6,
              padding: "8px 14px", cursor: "pointer", textAlign: "left", transition: "all 0.15s ease",
            }}>
              <div style={{ fontSize: 17, color: "#3d7eff", fontWeight: 600 }}>{p.code}</div>
              <div style={{ fontSize: 17, color: "var(--c-text-dim)" }}>{p.name}</div>
            </button>
          ))}
        </div>
      </Card>
      {showAtrModal && <AtrStopModal symbol={symbol} onClose={() => setShowAtrModal(false)} />}
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
