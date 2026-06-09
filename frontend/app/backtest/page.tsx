"use client";
import { useState, useMemo, useEffect } from "react";

const API = "";

// ── OHLCV 型別 ────────────────────────────────────────────────────
interface Bar { time: string; open: number; high: number; low: number; close: number; volume: number; }

// ── 回測結果型別 ──────────────────────────────────────────────────
interface Trade {
  entry_date: string; entry_price: number;
  exit_date:  string; exit_price:  number;
  pnl_pct: number; pnl_abs: number;
}
interface BacktestResult {
  trades:        Trade[];
  equity:        { date: string; value: number }[];
  total_return:  number;
  win_rate:      number;
  max_drawdown:  number;
  num_trades:    number;
  avg_hold_days: number;
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

// ── 策略回測引擎 ──────────────────────────────────────────────────
function runBacktest(
  bars: Bar[],
  strategy: "ma_cross" | "rsi",
  params: Record<string, number>,
  capital: number
): BacktestResult {
  const closes = bars.map((b) => b.close);
  let signals: ("buy" | "sell" | null)[] = Array(bars.length).fill(null);

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
  } else {
    const r = rsi(closes, params.rsi_period);
    for (let i = 1; i < bars.length; i++) {
      if (r[i] === null) continue;
      const prev = r[i - 1];
      const curr = r[i]!;
      if (prev !== null && prev <= params.oversold  && curr > params.oversold)  signals[i] = "buy";
      if (prev !== null && prev >= params.overbought && curr < params.overbought) signals[i] = "sell";
    }
  }

  const trades: Trade[] = [];
  const equity: { date: string; value: number }[] = [];
  let cash = capital, holding = 0, entryPrice = 0, entryDate = "";
  let entryIdx = -1;

  for (let i = 0; i < bars.length; i++) {
    const bar = bars[i];
    if (signals[i] === "buy" && holding === 0) {
      holding = Math.floor(cash / bar.close / 1000) * 1000; // 整張
      if (holding === 0) holding = Math.floor(cash / bar.close);
      cash -= holding * bar.close;
      entryPrice = bar.close; entryDate = bar.time; entryIdx = i;
    } else if ((signals[i] === "sell" || i === bars.length - 1) && holding > 0) {
      const pnl_abs = (bar.close - entryPrice) * holding;
      const pnl_pct = (bar.close - entryPrice) / entryPrice * 100;
      const days = i - entryIdx;
      cash += holding * bar.close;
      trades.push({ entry_date: entryDate, entry_price: entryPrice, exit_date: bar.time, exit_price: bar.close, pnl_pct, pnl_abs });
      holding = 0;
    }
    equity.push({ date: bar.time, value: cash + holding * bar.close });
  }

  const initVal = equity[0]?.value ?? capital;
  const finalVal = equity[equity.length - 1]?.value ?? capital;
  const total_return = (finalVal - capital) / capital * 100;
  const win_rate = trades.length ? trades.filter((t) => t.pnl_pct > 0).length / trades.length * 100 : 0;
  const avg_hold_days = trades.length
    ? trades.reduce((s, t) => {
        const diff = (new Date(t.exit_date).getTime() - new Date(t.entry_date).getTime()) / 86400000;
        return s + diff;
      }, 0) / trades.length
    : 0;

  // 最大回撤
  let peak = equity[0]?.value ?? capital, max_drawdown = 0;
  for (const e of equity) {
    if (e.value > peak) peak = e.value;
    const dd = (peak - e.value) / peak * 100;
    if (dd > max_drawdown) max_drawdown = dd;
  }

