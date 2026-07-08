"use client";
import { useState, useMemo, useEffect } from "react";

const API = "";

// ── OHLCV 型別 ────────────────────────────────────────────────────
interface Bar { time: string; open: number; high: number; low: number; close: number; volume: number; }

// ── 回測結果型別 ──────────────────────────────────────────────────
interface Trade {
  symbol: string;
  side: 1 | -1;            // 1=多 -1=空
  entry_date: string; entry_price: number;
  exit_date:  string; exit_price:  number;
  pnl_pct: number; pnl_abs: number;
  exit_reason: string;
}

type Direction = "long" | "short" | "both";
type StrategyId = "ma_cross" | "rsi" | "wave" | "momentum";

// 風險控制參數（0 = 停用該規則）
interface RiskParams {
  stopLoss:   number;  // 停損 %
  takeProfit: number;  // 停利 %
  maxHold:    number;  // 最長持有天數（bar 數）
  withCost:   boolean; // 計入手續費 0.1425% + 證交稅 0.3%
}

const FEE_RATE = 0.001425;
const TAX_RATE = 0.003;
interface PerSymbolStat {
  symbol: string; pnl_abs: number; num_trades: number; win_rate: number;
}

interface BacktestResult {
  trades:        Trade[];
  equity:        { date: string; value: number }[];
  total_return:  number;
  win_rate:      number;
  max_drawdown:  number;
  num_trades:    number;
  avg_hold_days: number;
  annualized:    number | null;  // 年化報酬 %
  sharpe:        number | null;  // 夏普比率（日報酬 × √252）
  profit_factor: number | null;  // 獲利因子（毛利/毛損）
  per_symbol:    PerSymbolStat[];
}

// ── 指標計算 ──────────────────────────────────────────────────────
function sma(closes: number[], n: number): (number | null)[] {
  return closes.map((_, i) =>
    i < n - 1 ? null : closes.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n
  );
}

function rsi(closes: number[], period = 14): (number | null)[] {
  const result: (number | null)[] = Array(closes.length).fill(null);
  if (closes.length < period + 1) return result;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) gains += d; else losses -= d;
  }
  let avgG = gains / period, avgL = losses / period;
  result[period] = avgL === 0 ? 100 : 100 - 100 / (1 + avgG / avgL);
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    avgG = (avgG * (period - 1) + Math.max(d, 0)) / period;
    avgL = (avgL * (period - 1) + Math.max(-d, 0)) / period;
    result[i] = avgL === 0 ? 100 : 100 - 100 / (1 + avgG / avgL);
  }
  return result;
}

// ── 指標：EMA / MACD 柱 ───────────────────────────────────────────
function ema(closes: number[], n: number): number[] {
  const k = 2 / (n + 1);
  const out: number[] = [];
  for (let i = 0; i < closes.length; i++) out.push(i === 0 ? closes[0] : closes[i] * k + out[i - 1] * (1 - k));
  return out;
}

function macdHist(closes: number[]): number[] {
  const fast = ema(closes, 12), slow = ema(closes, 26);
  const diff = closes.map((_, i) => fast[i] - slow[i]);
  const signal = ema(diff, 9);
  return diff.map((d, i) => d - signal[i]);
}

