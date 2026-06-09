"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppContext } from "@/contexts/AppContext";

function useIsMobile() {
  const [m, setM] = useState(false);
  useEffect(() => {
    const c = () => setM(window.innerWidth < 768);
    c(); window.addEventListener("resize", c);
    return () => window.removeEventListener("resize", c);
  }, []);
  return m;
}

// API calls go through Next.js rewrite proxy → /api/* → fastapi:8000
const API = "";

interface UsIndex { price: number; change_pct: number; level?: string }
interface UsIndicesData { sp500: UsIndex; nasdaq: UsIndex; dji: UsIndex; vix: UsIndex }

function fmtPrice(p: number, key: string) {
  if (key === "vix") return p.toFixed(2);
  return p.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function fmtPct(p: number) { return (p >= 0 ? "+" : "") + p.toFixed(2) + "%"; }

function useApi<T>(path: string, interval: number) {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}${path}`);
        if (res.ok) setData(await res.json());
      } catch {}
    };
    load();
    const id = setInterval(load, interval);
    return () => clearInterval(id);
  }, [path, interval]);
  return data;
}

interface TwIndex {
  price: number; change: number; change_pct: number;
  trade_value_bn: number; update_time: string;
}
interface TwBreadth { up: number; down: number; flat: number; source: string }
interface TwMarketData { taiex: TwIndex; otc: TwIndex; breadth: TwBreadth }

interface ChipTotals { foreign: number; trust: number; dealer: number }
interface ChipData { totals: ChipTotals }

function useUsIndices() { return useApi<UsIndicesData>("/api/market/us-indices", 30_000); }
function useTwMarket()  { return useApi<TwMarketData>("/api/market/tw", 10_000); }
function useChip()      { return useApi<ChipData>("/api/market/chip", 300_000); }

function fmtShares(n: number): string {
  // FinMind 單位為股，÷1000 = 張
  const lots = Math.round(n / 1000);
  const sign = lots >= 0 ? "+" : "";
  return `${sign}${lots.toLocaleString()}張`;
}

// ── 共用卡片 ──────────────────────────────────────────────
function Card({
  title,
  children,
  style,
}: {
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        background: "var(--c-bg-card)",
        border: "1px solid var(--c-border)",
        borderRadius: 8,
        padding: 12,
        ...style,
      }}
    >
      <div
        style={{
          fontSize: 17,
          color: "var(--c-label)",
          marginBottom: 10,
          fontWeight: 700,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

// ── 一般指數卡片 ───────────────────────────────────────────
function IndexCard({
  label,
  value,
  chg,
  up,
}: {
  label: string;
  value: string;
  chg: string;
  up: boolean;
}) {
  return (
    <div
      style={{
        background: "var(--c-bg-deep)",
        border: "1px solid var(--c-border)",
        borderRadius: 8,
        padding: "10px 14px",
        flex: 1,
      }}
    >
      <div style={{ fontSize: 13, color: "var(--c-label)", marginBottom: 4, letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--c-text)", fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
      <div
        style={{
          fontSize: 15,
          color: up ? "#00c076" : "#ff4d4d",
          marginTop: 2,
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 600,
        }}
      >
        {chg}
      </div>
    </div>
  );
}

// ── 恐懼貪婪半圓儀表（Bloomberg Cyberpunk 版）────────────────
function fngColor(v: number) {
  return v >= 75 ? "#00e676" : v >= 55 ? "#69f0ae" : v >= 45 ? "#ffd600" : v >= 25 ? "#ff6d00" : "#ff1744";
}
function fngLabel(v: number) {
  return v >= 75 ? "極度貪婪" : v >= 55 ? "貪婪" : v >= 45 ? "中性" : v >= 25 ? "恐懼" : "極度恐懼";
}

function FearGreedGauge({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDisplayed(value), 300);
    return () => clearTimeout(t);
  }, [value]);
  const cx = 160, cy = 140;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  function arcPath(a1: number, a2: number, innerR: number, outerR: number) {
    const p1o = { x: cx + outerR * Math.cos(toRad(a1)), y: cy + outerR * Math.sin(toRad(a1)) };
    const p2o = { x: cx + outerR * Math.cos(toRad(a2)), y: cy + outerR * Math.sin(toRad(a2)) };
    const p1i = { x: cx + innerR * Math.cos(toRad(a1)), y: cy + innerR * Math.sin(toRad(a1)) };
    const p2i = { x: cx + innerR * Math.cos(toRad(a2)), y: cy + innerR * Math.sin(toRad(a2)) };
    return `M ${p1o.x} ${p1o.y} A ${outerR} ${outerR} 0 0 1 ${p2o.x} ${p2o.y} L ${p2i.x} ${p2i.y} A ${innerR} ${innerR} 0 0 0 ${p1i.x} ${p1i.y} Z`;
  }
  const needleAngle = 180 + (displayed / 100) * 180;
  const nX = cx + 90 * Math.cos(toRad(needleAngle));
  const nY = cy + 90 * Math.sin(toRad(needleAngle));
  const color = fngColor(displayed);
  return (
    <svg viewBox="0 0 320 155" style={{ width: "100%", overflow: "visible" }}>
      <defs>
        <filter id="fng-glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {/* 背景弧 */}
      <path d={arcPath(180, 360, 88, 118)} fill="var(--c-border)" />
      {/* 色帶 */}
      <path d={arcPath(180, 207, 90, 116)} fill="#b71c1c" opacity={0.85} />
      <path d={arcPath(207, 234, 90, 116)} fill="#f44336" opacity={0.85} />
      <path d={arcPath(234, 261, 90, 116)} fill="#ff6d00" opacity={0.85} />
      <path d={arcPath(261, 288, 90, 116)} fill="#ffd600" opacity={0.85} />
      <path d={arcPath(288, 315, 90, 116)} fill="#69f0ae" opacity={0.85} />
      <path d={arcPath(315, 360, 90, 116)} fill="#00e676" opacity={0.85} />
      {/* 遮罩環 */}
      <path d={arcPath(180, 360, 82, 92)} fill="var(--c-bg-deep)" opacity={0.6} />
      {/* 刻度 */}
      {([0, 25, 50, 75, 100] as const).map(t => {
        const a = 180 + (t / 100) * 180;
        return (
          <text key={`tick-${t}`}
            x={cx + 130 * Math.cos(toRad(a))} y={cy + 130 * Math.sin(toRad(a))}
            textAnchor="middle" dominantBaseline="middle" fontSize="12"
            fill="var(--c-label)" fontFamily="'JetBrains Mono', monospace">{t}</text>
        );
      })}
      {/* 指針 */}
      <line x1={cx} y1={cy} x2={nX} y2={nY}
        stroke={color} strokeWidth="3" strokeLinecap="round"
        filter="url(#fng-glow)"
        style={{ transition: "all 1.2s cubic-bezier(.34,1.56,.64,1)" }} />
      <circle cx={cx} cy={cy} r="8" fill={color} filter="url(#fng-glow)" />
      <circle cx={cx} cy={cy} r="4" fill="var(--c-bg-deep)" />
      {/* 數值 */}
      <text x={cx} y={cy - 28} textAnchor="middle" fontSize="38" fontWeight="700"
        fill={color} fontFamily="'JetBrains Mono', monospace" filter="url(#fng-glow)">{displayed}</text>
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize="15"
        fill={color} fontFamily="'Noto Sans TC', sans-serif" fontWeight="600">{fngLabel(displayed)}</text>
    </svg>
  );
}

// ── VIX 獨立卡片（含顏色分級）─────────────────────────────
function VixCard({
  value,
  chg,
  level,
}: {
  value: string;
  chg: string;
  level: "low" | "medium" | "high";
}) {
  const map = {
    low:    { color: "#00c076", bg: "#003d20", text: "低恐慌", note: "VIX < 20 多頭有利" },
    medium: { color: "#f5a623", bg: "#3d2a00", text: "中性波動", note: "VIX 20-30 謹慎操作" },
    high:   { color: "#ff4d4d", bg: "#3d0000", text: "高恐慌", note: "VIX > 30 注意風險" },
  };
  const { color, bg, text, note } = map[level];
  return (
    <div
      style={{
        background: bg,
        border: `1px solid ${color}55`,
        borderRadius: 10,
        padding: "20px 24px",
        width: "100%",
      }}
    >
      <div style={{ fontSize: 14, color: "var(--c-text-dim)", marginBottom: 8, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono',monospace" }}>
        VIX 恐慌指數
      </div>
      <div style={{ fontSize: 42, fontWeight: 700, color: "var(--c-text)", fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 18, color, marginTop: 6, fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{chg}</div>
      <div
        style={{
          marginTop: 12,
          fontSize: 15,
          color,
          fontWeight: 700,
          padding: "4px 12px",
          background: `${color}22`,
          borderRadius: 6,
          border: `1px solid ${color}66`,
          display: "inline-block",
          letterSpacing: 0.5,
        }}
      >
        {text}
      </div>
      <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>{note}</div>
    </div>
  );
}

// ── 巴菲特指標（台股）────────────────────────────────────────
// 台股市值 ÷ 台灣 GDP × 100%
// 區間：<80% 低估｜80-120% 合理｜120-160% 高估｜>160% 嚴重高估
interface BuffettData {
  ratio: number;        // e.g. 142.5
  market_cap_nt: number; // 台股總市值（兆元）
  gdp_nt: number;        // GDP（兆元）
  date: string;
  source?: string;
}

const BUFFETT_ZONES = [
  { max: 80,  label: "嚴重低估", color: "#3d7eff", bg: "#0a1a3d" },
  { max: 120, label: "合理區間", color: "#00c076", bg: "#003d20" },
  { max: 160, label: "高估區間", color: "#f5a623", bg: "#3d2a00" },
  { max: 999, label: "嚴重高估", color: "#ff4d4d", bg: "#3d0000" },
];

function buffettZone(ratio: number) {
  return BUFFETT_ZONES.find(z => ratio < z.max) ?? BUFFETT_ZONES[BUFFETT_ZONES.length - 1];
}

function BuffettCard() {
  const [data, setData] = useState<BuffettData | null | "unavailable">(null);

  useEffect(() => {
    fetch("/api/market/buffett")
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.ratio != null) setData(d);
        else setData("unavailable");
      })
      .catch(() => setData("unavailable"));
  }, []);

  // fallback demo（台股 2024 年底估算）
  const demo: BuffettData = {
    ratio: 156.3,
    market_cap_nt: 73.2,
    gdp_nt: 46.8,
    date: "2025/12",
    source: "demo",
  };
  const d = data === "unavailable" ? demo : (data ?? null);
  const zone = d ? buffettZone(d.ratio) : null;

  // 橫向分段量表（0% → 200%）
  const BAR_MAX = 200;
  const segments = [
    { from: 0,   to: 80,  color: "#3d7eff33", border: "#3d7eff" },
    { from: 80,  to: 120, color: "#00c07633", border: "#00c076" },
    { from: 120, to: 160, color: "#f5a62333", border: "#f5a623" },
    { from: 160, to: 200, color: "#ff4d4d33", border: "#ff4d4d" },
  ];

  return (
    <Card title="巴菲特指標・台股">
      {d === null ? (
        <div style={{ color:"var(--c-text-dim)", fontSize:13, padding:"40px 0", textAlign:"center" }}>載入中…</div>
      ) : (
        <div style={{ display:"flex", flexDirection:"column", gap:12 }}>

          {/* 數值 + 區間標籤 */}
          <div style={{ display:"flex", alignItems:"flex-end", gap:12 }}>
            <div>
              <div style={{ fontSize:11, color:"var(--c-label)", letterSpacing:1, textTransform:"uppercase", fontFamily:"'JetBrains Mono',monospace", marginBottom:4 }}>
                市值 / GDP
              </div>
              <div style={{ fontSize:44, fontWeight:700, color: zone!.color, fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>
                {d.ratio.toFixed(1)}<span style={{ fontSize:22 }}>%</span>
              </div>
            </div>
            <div style={{
              marginBottom:6, padding:"4px 12px", borderRadius:6,
              background: `${zone!.color}22`, border:`1px solid ${zone!.color}66`,
              color: zone!.color, fontSize:14, fontWeight:700, letterSpacing:0.5,
            }}>
              {zone!.label}
            </div>
          </div>

          {/* 橫向量表 */}
          <div>
            <div style={{ display:"flex", borderRadius:6, overflow:"hidden", height:12, marginBottom:6 }}>
              {segments.map((seg, i) => {
                const width = ((seg.to - seg.from) / BAR_MAX) * 100;
                return (
                  <div key={i} style={{
                    width:`${width}%`, background: seg.color,
                    borderRight: i < segments.length-1 ? `1px solid ${seg.border}` : undefined,
                  }} />
                );
              })}
            </div>
            {/* 指針 */}
            <div style={{ position:"relative", height:16, marginBottom:2 }}>
              <div style={{
                position:"absolute",
                left:`${Math.min((d.ratio / BAR_MAX) * 100, 98)}%`,
                transform:"translateX(-50%)",
                fontSize:12, color: zone!.color, fontWeight:700,
              }}>▲</div>
            </div>
            {/* 刻度標籤 */}
            <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--c-text-dim)" }}>
              {[0, 80, 120, 160, 200].map(v => (
                <span key={v}>{v}%</span>
              ))}
            </div>
          </div>

          {/* 細節 */}
          <div style={{ display:"flex", flexDirection:"column", gap:5, borderTop:"1px solid var(--c-border)", paddingTop:8 }}>
            {[
              { label:"台股總市值", value: d.market_cap_nt ? `${d.market_cap_nt.toFixed(1)} 兆` : "---" },
              { label:"台灣 GDP",   value: d.gdp_nt ? `${d.gdp_nt.toFixed(1)} 兆` : "---" },
              { label:"資料日期",   value: d.date ?? "---" },
            ].map(r => (
              <div key={r.label} style={{ display:"flex", justifyContent:"space-between", fontSize:17 }}>
                <span style={{ color:"var(--c-text-dim)" }}>{r.label}</span>
                <span style={{ color:"var(--c-text)", fontFamily:"'JetBrains Mono',monospace" }}>{r.value}</span>
              </div>
            ))}
          </div>

          {/* 說明 */}
          <div style={{ fontSize:14, color:"var(--c-text-dim)", lineHeight:1.6, borderTop:"1px solid var(--c-border)", paddingTop:8 }}>
            {data === "unavailable" && <span style={{ color:"#f5a623" }}>⚠ 使用估算數據 · </span>}
            &lt;80% 嚴重低估｜80-120% 合理｜120-160% 高估｜&gt;160% 過熱
          </div>

        </div>
      )}
    </Card>
  );
}

// ── 熱力圖格子（台股：漲紅跌綠）────────────────────────────
function TwHeatCell({ label, chg }: { label: string; chg: number }) {
  const router = useRouter();
  const color =
    chg > 2 ? "#ff4d4d" : chg > 0 ? "#cc3333" : chg > -2 ? "#009955" : "#00c076";
  const bg =
    chg > 2 ? "#3d0000" : chg > 0 ? "#2a0a0a" : chg > -2 ? "#002210" : "#003d20";
  return (
    <div
      onClick={() => router.push(`/industry?s=${encodeURIComponent(label)}`)}
      style={{
        background: bg,
        border: `1px solid ${color}55`,
        borderRadius: 6,
        padding: "8px 6px",
        textAlign: "center",
        cursor: "pointer",
        transition: "all 0.15s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.filter = "brightness(1.3)";
        e.currentTarget.style.boxShadow = `0 0 10px ${color}55`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.filter = "brightness(1)";
        e.currentTarget.style.boxShadow = "none";
      }}
      title={`查看${label}產業個股`}
    >
      <div style={{ fontSize: 14, color: "var(--c-text-mid)", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {chg > 0 ? "+" : ""}
        {chg}%
      </div>
    </div>
  );
}

// ── 美股格子點擊 Modal ───────────────────────────────────────
function UsStockModal({
  stock,
  onClose,
}: {
  stock: { label: string; full_name?: string; symbol?: string; chg: number; price?: number; is_crypto?: boolean };
  onClose: () => void;
}) {
  const up = stock.chg >= 0;
  const color = up ? "#00c076" : "#ff4d4d";
  const tvSym = stock.is_crypto ? "BTCUSD" : stock.symbol ?? stock.label;
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${tvSym}`;
  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"#00000099", zIndex:1000,
      display:"flex", alignItems:"center", justifyContent:"center",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background:"var(--c-bg-modal)", border:"1px solid #3a3a5a", borderRadius:14,
        padding:"24px 28px", minWidth:280, boxShadow:"0 8px 40px #000c",
      }}>
        {/* 標題 */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16 }}>
          <div>
            <div style={{ fontSize:22, fontWeight:800, color:"var(--c-text)" }}>{stock.label}</div>
            {stock.full_name && (
              <div style={{ fontSize:13, color:"var(--c-text-dim)", marginTop:2 }}>{stock.full_name}</div>
            )}
          </div>
          <button onClick={onClose} style={{
            background:"transparent", border:"none", color:"var(--c-text-dim)",
            fontSize:18, cursor:"pointer", padding:"0 4px",
          }}>✕</button>
        </div>
        {/* 價格 */}
        <div style={{ marginBottom:20 }}>
          <div style={{ fontSize:30, fontWeight:700, color:"var(--c-text)" }}>
            {stock.is_crypto
              ? `$${Number(stock.price).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
              : `$${stock.price?.toLocaleString("en-US", { maximumFractionDigits: 2 }) ?? "--"}`
            }
          </div>
          <div style={{ fontSize:18, fontWeight:600, color, marginTop:4 }}>
            {up ? "▲ +" : "▼ "}{Math.abs(stock.chg).toFixed(2)}%
            <span style={{ fontSize:13, color:"var(--c-text-dim)", marginLeft:8 }}>較前日收盤</span>
          </div>
        </div>
        {/* 標籤 */}
        <div style={{ display:"flex", gap:8, marginBottom:20, flexWrap:"wrap" }}>
          <span style={{
            fontSize:12, padding:"3px 10px", borderRadius:20,
            background: stock.is_crypto ? "#2a1a3a" : "#1a2a3a",
            color: stock.is_crypto ? "#cc44ff" : "#3d7eff",
            border: `1px solid ${stock.is_crypto ? "#cc44ff44" : "#3d7eff44"}`,
          }}>
            {stock.is_crypto ? "🪙 加密貨幣" : "🇺🇸 美股"}
          </span>
          <span style={{
            fontSize:12, padding:"3px 10px", borderRadius:20,
            background: up ? "#003d20" : "#3d0000",
            color, border:`1px solid ${color}44`,
          }}>
            {up ? "上漲" : "下跌"}
          </span>
        </div>
        {/* TradingView 連結 */}
        <a href={tvUrl} target="_blank" rel="noopener noreferrer" style={{
          display:"block", textAlign:"center", padding:"10px 0",
          background:"var(--c-bg-deep)", border:"1px solid #3d7eff44", borderRadius:8,
          color:"#3d7eff", fontSize:13, fontWeight:600, textDecoration:"none",
        }}
          onMouseEnter={e => (e.currentTarget.style.background="#222240")}
          onMouseLeave={e => (e.currentTarget.style.background="var(--c-bg-deep)")}
        >
          📈 在 TradingView 查看完整圖表 →
        </a>
      </div>
    </div>
  );
}

// ── 熱力圖格子（美股：漲綠跌紅）────────────────────────────
function UsHeatCell({
  label, chg, price, full_name, symbol, is_crypto, onClick,
}: {
  label: string; chg: number; price?: number;
  full_name?: string; symbol?: string; is_crypto?: boolean;
  onClick: () => void;
}) {
  const color =
    chg > 2 ? "#00c076" : chg > 0 ? "#009955" : chg > -2 ? "#cc3333" : "#ff4d4d";
  const bg =
    chg > 2 ? "#003d20" : chg > 0 ? "#002210" : chg > -2 ? "#2a0a0a" : "#3d0000";
  return (
    <div
      onClick={onClick}
      style={{
        background: bg, border: `1px solid ${color}55`, borderRadius: 6,
        padding: "8px 6px", textAlign: "center", cursor: "pointer",
        transition: "all 0.15s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.filter = "brightness(1.35)";
        e.currentTarget.style.boxShadow = `0 0 10px ${color}55`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.filter = "brightness(1)";
        e.currentTarget.style.boxShadow = "none";
      }}
      title={full_name}
    >
      <div style={{ fontSize: 14, color: "var(--c-text-mid)", marginBottom: 1 }}>
        {is_crypto ? "₿ " : ""}{label}
      </div>
      {price !== undefined && (
        <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginBottom: 1, fontFamily: "'JetBrains Mono', monospace" }}>
          {is_crypto
            ? `$${Number(price).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
            : `$${price}`}
        </div>
      )}
      <div style={{ fontSize: 15, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {chg > 0 ? "+" : ""}{chg.toFixed(2)}%
      </div>
    </div>
  );
}