  return { trades, equity, total_return, win_rate, max_drawdown, num_trades: trades.length, avg_hold_days };
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
        <line x1={PAD} x2={W - PAD} y1={baseY} y2={baseY} stroke="#555570" strokeWidth="1" strokeDasharray="4 3" />
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
    <div style={{ background: "#0d0d15", border: "1px solid #2a2a3a", borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "#e8e8f0" }}>{value}</div>
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
  const [symbol,   setSymbol]   = useState("2330");
  const [period,   setPeriod]   = useState("1y");
  const [strategy, setStrategy] = useState<"ma_cross" | "rsi">("ma_cross");
  const [shortP,   setShortP]   = useState(10);
  const [longP,    setLongP]    = useState(30);
  const [rsiPeriod,setRsiPeriod]= useState(14);
  const [oversold, setOversold] = useState(30);
  const [overbought,setOverbought]=useState(70);
  const [capital,  setCapital]  = useState(1_000_000);

  const [bars,     setBars]     = useState<Bar[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [ran,      setRan]      = useState(false);

  async function fetchAndRun() {
    if (!symbol.trim()) return;
    setLoading(true); setError(""); setRan(false);
    try {
      const res = await fetch(`${API}/api/stock/${symbol.trim()}/ohlcv?period=${period}`);
      if (!res.ok) throw new Error(`API 錯誤 ${res.status}`);
      const data = await res.json();
      if (!data.bars?.length) throw new Error("查無歷史資料，請確認股票代號");
      setBars(data.bars);
      setRan(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "未知錯誤");
    } finally {
      setLoading(false);
    }
  }

  const result = useMemo<BacktestResult | null>(() => {
    if (!ran || !bars.length) return null;
    const params: Record<string, number> = strategy === "ma_cross"
      ? { short_period: shortP, long_period: longP, rsi_period: 0, oversold: 0, overbought: 0 }
      : { short_period: 0, long_period: 0, rsi_period: rsiPeriod, oversold, overbought };
    return runBacktest(bars, strategy, params, capital);
  }, [ran, bars, strategy, shortP, longP, rsiPeriod, oversold, overbought, capital]);

  // ── 顏色工具 ──────────────────────────────────────────────────
  const retColor = result
    ? result.total_return >= 0 ? "#ff4d4d" : "#00c076"
    : "#e8e8f0";

  // ── input 共用樣式 ────────────────────────────────────────────
  const inp: React.CSSProperties = {
    background: "#0d0d15", border: "1px solid #2a2a3a", borderRadius: 6,
    color: "#e8e8f0", padding: "6px 10px", fontSize: 13,
  };

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>

      {/* 頁首 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: "#3d7eff", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Backtest</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h1 style={{ margin: 0, fontSize: 24, color: "#e8e8f0", fontWeight: 700 }}>策略回測</h1>
          <div style={{ fontSize: 11, color: "#555570", background: "#111118", border: "1px solid #2a2a3a", borderRadius: 6, padding: "4px 10px" }}>
            資料來源：yfinance · 純前端計算
          </div>
        </div>
      </div>

      {/* 設定面板 */}
      <div style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 8, padding: 14, marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: "#8888aa", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 12 }}>
          回測參數
        </div>

        {/* 第一排：基本設定 */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "120px 130px 1fr 160px", gap: 10, marginBottom: 10, alignItems: "end" }}>
          <div>
            <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>股票代號</div>
            <input style={{ ...inp, width: "100%" }} placeholder="2330" value={symbol}
              onChange={(e) => setSymbol(e.target.value)} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>資料區間</div>
            <select style={{ ...inp, width: "100%" }} value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="90d">近 3 個月</option>
              <option value="180d">近 6 個月</option>
              <option value="1y">近 1 年</option>
              <option value="2y">近 2 年</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>策略</div>
            <div style={{ display: "flex", gap: 6 }}>
              {(["ma_cross", "rsi"] as const).map((s) => (
                <button key={s} onClick={() => setStrategy(s)} style={{
                  flex: 1, padding: "6px 0", borderRadius: 6, cursor: "pointer", fontSize: 13,
                  border: `1px solid ${strategy === s ? "#00c07655" : "#2a2a3a"}`,
                  background: strategy === s ? "#003d20" : "#0d0d15",
                  color: strategy === s ? "#00c076" : "#8888aa", fontWeight: strategy === s ? 600 : 400,
                }}>
                  {s === "ma_cross" ? "MA 均線交叉" : "RSI 超買超賣"}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>初始資金（元）</div>
            <input style={{ ...inp, width: "100%" }} type="number" value={capital}
              onChange={(e) => setCapital(Number(e.target.value))} />
          </div>
        </div>

        {/* 第二排：策略參數 */}
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          {strategy === "ma_cross" ? (
            <>
              <div>
                <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>短均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={2} max={50} value={shortP}
                  onChange={(e) => setShortP(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>長均線天數</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={200} value={longP}
                  onChange={(e) => setLongP(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "#555570", alignSelf: "flex-end", paddingBottom: 8 }}>
                短均穿越長均 → 買入；長均穿越短均 → 賣出
              </div>
            </>
          ) : (
            <>
              <div>
                <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>RSI 週期</div>
                <input style={{ ...inp, width: 90 }} type="number" min={5} max={30} value={rsiPeriod}
                  onChange={(e) => setRsiPeriod(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>超賣線（買入）</div>
                <input style={{ ...inp, width: 90 }} type="number" min={10} max={45} value={oversold}
                  onChange={(e) => setOversold(Number(e.target.value))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>超買線（賣出）</div>
                <input style={{ ...inp, width: 90 }} type="number" min={55} max={90} value={overbought}
                  onChange={(e) => setOverbought(Number(e.target.value))} />
              </div>
              <div style={{ fontSize: 12, color: "#555570", alignSelf: "flex-end", paddingBottom: 8 }}>
                RSI 從超賣回升 → 買入；從超買回落 → 賣出
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={fetchAndRun} disabled={loading} style={{
            background: loading ? "#1a2a3a" : "#003d20",
            border: `1px solid ${loading ? "#2a2a3a" : "#00c07655"}`,
            borderRadius: 6, color: loading ? "#555570" : "#00c076",
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

          {/* 淨值曲線 */}
          <div style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 8, padding: 14, marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ fontSize: 13, color: "#8888aa", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase" }}>
                淨值曲線
              </div>
              <div style={{ fontSize: 12, color: "#555570" }}>
                期末資產：<span style={{ color: retColor, fontWeight: 700 }}>
                  NT${(result.equity[result.equity.length - 1]?.value ?? capital).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </span>
                　初始：NT${capital.toLocaleString()}
              </div>
            </div>
            <EquityChart equity={result.equity} capital={capital} />
            <div style={{ fontSize: 11, color: "#555570", marginTop: 6 }}>
              虛線 = 初始資金基準　紅色 = 高於初始　綠色 = 低於初始（台股慣例）
            </div>
          </div>

          {/* 交易紀錄 */}
          <div style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 8, padding: 14 }}>
            <div style={{ fontSize: 13, color: "#8888aa", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 10 }}>
              交易紀錄（{result.trades.length} 筆）
            </div>
            {result.trades.length === 0 ? (
              <div style={{ fontSize: 13, color: "#555570", textAlign: "center", padding: "20px 0" }}>
                此區間內無交易訊號，試著調整策略參數或拉長區間。
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ color: "#555570", borderBottom: "1px solid #2a2a3a" }}>
                      {["#", "買入日期", "買入價", "賣出日期", "賣出價", "報酬率", "損益（元）"].map((h) => (
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
                          onMouseEnter={(e) => (e.currentTarget.style.background = "#0d0d15")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                          <td style={{ padding: "6px 10px", textAlign: "center", color: "#555570" }}>{i + 1}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#8888aa" }}>{t.entry_date}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#c8c8d8" }}>{t.entry_price.toLocaleString()}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#8888aa" }}>{t.exit_date}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#c8c8d8" }}>{t.exit_price.toLocaleString()}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color, fontWeight: 700 }}>
                            {up ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                          </td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color }}>
                            {up ? "+" : ""}{Math.round(t.pnl_abs).toLocaleString()}
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