// ── 訊號產生器（四策略）──────────────────────────────────────────
function buildSignals(bars: Bar[], strategy: StrategyId, params: Record<string, number>): ("buy" | "sell" | null)[] {
  const closes = bars.map((b) => b.close);
  const signals: ("buy" | "sell" | null)[] = Array(bars.length).fill(null);

  if (strategy === "ma_cross") {
    const short = sma(closes, params.short_period);
    const long_  = sma(closes, params.long_period);
    for (let i = 1; i < bars.length; i++) {
      if (short[i] === null || long_[i] === null) continue;
      const prevDiff = (short[i - 1] ?? 0) - (long_[i - 1] ?? 0);
      const currDiff = short[i]! - long_[i]!;
      if (prevDiff <= 0 && currDiff > 0) signals[i] = "buy";
      if (prevDiff >= 0 && currDiff < 0) signals[i] = "sell";
    }
  } else if (strategy === "rsi") {
    const r = rsi(closes, params.rsi_period);
    for (let i = 1; i < bars.length; i++) {
      if (r[i] === null) continue;
      const prev = r[i - 1];
      const curr = r[i]!;
      if (prev !== null && prev <= params.oversold  && curr > params.oversold)  signals[i] = "buy";
      if (prev !== null && prev >= params.overbought && curr < params.overbought) signals[i] = "sell";
    }
  } else if (strategy === "wave") {
    // 波段：MACD 柱翻正（金叉）+ RSI < 上限 + 站上 MA → 買；MACD 柱翻負或跌破 MA → 賣
    const hist = macdHist(closes);
    const r = rsi(closes, 14);
    const ma = sma(closes, params.wave_ma);
    for (let i = 1; i < bars.length; i++) {
      if (ma[i] === null) continue;
      const goldenCross = hist[i - 1] <= 0 && hist[i] > 0;
      const deadCross   = hist[i - 1] >= 0 && hist[i] < 0;
      if (goldenCross && (r[i] ?? 100) < params.wave_rsi_max && closes[i] > ma[i]!) signals[i] = "buy";
      else if (deadCross || closes[i] < ma[i]!) signals[i] = "sell";
    }
  } else {
    // 趨勢：創 N 日新高 + 連 M 日收紅 → 買；跌破出場 MA → 賣
    const exitMa = sma(closes, params.momo_exit_ma);
    for (let i = 1; i < bars.length; i++) {
      const look = params.momo_lookback;
      if (i >= look) {
        const isHigh = closes[i] >= Math.max(...closes.slice(i - look + 1, i + 1));
        let reds = 0;
        for (let j = i; j > i - params.momo_red_days && j >= 0; j--) {
          if (bars[j].close > bars[j].open) reds++;
        }
        if (isHigh && reds >= params.momo_red_days) signals[i] = "buy";
      }
      if (exitMa[i] !== null && closes[i] < exitMa[i]!) signals[i] = signals[i] ?? "sell";
    }
  }
  return signals;
}

// ── 單一股票回測（支援多/空）──────────────────────────────────────
// 空單以 100% 保證金模擬：開空占用 notional 的現金，平倉取回保證金 ± 損益
function runSingle(
  symbol: string,
  bars: Bar[],
  strategy: StrategyId,
  params: Record<string, number>,
  capital: number,
  risk: RiskParams,
  direction: Direction
): { trades: Trade[]; equity: { date: string; value: number }[] } {
  const signals = buildSignals(bars, strategy, params);

  const trades: Trade[] = [];
  const equity: { date: string; value: number }[] = [];
  let cash = capital;
  let side: 1 | -1 | 0 = 0, qty = 0, entryPrice = 0, entryDate = "";
  let entryIdx = -1, margin = 0, entryFees = 0;

  const openPos = (s: 1 | -1, bar: Bar, i: number) => {
    qty = Math.floor(cash / bar.close / 1000) * 1000; // 整張
    if (qty === 0) qty = Math.floor(cash / bar.close);
    if (qty <= 0) { qty = 0; return; }
    const notional = qty * bar.close;
    // 多單手續費在買進腿；空單開倉是賣出腿（手續費+證交稅）
    entryFees = risk.withCost ? notional * (s === 1 ? FEE_RATE : FEE_RATE + TAX_RATE) : 0;
    margin = notional;
    cash -= notional + entryFees;
    side = s; entryPrice = bar.close; entryDate = bar.time; entryIdx = i;
  };

  const closePos = (bar: Bar, reason: string) => {
    const exitNotional = qty * bar.close;
    // 多單平倉是賣出腿（手續費+證交稅）；空單回補是買進腿（手續費）
    const exitFees = risk.withCost ? exitNotional * (side === 1 ? FEE_RATE + TAX_RATE : FEE_RATE) : 0;
    const pnlGross = side === 1 ? (bar.close - entryPrice) * qty : (entryPrice - bar.close) * qty;
    const pnl_abs = pnlGross - entryFees - exitFees;
    cash += margin + pnlGross - exitFees;
    trades.push({
      symbol, side: side as 1 | -1,
      entry_date: entryDate, entry_price: entryPrice,
      exit_date: bar.time, exit_price: bar.close,
      pnl_pct: pnl_abs / (margin + entryFees) * 100, pnl_abs,
      exit_reason: reason,
    });
    side = 0; qty = 0; margin = 0; entryFees = 0;
  };

  for (let i = 0; i < bars.length; i++) {
    const bar = bars[i];
    const sig = signals[i];

    if (side === 0) {
      // 空手進場：做多看 buy；做空看 sell；雙向兩者皆可
      if (sig === "buy" && (direction === "long" || direction === "both")) openPos(1, bar, i);
      else if (sig === "sell" && (direction === "short" || direction === "both")) openPos(-1, bar, i);
    } else {
      // 出場判斷（優先序：停損 > 停利 > 反向訊號 > 逾時 > 期末）；chgPct 依方向折算
      const chgPct = (side === 1 ? bar.close - entryPrice : entryPrice - bar.close) / entryPrice * 100;
      const oppositeSig = (side === 1 && sig === "sell") || (side === -1 && sig === "buy");
      let reason: string | null = null;
      if (risk.stopLoss > 0 && chgPct <= -risk.stopLoss)          reason = "停損";
      else if (risk.takeProfit > 0 && chgPct >= risk.takeProfit)  reason = "停利";
      else if (oppositeSig)                                       reason = "訊號";
      else if (risk.maxHold > 0 && i - entryIdx >= risk.maxHold)  reason = "逾時";
      else if (i === bars.length - 1)                             reason = "期末";

      if (reason) {
        const prevSide = side;
        closePos(bar, reason);
        // 雙向模式：反向訊號出場後同根 K 直接翻單
        if (reason === "訊號" && direction === "both" && i < bars.length - 1) {
          openPos(prevSide === 1 ? -1 : 1, bar, i);
        }
      }
    }

    const posValue = side === 0 ? 0
      : side === 1 ? qty * bars[i].close
      : margin + (entryPrice - bars[i].close) * qty;
    equity.push({ date: bar.time, value: cash + posValue });
  }

  return { trades, equity };
}