// ── 主頁面 ────────────────────────────────────────────────
export default function MarketOverview() {
  const isMobile = useIsMobile();
  const router   = useRouter();
  const { stockPool, setIsSettingsOpen } = useAppContext();
  const usData  = useUsIndices();
  const twData  = useTwMarket();
  const chipData = useChip();
  // ── 台股產業熱力圖（API）────────────────────────────────────
  const [tw, setTw] = useState<{label:string;chg:number}[]>([]);
  useEffect(() => {
    fetch(`${API}/api/market/sectors`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.sectors?.length && setTw(d.sectors))
      .catch(() => {});
  }, []);

  // ── 記憶體族群（API）────────────────────────────────────────
  const [memStocks, setMemStocks] = useState<{code:string;name:string;price:number;chg:number}[]>([]);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/memory-stocks`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.stocks?.length && setMemStocks(d.stocks))
      .catch(() => {});
    load();
    const id = setInterval(load, 300_000);
    return () => clearInterval(id);
  }, []);

  // ── 八大官股（API）──────────────────────────────────────────
  const [govFunds, setGovFunds] = useState<{items:{name:string;net_bn:number;direction:string}[];total_bn:number;date:string;source:string} | null | "unavailable">(null);
  useEffect(() => {
    fetch(`${API}/api/market/gov-funds`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return;
        if (d.source === "unavailable" || !d.items?.length) {
          setGovFunds("unavailable");
        } else {
          setGovFunds(d);
        }
      })
      .catch(() => setGovFunds("unavailable"));
  }, []);

  // ── 恐懼與貪婪指數（API）────────────────────────────────────
  interface FgPoint { value: number; label: string; date: string }
  interface FgData { today?: FgPoint; yesterday?: FgPoint; week_ago?: FgPoint; month_ago?: FgPoint; year_ago?: FgPoint }
  const [fg, setFg] = useState<FgData | null>(null);
  useEffect(() => {
    fetch(`${API}/api/market/fear-greed`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.today && setFg(d))
      .catch(() => {});
  }, []);

  // ── 美股科技熱力圖（API）────────────────────────────────────
  const [us, setUs] = useState<{label:string;chg:number;price?:number;full_name?:string;symbol?:string;is_crypto?:boolean}[]>([]);
  const [usModal, setUsModal] = useState<typeof us[0] | null>(null);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/us-stocks`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.stocks?.length && setUs(d.stocks))
      .catch(() => {});
    load();
    const id = setInterval(load, 300_000); // 5分鐘
    return () => clearInterval(id);
  }, []);

  // ── 波段領頭羊（API）────────────────────────────────────────
  const [leaders, setLeaders] = useState<{code:string;name:string;score:number;rsi:number}[]>([]);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/leaders?limit=5`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.results && setLeaders(d.results))
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  // ── 漲幅排行榜（API）────────────────────────────────────────
  const [topMovers, setTopMovers] = useState<{code:string;name:string;price:number;chg_pct:number}[]>([]);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/top-movers?limit=5`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.results && setTopMovers(d.results))
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  // ── 手機判斷 (S25 Ultra = 412px) ─────────────────────────────
  const isTablet = !isMobile && typeof window !== "undefined" && window.innerWidth < 1024;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {usModal && <UsStockModal stock={usModal} onClose={() => setUsModal(null)} />}

      {/* ══ Row 1：市場溫度計 ＋ 恐懼與貪婪 ＋ 巴菲特指標 ══ */}
      <div style={{
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : isTablet ? "1fr 1fr" : "1fr 1fr 1fr",
        gap: 12,
      }}>

        {/* 市場溫度計 */}
        <Card title="市場溫度計">
          {(() => {
            const taiex    = twData?.taiex;
            const breadth  = twData?.breadth;
            const total    = (breadth?.up ?? 0) + (breadth?.down ?? 0);
            const bullPct  = total > 0 ? Math.round((breadth!.up / total) * 100) : 50;
            const bullColor = bullPct >= 55 ? "#ff4d4d" : bullPct <= 45 ? "#00c076" : "#f5a623";
            const bullLabel = bullPct >= 55 ? "偏多↑" : bullPct <= 45 ? "偏空↓" : "中性";
            const tradeStr  = taiex
              ? `成交 ${taiex.trade_value_bn.toFixed(0)}億`
              : "成交 ---";
            return (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 12 }}>
                  <div style={{
                    width: 64, height: 64, borderRadius: "50%",
                    background: `conic-gradient(${bullColor} 0% ${bullPct}%, #1a1a2a ${bullPct}% 100%)`,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <div style={{
                      width: 50, height: 50, borderRadius: "50%",
                      background: "var(--c-bg-modal)", display: "flex", alignItems: "center",
                      justifyContent: "center", fontSize: 22, fontWeight: 700, color: bullColor,
                    }}>
                      {total > 0 ? bullPct : "--"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 22, color: bullColor, fontWeight: 700 }}>{bullLabel}</div>
                    <div style={{ fontSize: 19, color: "var(--c-text-dim)", marginTop: 2 }}>{tradeStr}</div>
                    {taiex && (
                      <div style={{ fontSize: 19, color: "var(--c-text-dim)", marginTop: 1 }}>
                        更新 {taiex.update_time || "---"}
                      </div>
                    )}
                  </div>
                </div>
                {[
                  { label: "上漲家數", value: breadth && breadth.source !== "unavailable" ? breadth.up.toLocaleString() : "---", color: "#ff4d4d" },
                  { label: "下跌家數", value: breadth && breadth.source !== "unavailable" ? breadth.down.toLocaleString() : "---", color: "#00c076" },
                  { label: "加權指數", value: taiex ? taiex.price.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "---", color: (taiex?.change_pct ?? 0) >= 0 ? "#ff4d4d" : "#00c076" },
                  { label: "OTC 指數", value: twData ? twData.otc.price.toFixed(2) : "---", color: (twData?.otc.change_pct ?? 0) >= 0 ? "#ff4d4d" : "#00c076" },
                  {
                    label: "外資方向",
                    value: chipData ? fmtShares(chipData.totals.foreign) : "---",
                    color: (chipData?.totals.foreign ?? 0) >= 0 ? "#ff4d4d" : "#00c076",
                  },
                ].map((r) => (
                  <div key={r.label} style={{
                    display: "flex", justifyContent: "space-between",
                    marginBottom: 5, paddingBottom: 5, borderBottom: "1px solid #1a1a2a",
                  }}>
                    <span style={{ fontSize: 19, color: "var(--c-text-dim)" }}>{r.label}</span>
                    <span style={{ fontSize: 19, fontWeight: 600, color: r.color }}>{r.value}</span>
                  </div>
                ))}
              </>
            );
          })()}
        </Card>

        {/* ── 恐懼與貪婪卡片（縮排版） ── */}
        <Card title="恐懼與貪婪指數">
          {fg?.today ? (
            <div style={{ display:"flex", flexDirection:"column", gap: 10 }}>
              {/* 儀表 */}
              <FearGreedGauge value={fg.today.value} />
              <div style={{ textAlign:"center", fontSize:11, color:"var(--c-text-dim)", marginTop:-6 }}>
                {fg.today.date} · 加密市場情緒
              </div>
              {/* 歷史對比 */}
              <div style={{ display:"flex", flexDirection:"column", gap:4, borderTop:"1px solid var(--c-border)", paddingTop:8 }}>
                {([
                  { key:"yesterday", label:"前一日" },
                  { key:"week_ago",  label:"一週前" },
                  { key:"month_ago", label:"一個月前" },
                  { key:"year_ago",  label:"一年前" },
                ] as { key: keyof FgData; label: string }[]).map(({ key, label }) => {
                  const pt = fg[key] as FgPoint | undefined;
                  if (!pt) return null;
                  const c = fngColor(pt.value);
                  return (
                    <div key={key} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", fontSize:17 }}>
                      <span style={{ color:"var(--c-text-dim)" }}>{label}
                        <span style={{ color:"#444460", marginLeft:5, fontSize:12 }}>{pt.date}</span>
                      </span>
                      <span style={{ color:c, fontWeight:700, fontFamily:"'JetBrains Mono',monospace" }}>
                        {pt.label} {pt.value}
                      </span>
                    </div>
                  );
                })}
              </div>
              {/* VIX 小版 */}
              <div style={{ borderTop:"1px solid var(--c-border)", paddingTop:8 }}>
                <VixCard
                  value={usData ? fmtPrice(usData.vix.price, "vix") : "---"}
                  chg={usData ? fmtPct(usData.vix.change_pct) : "---"}
                  level={(usData?.vix.level ?? "low") as "low" | "medium" | "high"}
                />
              </div>
            </div>
          ) : (
            <div style={{ color:"var(--c-text-dim)", fontSize:13, padding:"40px 0", textAlign:"center" }}>載入中…</div>
          )}
        </Card>

        {/* ── 巴菲特指標（台股）── */}
        <BuffettCard />

      </div>

      {/* ══ Row 2：八大官股 ＋ 美股指數 ＋ 美股熱力圖 ＋ 台股產業熱力圖 ══ */}
      <div style={{
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : isTablet ? "1fr 1fr" : "1fr 1fr 1.5fr 1.5fr",
        gap: 12,
      }}>

        {/* 八大官股 */}
        <Card title="八大官股動向">
          {govFunds === null ? (
            <div style={{ fontSize: 15, color: "var(--c-text-dim)", padding: "20px 0", textAlign: "center" }}>載入中…</div>
          ) : govFunds === "unavailable" ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.6 }}>
              <div style={{ fontSize: 22, marginBottom: 8 }}>📭</div>
              <div>資料不可用</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>非交易時段或資料來源無回應</div>
            </div>
          ) : (
            <>
              {govFunds.items.map((b) => (
                <div
                  key={b.name}
                  style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: 6, padding: "4px 0",
                    borderBottom: "1px solid var(--c-border)",
                  }}
                >
                  <span style={{ fontSize: 15, color: "var(--c-text-mid)" }}>{b.name}</span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: b.net_bn >= 0 ? "#ff4d4d" : "#00c076", fontFamily:"'JetBrains Mono',monospace" }}>
                    {b.net_bn >= 0 ? "+" : ""}{b.net_bn}億
                  </span>
                </div>
              ))}
              <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 4 }}>
                合計 {govFunds.total_bn >= 0 ? "+" : ""}{govFunds.total_bn}億
                {govFunds.date ? ` ｜ ${govFunds.date}` : ""}
                {govFunds.source === "dealer_proxy" ? " (估算)" : ""}
              </div>
            </>
          )}
        </Card>

        {/* 美股指數 */}
        <Card title="美股指數">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <IndexCard label="S&P 500" value={usData ? fmtPrice(usData.sp500.price, "sp500")  : "---"} chg={usData ? fmtPct(usData.sp500.change_pct)  : "---"} up={(usData?.sp500.change_pct  ?? 1) >= 0} />
            <IndexCard label="Nasdaq"  value={usData ? fmtPrice(usData.nasdaq.price, "nasdaq") : "---"} chg={usData ? fmtPct(usData.nasdaq.change_pct) : "---"} up={(usData?.nasdaq.change_pct ?? 1) >= 0} />
            <IndexCard label="道瓊"    value={usData ? fmtPrice(usData.dji.price, "dji") : "---"} chg={usData ? fmtPct(usData.dji.change_pct) : "---"} up={(usData?.dji.change_pct ?? 0) >= 0} />
          </div>
        </Card>

        {/* 美股科技熱力圖 */}
        <Card title="美股科技熱力圖（點擊看詳情）">
          {us.length === 0 ? (
            <div style={{ color:"var(--c-text-dim)", fontSize:13, padding:"20px 0", textAlign:"center" }}>載入中…</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
              {us.map((s) => (
                <UsHeatCell
                  key={s.label} label={s.label} chg={s.chg} price={s.price}
                  full_name={s.full_name} symbol={s.symbol} is_crypto={s.is_crypto}
                  onClick={() => setUsModal(s)}
                />
              ))}
            </div>
          )}
        </Card>

        {/* 台股產業熱力圖 */}
        <Card title="台股產業熱力圖（漲紅跌綠）">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 5 }}>
            {tw.map((i) => (
              <TwHeatCell key={i.label} {...i} />
            ))}
          </div>
          {memStocks.length > 0 && (
            <div style={{ marginTop: 10, borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
              <div style={{ fontSize: 12, color: "var(--c-label)", marginBottom: 5, letterSpacing: 1, textTransform:"uppercase" }}>
                💾 記憶體族群
              </div>
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {memStocks.map(s => {
                  const up = s.chg >= 0;
                  const color = up ? "#ff4d4d" : "#00c076";
                  const bg    = up ? "#2a0a0a" : "#002210";
                  return (
                    <div
                      key={s.code}
                      onClick={() => router.push(`/stock?s=${s.code}`)}
                      style={{
                        background: bg, border: `1px solid ${color}44`, borderRadius: 5,
                        padding: "4px 8px", cursor: "pointer", textAlign: "center",
                        transition: "filter 0.15s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.filter = "brightness(1.3)")}
                      onMouseLeave={e => (e.currentTarget.style.filter = "brightness(1)")}
                    >
                      <div style={{ fontSize: 12, color: "var(--c-text-mid)" }}>{s.name}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color, fontFamily:"'JetBrains Mono',monospace" }}>
                        {up ? "+" : ""}{s.chg.toFixed(2)}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>
      </div>



      {/* ══ Row 3：個股動向 ══ */}
      <div style={isMobile ? {
        display: "flex", gap: 10,
        overflowX: "auto", WebkitOverflowScrolling: "touch" as "touch",
        paddingBottom: 4,
        scrollSnapType: "x mandatory",
      } : { display: "grid", gridTemplateColumns: isTablet ? "1fr 1fr" : "1fr 1fr 1fr 1fr", gap: 12 }}>

        {/* 波段領頭羊 */}
        <Card title="波段領頭羊" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {leaders.length === 0 ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.8 }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>📋</div>
              <div>尚無追蹤個股資料</div>
              <button
                onClick={() => setIsSettingsOpen(true)}
                style={{
                  marginTop: 10, background: "transparent", border: "1px solid #00c07644",
                  borderRadius: 6, color: "#00c076", fontSize: 13, cursor: "pointer",
                  padding: "4px 14px",
                }}
              >⚙️ 設定股票池</button>
            </div>
          ) : leaders.map((s) => (
            <div
              key={s.code}
              onClick={() => router.push(`/stock?s=${s.code}`)}
              style={{
                display: "flex", justifyContent: "space-between",
                alignItems: "center", padding: "8px 0",
                borderBottom: "1px solid #1a1a2a",
                cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--c-bg-deep)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 16, color: "#3d7eff", fontWeight: 700, whiteSpace: "nowrap" }}>
                  {s.code}
                </span>
                <span style={{ fontSize: 15, color: "var(--c-text-dim)", whiteSpace: "nowrap" }}>
                  {s.name}
                </span>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span style={{ fontSize: 14, color: "var(--c-text-dim)" }}>RSI {s.rsi}</span>
                <span style={{
                  fontSize: 14, padding: "1px 6px", borderRadius: 3, fontWeight: 700,
                  background: s.score >= 80 ? "#3d0000" : "#1a2a3a",
                  color: s.score >= 80 ? "#ff4d4d" : "#3d7eff",
                  border: `1px solid ${s.score >= 80 ? "#ff4d4d44" : "#3d7eff44"}`,
                }}>
                  AI {s.score}
                </span>
              </div>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>
            AI ≥ 80 = 強烈關注 · 每分鐘更新 · 點擊看個股
          </div>
        </Card>

        {/* 漲幅排行 */}
        <Card title="漲幅排行榜" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {topMovers.length === 0 ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.8 }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>📊</div>
              <div>尚無排行資料</div>
              <button
                onClick={() => setIsSettingsOpen(true)}
                style={{
                  marginTop: 10, background: "transparent", border: "1px solid #00c07644",
                  borderRadius: 6, color: "#00c076", fontSize: 13, cursor: "pointer",
                  padding: "4px 14px",
                }}
              >⚙️ 設定股票池</button>
            </div>
          ) : topMovers.map((s, i) => (
            <div
              key={s.code}
              onClick={() => router.push(`/stock?s=${s.code}`)}
              style={{
                display: "flex", gap: 8, alignItems: "center",
                padding: "7px 0", borderBottom: "1px solid #1a1a2a",
                cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--c-bg-deep)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ fontSize: 14, color: "var(--c-text-dim)", width: 14, flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontSize: 16, color: "#3d7eff", fontWeight: 700, whiteSpace: "nowrap" }}>{s.code}</span>
              <span style={{ fontSize: 15, color: "var(--c-text-dim)", flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</span>
              <span style={{ fontSize: 15, fontWeight: 700, whiteSpace: "nowrap",
                color: s.chg_pct >= 0 ? "#ff4d4d" : "#00c076" }}>
                {s.chg_pct >= 0 ? "+" : ""}{s.chg_pct.toFixed(2)}%
              </span>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>
            追蹤股池即時漲幅 · 點擊看個股
          </div>
        </Card>

        {/* 市場快訊 */}
        <Card title="市場快訊" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {[
            { time: "14:32", text: "輝達 CEO 黃仁勳確認台灣投資計畫", tag: "利多" },
            { time: "13:15", text: "台積電 6 月營收創歷史新高",        tag: "利多" },
            { time: "11:40", text: "聯準會官員發表鷹派言論",            tag: "注意" },
            { time: "09:05", text: "台幣升值 0.2 角，外資大幅匯入",     tag: "中性" },
          ].map((n, i) => {
            const tagColor =
              n.tag === "利多" ? "#00c076" : n.tag === "注意" ? "#f5a623" : "var(--c-text-dim)";
            return (
              <div key={i} style={{ padding: "7px 0", borderBottom: "1px solid #1a1a2a" }}>
                <div
                  style={{
                    display: "flex", gap: 6, alignItems: "center", marginBottom: 3,
                  }}
                >
                  <span style={{ fontSize: 22, color: "var(--c-text-dim)" }}>{n.time}</span>
                  <span
                    style={{
                      fontSize: 22, padding: "0 5px", borderRadius: 2,
                      border: `1px solid ${tagColor}55`, color: tagColor,
                    }}
                  >
                    {n.tag}
                  </span>
                </div>
                <div style={{ fontSize: 23, color: "var(--c-text-mid)", lineHeight: 1.5 }}>
                  {n.text}
                </div>
              </div>
            );
          })}
        </Card>

        {/* 台美連動 */}
        <Card title="台美連動分析" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {[
            { label: "NVDA ↔ 台積電",    corr: 0.82,  color: "#00c076" },
            { label: "費半 ↔ 半導體",    corr: 0.79,  color: "#00c076" },
            { label: "TSMC ADR ↔ 現貨", corr: 0.94,  color: "#00c076" },
            { label: "DXY ↔ 台幣",      corr: -0.71, color: "#ff4d4d" },
          ].map((c) => (
            <div key={c.label} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 15, color: "var(--c-text-dim)" }}>{c.label}</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: c.color }}>{c.corr}</span>
              </div>
              <div style={{ height: 3, background: "var(--c-border)", borderRadius: 2 }}>
                <div style={{ height: "100%", borderRadius: 2, background: c.color, width: `${Math.abs(c.corr) * 100}%` }} />
              </div>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 4 }}>60 日滾動相關係數 ｜ 每日更新</div>
        </Card>
      </div>
    </div>
  );
}