// ── 組合回測：多股票均分資金、合併淨值與統計 ──────────────────────
function runPortfolio(
  data: { symbol: string; bars: Bar[] }[],
  strategy: StrategyId,
  params: Record<string, number>,
  capital: number,
  risk: RiskParams,
  direction: Direction
): BacktestResult {
  const per = capital / data.length;
  const singles = data.map((d) => ({ symbol: d.symbol, ...runSingle(d.symbol, d.bars, strategy, params, per, risk, direction) }));

  // 合併淨值：日期取聯集，缺值 forward-fill（首日前用起始資金）
  const allDates = [...new Set(singles.flatMap((s) => s.equity.map((e) => e.date)))].sort();
  const maps = singles.map((s) => new Map(s.equity.map((e) => [e.date, e.value])));
  const lastVals = singles.map(() => per);
  const equity = allDates.map((date) => {
    let total = 0;
    maps.forEach((m, i) => {
      const v = m.get(date);
      if (v !== undefined) lastVals[i] = v;
      total += lastVals[i];
    });
    return { date, value: total };
  });

  const trades = singles.flatMap((s) => s.trades).sort((a, b) => a.entry_date.localeCompare(b.entry_date));

  const finalVal = equity[equity.length - 1]?.value ?? capital;
  const total_return = (finalVal - capital) / capital * 100;
  const win_rate = trades.length ? trades.filter((t) => t.pnl_pct > 0).length / trades.length * 100 : 0;
  const avg_hold_days = trades.length
    ? trades.reduce((s, t) => s + (new Date(t.exit_date).getTime() - new Date(t.entry_date).getTime()) / 86400000, 0) / trades.length
    : 0;

  let peak = equity[0]?.value ?? capital, max_drawdown = 0;
  for (const e of equity) {
    if (e.value > peak) peak = e.value;
    const dd = (peak - e.value) / peak * 100;
    if (dd > max_drawdown) max_drawdown = dd;
  }

  // 年化報酬
  let annualized: number | null = null;
  if (equity.length > 1 && finalVal > 0) {
    const days = (new Date(equity[equity.length - 1].date).getTime() - new Date(equity[0].date).getTime()) / 86400000;
    if (days >= 30) annualized = (Math.pow(finalVal / capital, 365 / days) - 1) * 100;
  }

  // 夏普比率（日報酬 × √252，無風險利率取 0）
  let sharpe: number | null = null;
  if (equity.length > 2) {
    const rets: number[] = [];
    for (let i = 1; i < equity.length; i++) {
      if (equity[i - 1].value > 0) rets.push(equity[i].value / equity[i - 1].value - 1);
    }
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length);
    if (sd > 0) sharpe = (mean / sd) * Math.sqrt(252);
  }

  // 獲利因子
  const grossProfit = trades.filter((t) => t.pnl_abs > 0).reduce((a, t) => a + t.pnl_abs, 0);
  const grossLoss = -trades.filter((t) => t.pnl_abs < 0).reduce((a, t) => a + t.pnl_abs, 0);
  const profit_factor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : null);

  const per_symbol: PerSymbolStat[] = singles.map((s) => ({
    symbol: s.symbol,
    pnl_abs: s.trades.reduce((a, t) => a + t.pnl_abs, 0),
    num_trades: s.trades.length,
    win_rate: s.trades.length ? s.trades.filter((t) => t.pnl_pct > 0).length / s.trades.length * 100 : 0,
  }));

  return { trades, equity, total_return, win_rate, max_drawdown, num_trades: trades.length, avg_hold_days, annualized, sharpe, profit_factor, per_symbol };
}

// ── SVG 淨值曲線 ──────────────────────────────────────────────────
function EquityChart({ equity, capital }: { equity: { date: string; value: number }[]; capital: number }) {
  const W = 700, H = 180, PAD = 8;
  if (!equity.length) return null;
  const vals = equity.map((e) => e.value);
  const minV = Math.min(...vals) * 0.998;
  const maxV = Math.max(...vals) * 1.002;
  const toX = (i: number) => PAD + (i / (equity.length - 1)) * (W - PAD * 2);
  const toY = (v: number) => PAD + (1 - (v - minV) / (maxV - minV)) * (H - PAD * 2);
  const path = equity.map((e, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(e.value).toFixed(1)}`).join(" ");
  const finalUp = vals[vals.length - 1] >= capital;
  const color = finalUp ? "#ff4d4d" : "#00c076";
  // baseline (capital)
  const baseY = toY(capital);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H, display: "block" }}>
      {/* grid lines */}
      {[0.25, 0.5, 0.75].map((t) => (
        <line key={t} x1={PAD} x2={W - PAD} y1={PAD + t * (H - PAD * 2)} y2={PAD + t * (H - PAD * 2)}
          stroke="#1a1a2a" strokeWidth="1" />
      ))}
      {/* capital baseline */}
      {baseY >= PAD && baseY <= H - PAD && (
        <line x1={PAD} x2={W - PAD} y1={baseY} y2={baseY} stroke="var(--c-text-dim)" strokeWidth="1" strokeDasharray="4 3" />
      )}
      {/* area fill */}
      <path
        d={`${path} L${toX(equity.length - 1).toFixed(1)},${H - PAD} L${PAD},${H - PAD} Z`}
        fill={color} fillOpacity="0.08"
      />
      {/* line */}
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

// ── 統計格子 ──────────────────────────────────────────────────────
function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "var(--c-bg-main)", border: "1px solid var(--c-border)", borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "var(--c-text)" }}>{value}</div>
    </div>
  );
}

// ── 主頁面 ────────────────────────────────────────────────────────
function useIsMobile() {
  const [m, setM] = useState(false);
  useEffect(() => {
    const check = () => setM(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return m;
}

export default function BacktestPage() {
  const isMobile = useIsMobile();
  const [symbol,   setSymbol]   = useState("2330");   // 可逗號分隔多檔
  const [period,   setPeriod]   = useState("1y");
  const [strategy, setStrategy] = useState<StrategyId>("ma_cross");
  const [direction,setDirection]= useState<Direction>("long");
  const [shortP,   setShortP]   = useState(10);
  const [longP,    setLongP]    = useState(30);
  const [rsiPeriod,setRsiPeriod]= useState(14);
  const [oversold, setOversold] = useState(30);
  const [overbought,setOverbought]=useState(70);
  const [waveRsiMax, setWaveRsiMax] = useState(70);
  const [waveMa,     setWaveMa]     = useState(20);
  const [momoLookback, setMomoLookback] = useState(60);
  const [momoRedDays,  setMomoRedDays]  = useState(3);
  const [momoExitMa,   setMomoExitMa]   = useState(20);
  const [capital,  setCapital]  = useState(1_000_000);
  const [stopLoss,   setStopLoss]   = useState(0);   // 0 = 停用
  const [takeProfit, setTakeProfit] = useState(0);   // 0 = 停用
  const [maxHold,    setMaxHold]    = useState(0);   // 0 = 不限
  const [withCost,   setWithCost]   = useState(true);

  const [data,     setData]     = useState<{ symbol: string; bars: Bar[] }[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [ran,      setRan]      = useState(false);
  const [saveMsg,  setSaveMsg]  = useState("");

  async function fetchAndRun() {
    const symbols = [...new Set(symbol.split(/[,，\s]+/).map((s) => s.trim().toUpperCase()).filter(Boolean))];
    if (!symbols.length) return;
    if (symbols.length > 10) { setError("最多同時回測 10 檔"); return; }
    setLoading(true); setError(""); setRan(false);
    try {
      const results = await Promise.all(symbols.map(async (sym) => {
        const res = await fetch(`${API}/api/stock/${sym}/ohlcv?period=${period}`);
        if (!res.ok) throw new Error(`${sym}：API 錯誤 ${res.status}`);
        const d = await res.json();
        if (!d.bars?.length) throw new Error(`${sym}：查無歷史資料，請確認代號`);
        return { symbol: sym, bars: d.bars as Bar[] };
      }));
      setData(results);
      setRan(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "未知錯誤");
    } finally {
      setLoading(false);
    }
  }

  const result = useMemo<BacktestResult | null>(() => {
    if (!ran || !data.length) return null;
    const params: Record<string, number> = {
      short_period: shortP, long_period: longP,
      rsi_period: rsiPeriod, oversold, overbought,
      wave_rsi_max: waveRsiMax, wave_ma: waveMa,
      momo_lookback: momoLookback, momo_red_days: momoRedDays, momo_exit_ma: momoExitMa,
    };
    return runPortfolio(data, strategy, params, capital, { stopLoss, takeProfit, maxHold, withCost }, direction);
  }, [ran, data, strategy, direction, shortP, longP, rsiPeriod, oversold, overbought,
      waveRsiMax, waveMa, momoLookback, momoRedDays, momoExitMa,
      capital, stopLoss, takeProfit, maxHold, withCost]);

  // 儲存結果到策略分析頁（backtest_results 表）
  async function saveResult() {
    if (!result || !result.equity.length) return;
    const stratLabel = { ma_cross: "MA交叉", rsi: "RSI", wave: "波段", momentum: "趨勢" }[strategy];
    const dirLabel = { long: "多", short: "空", both: "多空" }[direction];
    setSaveMsg("儲存中…");
    try {
      const res = await fetch(`${API}/api/analytics/strategies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: `${data.map((d) => d.symbol).join("+")}·${stratLabel}·${dirLabel}`,
          period_start: result.equity[0].date,
          period_end: result.equity[result.equity.length - 1].date,
          win_rate: result.win_rate / 100,
          total_return: result.total_return / 100,
          max_drawdown: result.max_drawdown / 100,
          trades: result.trades.map((t) => ({
            pnl: t.pnl_pct, symbol: t.symbol, side: t.side,
            entry: t.entry_date, exit: t.exit_date, reason: t.exit_reason,
          })),
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setSaveMsg("✓ 已儲存，可至「策略分析」頁比較");
    } catch (e) {
      setSaveMsg(`⚠ 儲存失敗（${e instanceof Error ? e.message : e}）`);
    }
  }

  // ── 顏色工具 ──────────────────────────────────────────────────
  const retColor = result
    ? result.total_return >= 0 ? "#ff4d4d" : "#00c076"
    : "var(--c-text)";

  // ── input 共用樣式 ────────────────────────────────────────────
  const inp: React.CSSProperties = {
    background: "var(--c-bg-main)", border: "1px solid var(--c-border)", borderRadius: 6,
    color: "var(--c-text)", padding: "6px 10px", fontSize: 13,
  };

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>

      {/* 頁首 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: "#3d7eff", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Backtest</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h1 style={{ margin: 0, fontSize: 24, color: "var(--c-text)", fontWeight: 700 }}>策略回測</h1>
          <div style={{ fontSize: 11, color: "var(--c-text-dim)", background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 6, padding: "4px 10px" }}>
            資料來源：yfinance · 純前端計算
          </div>
        </div>
      </div>

      {/* 設定面板 */}
      <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14, marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: "var(--c-text-dim)", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 12 }}>
          回測參數
        </div>

        {/* 第一排：基本設定 */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 130px 160px", gap: 10, marginBottom: 10, alignItems: "end" }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>股票代號（逗號分隔可多檔，資金均分）</div>
            <input style={{ ...inp, width: "100%" }} placeholder="2330, 2454, 0050" value={symbol}
              onChange={(e) => setSymbol(e.target.value)} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>資料區間</div>
            <select style={{ ...inp, width: "100%" }} value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="90d">近 3 個月</option>
              <option value="180d">近 6 個月</option>
              <option value="1y">近 1 年</option>
              <option value="2y">近 2 年</option>
              <option value="3y">近 3 年</option>
              <option value="5y">近 5 年</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>初始資金（元）</div>
            <input style={{ ...inp, width: "100%" }} type="number" value={capital}
              onChange={(e) => setCapital(Number(e.target.value))} />
          </div>
        </div>

        {/* 第二排：策略 + 交易方向 */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 260px", gap: 10, marginBottom: 10, alignItems: "end" }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>策略</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {([["ma_cross", "MA 均線交叉"], ["rsi", "RSI 超買超賣"], ["wave", "波段（MACD+RSI+MA）"], ["momentum", "趨勢（N日新高）"]] as const).map(([s, label]) => (
                <button key={s} onClick={() => setStrategy(s)} style={{
                  flex: "1 1 120px", padding: "6px 0", borderRadius: 6, cursor: "pointer", fontSize: 13,
                  border: `1px solid ${strategy === s ? "#00c07655" : "var(--c-border)"}`,
                  background: strategy === s ? "#003d20" : "var(--c-bg-main)",
                  color: strategy === s ? "#00c076" : "var(--c-text-dim)", fontWeight: strategy === s ? 600 : 400,
                }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>交易方向</div>
            <div style={{ display: "flex", gap: 6 }}>
              {([["long", "只做多"], ["short", "只做空"], ["both", "多空雙向"]] as const).map(([d, label]) => (
                <button key={d} onClick={() => setDirection(d)} style={{
                  flex: 1, padding: "6px 0", borderRadius: 6, cursor: "pointer", fontSize: 13,
                  border: `1px solid ${direction === d ? "#3d7eff55" : "var(--c-border)"}`,
                  background: direction === d ? "#001a40" : "var(--c-bg-main)",
                  color: direction === d ? "#3d7eff" : "var(--c-text-dim)", fontWeight: direction === d ? 600 : 400,
                }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 第三排：策略參數 */}
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          {strategy === "ma_cross" && (
            <>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>短均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={2} max={50} value={shortP}
                  onChange={(e) => setShortP(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>長均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={200} value={longP}
                  onChange={(e) => setLongP(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)", alignSelf: "flex-end", paddingBottom: 8 }}>
                短均穿越長均 → 買訊；長均穿越短均 → 賣訊
              </div>
            </>
          )}
          {strategy === "rsi" && (
            <>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>RSI 週期</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={30} value={rsiPeriod}
                  onChange={(e) => setRsiPeriod(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>超賣線（買訊）</div>
                <input style={{ ...inp, width: 90 }} type="number" min={10} max={45} value={oversold}
                  onChange={(e) => setOversold(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>超買線（賣訊）</div>
                <input style={{ ...inp, width: 90 }} type="number" min={55} max={90} value={overbought}
                  onChange={(e) => setOverbought(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)", alignSelf: "flex-end", paddingBottom: 8 }}>
                RSI 從超賣回升 → 買訊；從超買回落 → 賣訊
              </div>
            </>
          )}
          {strategy === "wave" && (
            <>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>RSI 上限</div>
                <input style={{ ...inp, width: 90 }} type="number" min={50} max={90} value={waveRsiMax}
                  onChange={(e) => setWaveRsiMax(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>趨勢均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={120} value={waveMa}
                  onChange={(e) => setWaveMa(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)", alignSelf: "flex-end", paddingBottom: 8 }}>
                MACD 金叉 + RSI 未過熱 + 站上均線 → 買訊；MACD 死叉或跌破均線 → 賣訊
              </div>
            </>
          )}
          {strategy === "momentum" && (
            <>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>新高回看天數</div>
                <input style={{ ...inp, width: 100 }} type="number" min={10} max={250} value={momoLookback}
                  onChange={(e) => setMomoLookback(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>連續紅K天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={1} max={10} value={momoRedDays}
                  onChange={(e) => setMomoRedDays(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>出場均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={120} value={momoExitMa}
                  onChange={(e) => setMomoExitMa(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)", alignSelf: "flex-end", paddingBottom: 8 }}>
                創 N 日新高＋連續收紅 → 買訊；跌破出場均線 → 賣訊
              </div>
            </>
          )}
        </div>

        {/* 第三排：風險控制（兩策略共用）*/}
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>停損 %（0=停用）</div>
            <input style={{ ...inp, width: 100 }} type="number" min={0} max={50} step={0.5} value={stopLoss}
              onChange={(e) => setStopLoss(Math.max(0, Number(e.target.value)))} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>停利 %（0=停用）</div>
            <input style={{ ...inp, width: 100 }} type="number" min={0} max={200} step={0.5} value={takeProfit}
              onChange={(e) => setTakeProfit(Math.max(0, Number(e.target.value)))} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 4 }}>最長持有天數（0=不限）</div>
            <input style={{ ...inp, width: 110 }} type="number" min={0} max={365} value={maxHold}
              onChange={(e) => setMaxHold(Math.max(0, Math.floor(Number(e.target.value))))} />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--c-text-dim)", cursor: "pointer", paddingBottom: 8 }}>
            <input type="checkbox" checked={withCost} onChange={(e) => setWithCost(e.target.checked)} />
            含交易成本（手續費 0.1425%＋證交稅 0.3%）
          </label>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={fetchAndRun} disabled={loading} style={{
            background: loading ? "#1a2a3a" : "#003d20",
            border: `1px solid ${loading ? "var(--c-border)" : "#00c07655"}`,
            borderRadius: 6, color: loading ? "var(--c-text-dim)" : "#00c076",
            fontSize: 13, padding: "8px 24px", cursor: loading ? "not-allowed" : "pointer", fontWeight: 600,
          }}>
            {loading ? "下載資料中…" : "▶ 開始回測"}
          </button>
          {error && <span style={{ fontSize: 12, color: "#ff4d4d" }}>⚠ {error}</span>}
        </div>
      </div>

      {/* 結果區 */}
      {result && (
        <>
          {/* 統計卡 */}
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5, 1fr)", gap: 10, marginBottom: 12 }}>
            <StatBox label="總報酬率" value={`${result.total_return >= 0 ? "+" : ""}${result.total_return.toFixed(2)}%`} color={retColor} />
            <StatBox label="勝率" value={`${result.win_rate.toFixed(1)}%`}
              color={result.win_rate >= 50 ? "#ff4d4d" : "#00c076"} />
            <StatBox label="總交易次數" value={`${result.num_trades} 次`} />
            <StatBox label="最大回撤" value={`-${result.max_drawdown.toFixed(2)}%`} color="#f5a623" />
            <StatBox label="平均持倉天數" value={`${result.avg_hold_days.toFixed(1)} 天`} />
          </div>

          {/* 進階統計 */}
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
            <StatBox label="年化報酬率"
              value={result.annualized === null ? "—" : `${result.annualized >= 0 ? "+" : ""}${result.annualized.toFixed(2)}%`}
              color={result.annualized === null ? undefined : result.annualized >= 0 ? "#ff4d4d" : "#00c076"} />
            <StatBox label="夏普比率"
              value={result.sharpe === null ? "—" : result.sharpe.toFixed(2)}
              color={result.sharpe !== null && result.sharpe >= 1 ? "#ff4d4d" : undefined} />
            <StatBox label="獲利因子"
              value={result.profit_factor === null ? "—" : result.profit_factor === Infinity ? "∞" : result.profit_factor.toFixed(2)}
              color={result.profit_factor !== null && result.profit_factor >= 1.5 ? "#ff4d4d" : undefined} />
            <StatBox label="平均每筆損益"
              value={result.num_trades ? `${result.trades.reduce((a, t) => a + t.pnl_abs, 0) / result.num_trades >= 0 ? "+" : ""}${Math.round(result.trades.reduce((a, t) => a + t.pnl_abs, 0) / result.num_trades).toLocaleString()} 元` : "—"} />
          </div>

          {/* 各股貢獻（多檔時顯示）*/}
          {result.per_symbol.length > 1 && (
            <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14, marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: "var(--c-text-dim)", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 10 }}>
                各股貢獻（資金均分 NT${Math.round(capital / result.per_symbol.length).toLocaleString()}/檔）
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "var(--c-text-dim)", borderBottom: "1px solid var(--c-border)" }}>
                    {["代號", "損益（元）", "交易次數", "勝率"].map((h) => (
                      <th key={h} style={{ padding: "4px 10px", textAlign: "right", fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.per_symbol.map((ps) => (
                    <tr key={ps.symbol} style={{ borderBottom: "1px solid #1a1a2a" }}>
                      <td style={{ padding: "5px 10px", textAlign: "right", color: "#3d7eff", fontWeight: 700 }}>{ps.symbol}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", color: ps.pnl_abs >= 0 ? "#ff4d4d" : "#00c076", fontWeight: 600 }}>
                        {ps.pnl_abs >= 0 ? "+" : ""}{Math.round(ps.pnl_abs).toLocaleString()}
                      </td>
                      <td style={{ padding: "5px 10px", textAlign: "right", color: "var(--c-text-mid)" }}>{ps.num_trades}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", color: "var(--c-text-mid)" }}>{ps.win_rate.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 淨值曲線 */}
          <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14, marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ fontSize: 13, color: "var(--c-text-dim)", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase" }}>
                  淨值曲線
                </div>
                <button onClick={saveResult} style={{
                  background: "var(--c-bg-deep)", border: "1px solid #3d7eff55", borderRadius: 6,
                  color: "#3d7eff", fontSize: 12, padding: "3px 12px", cursor: "pointer",
                }}>💾 存到策略分析</button>
                {saveMsg && <span style={{ fontSize: 11, color: saveMsg.startsWith("⚠") ? "#ff4d4d" : "#00c076" }}>{saveMsg}</span>}
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)" }}>
                期末資產：<span style={{ color: retColor, fontWeight: 700 }}>
                  NT${(result.equity[result.equity.length - 1]?.value ?? capital).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </span>
                　初始：NT${capital.toLocaleString()}
              </div>
            </div>
            <EquityChart equity={result.equity} capital={capital} />
            <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginTop: 6 }}>
              虛線 = 初始資金基準　紅色 = 高於初始　綠色 = 低於初始（台股慣例）
            </div>
          </div>

          {/* 交易紀錄 */}
          <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14 }}>
            <div style={{ fontSize: 13, color: "var(--c-text-dim)", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 10 }}>
              交易紀錄（{result.trades.length} 筆）
            </div>
            {result.trades.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--c-text-dim)", textAlign: "center", padding: "20px 0" }}>
                此區間內無交易訊號，試著調整策略參數或拉長區間。
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ color: "var(--c-text-dim)", borderBottom: "1px solid var(--c-border)" }}>
                      {["#", "代號", "方向", "進場日期", "進場價", "出場日期", "出場價", "報酬率", "損益（元）", "出場原因"].map((h) => (
                        <th key={h} style={{ padding: "4px 10px", textAlign: h === "#" ? "center" : "right", fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => {
                      const up = t.pnl_pct > 0;
                      const color = up ? "#ff4d4d" : "#00c076";
                      return (
                        <tr key={i} style={{ borderBottom: "1px solid #1a1a2a" }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--c-bg-main)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                          <td style={{ padding: "6px 10px", textAlign: "center", color: "var(--c-text-dim)" }}>{i + 1}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#3d7eff", fontWeight: 600 }}>{t.symbol}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right" }}>
                            <span style={{ fontSize: 11, fontWeight: 700, color: t.side === 1 ? "#ff4d4d" : "#00c076" }}>
                              {t.side === 1 ? "多" : "空"}
                            </span>
                          </td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--c-text-dim)" }}>{t.entry_date}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--c-text-mid)" }}>{t.entry_price.toLocaleString()}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--c-text-dim)" }}>{t.exit_date}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--c-text-mid)" }}>{t.exit_price.toLocaleString()}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color, fontWeight: 700 }}>
                            {up ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                          </td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color }}>
                            {up ? "+" : ""}{Math.round(t.pnl_abs).toLocaleString()}
                          </td>
                          <td style={{ padding: "6px 10px", textAlign: "right" }}>
                            <span style={{
                              fontSize: 11, padding: "1px 7px", borderRadius: 4,
                              color: t.exit_reason === "停損" ? "#ff4d4d" : t.exit_reason === "停利" ? "#00c076" : "var(--c-text-dim)",
                              background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
                            }}>{t.exit_reason}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
