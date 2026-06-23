"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSignalStream } from "@/hooks/useSignalStream";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

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

interface Stock {
  code: string; name: string; price: number | null; change_pct: number;
  volume_bn: number | null; vol_ratio: number | null;   // 量比（今日量/5日均量）
  rsi: number | null; ma_align: boolean | null;
  foreign_buy: boolean | null; ai_score: number | null; industry: string;
  limit_up: boolean; limit_down: boolean;     // 漲/跌停
  big_order_in: boolean | null;               // 大單流入
  gap_up: boolean | null;                     // 開盤跳空 >2%
}

const INDUSTRIES = ["全部", "半導體", "電子製造", "電子零組件", "航運", "金融", "光電", "PCB", "伺服器", "電商", "電腦", "鋼鐵", "汽車", "電信", "石化"];

const SORT_OPTIONS = [
  { value: "ai_score",   label: "AI評分" },
  { value: "change_pct", label: "漲跌幅" },
  { value: "volume_bn",  label: "成交額" },
  { value: "vol_ratio",  label: "量比" },
  { value: "rsi",        label: "RSI" },
];

const WL_KEY  = "tw_radar_watchlist";
const GRP_KEY = "tw_radar_wl_groups";

interface WlGroup { id: string; name: string; stocks: { code: string; name: string; price: number; change_pct: number; industry: string }[] }

const DEFAULT_GROUPS: WlGroup[] = [
  { id:"g1", name:"群組1", stocks:[] },
  { id:"g2", name:"群組2", stocks:[] },
  { id:"g3", name:"群組3", stocks:[] },
  { id:"g4", name:"群組4", stocks:[] },
  { id:"g5", name:"群組5", stocks:[] },
];

function loadWL(): string[] {
  try { return JSON.parse(localStorage.getItem(WL_KEY) || "[]"); } catch { return []; }
}

function loadGroups(): WlGroup[] {
  try { return JSON.parse(localStorage.getItem(GRP_KEY) || "null") || DEFAULT_GROUPS; } catch { return DEFAULT_GROUPS; }
}

function saveGroups(g: WlGroup[]) {
  localStorage.setItem(GRP_KEY, JSON.stringify(g));
}

// ── 群組選擇彈窗 ─────────────────────────────────────────────
function GroupPickerModal({
  stock,
  onClose,
  onPicked,
}: {
  stock: Stock;
  onClose: () => void;
  onPicked: (stock: Stock) => void;
}) {
  const groups = loadGroups();
  const addToGroup = (gId: string) => {
    const updated = groups.map(g => {
      if (g.id !== gId) return g;
      if (g.stocks.some(s => s.code === stock.code)) return g;
      return {
        ...g,
        stocks: [...g.stocks, {
          code: stock.code, name: stock.name,
          price: stock.price ?? 0, change_pct: stock.change_pct, industry: stock.industry,
        }],
      };
    });
    saveGroups(updated);
    onPicked(stock);
  };

  return (
    <div
      onClick={onClose}
      style={{
        position:"fixed", inset:0, background:"#00000088", zIndex:1000,
        display:"flex", alignItems:"center", justifyContent:"center",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background:"var(--c-bg-card)", border:"1px solid #3a3a5a", borderRadius:12,
          padding:"20px 24px", minWidth:260, boxShadow:"0 8px 32px #000a",
        }}
      >
        <div style={{ fontSize:14, fontWeight:700, color:"var(--c-text)", marginBottom:4 }}>
          加入自選收藏
        </div>
        <div style={{ fontSize:12, color:"var(--c-text-dim)", marginBottom:14 }}>
          {stock.name} ({stock.code}) → 選擇群組
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {groups.map(g => (
            <button
              key={g.id}
              onClick={() => addToGroup(g.id)}
              style={{
                background:"var(--c-bg-deep)", border:"1px solid var(--c-border)",
                borderRadius:8, padding:"10px 14px", cursor:"pointer",
                color:"#c8c8e8", fontSize:13, textAlign:"left",
                display:"flex", justifyContent:"space-between", alignItems:"center",
              }}
              onMouseEnter={e => (e.currentTarget.style.background='var(--c-bg-deep)')}
              onMouseLeave={e => (e.currentTarget.style.background="var(--c-bg-deep)")}
            >
              <span>⭐ {g.name}</span>
              <span style={{ fontSize:11, color:"var(--c-text-dim)" }}>{g.stocks.length} 檔</span>
            </button>
          ))}
        </div>
        <button
          onClick={onClose}
          style={{
            marginTop:12, width:"100%", background:"transparent",
            border:"1px solid var(--c-border)", borderRadius:6,
            color:"var(--c-text-dim)", fontSize:12, padding:"6px 0", cursor:"pointer",
          }}
        >
          取消
        </button>
      </div>
    </div>
  );
}

function scoreColor(s: number) {
  if (s >= 80) return "#ff4d4d";
  if (s >= 65) return "#f5a623";
  if (s >= 50) return "var(--c-text-dim)";
  if (s >= 35) return "#3d7eff";
  return "#00c076";
}
function scoreLabel(s: number) {
  if (s >= 80) return "強力買進";
  if (s >= 65) return "買進";
  if (s >= 50) return "觀望";
  if (s >= 35) return "減碼";
  return "賣出";
}
function volRatioColor(r: number) {
  if (r >= 5) return "#ff4d4d";
  if (r >= 3) return "#f5a623";
  if (r >= 1.5) return "var(--c-text)";
  return "var(--c-text-dim)";
}

function Tag({ label, val, color }: { label: string; val: string; color: string }) {
  return (
    <div style={{ display:"flex", gap:4, alignItems:"center", background:"var(--c-bg-deep)", borderRadius:5, padding:"3px 7px" }}>
      <span style={{ fontSize:11, color:"var(--c-text-dim)" }}>{label}</span>
      <span style={{ fontSize:12, fontWeight:600, color }}>{val}</span>
    </div>
  );
}

function Chip({ label, active, onClick, accent }: { label:string; active:boolean; onClick:()=>void; accent?:string }) {
  const c = accent ?? "#00c076";
  return (
    <button onClick={onClick} style={{
      padding:"4px 12px", borderRadius:16, fontSize:12, cursor:"pointer",
      background: active ? `${c}22` : "var(--c-bg-deep)",
      color: active ? c : "var(--c-text-dim)",
      border:`1px solid ${active ? c : "var(--c-border)"}`,
      fontWeight: active ? 600 : 400,
    }}>
      {active ? "✓ " : ""}{label}
    </button>
  );
}

function GroupLabel({ label }: { label: string }) {
  return <span style={{ fontSize:11, color:"#444460", letterSpacing:1, whiteSpace:"nowrap", padding:"0 4px" }}>{label}</span>;
}

interface LiveStock { symbol: string; name: string; close: number; change: number; change_pct: number; volume_lot: number; }

export default function ScreenerPage() {
  const router = useRouter();
  const isMobile = useIsMobile();
  const { signals, connected } = useSignalStream();
  const [industry,      setIndustry]      = useState("全部");
  const [sortBy,        setSortBy]        = useState("ai_score");
  const [filterMA,      setFilterMA]      = useState(false);
  const [filterForeign, setFilterForeign] = useState(false);
  const [filterRSI,     setFilterRSI]     = useState(false);
  // 當沖特化
  const [filterVolume,  setFilterVolume]  = useState(false);
  const [filterLimitUp, setFilterLimitUp] = useState(false);
  const [filterLimitDn, setFilterLimitDn] = useState(false);
  const [filterBigOrder,setFilterBigOrder]= useState(false);
  const [filterGapUp,   setFilterGapUp]   = useState(false);
  const [filterOverbought,setFilterOverbought] = useState(false);
  const [filterOversold,  setFilterOversold]   = useState(false);
  // K線形態 & 主力意圖
  const [selectedPatterns, setSelectedPatterns] = useState<string[]>([]);
  const [selectedPhase,    setSelectedPhase]    = useState("全部");
  // RWD: 手機篩選摺疊
  const [filterOpen, setFilterOpen] = useState(true);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [tab, setTab] = useState<"scan" | "watchlist">("scan");
  const [pickerStock, setPickerStock] = useState<Stock | null>(null);

  // Live scan
  const [liveStocks, setLiveStocks] = useState<LiveStock[] | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState("");

  // 因子掃描卡片（真實資料）
  const [scanStocks, setScanStocks] = useState<Stock[]>([]);

  useEffect(() => { setWatchlist(loadWL()); }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/screener/factor-scan?limit=100`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.stocks) setScanStocks(d.stocks as Stock[]); })
      .catch(() => {});
  }, []);

  const runLiveScan = useCallback(async () => {
    setLiveLoading(true); setLiveError(""); setLiveStocks(null);
    const strategy = filterForeign ? "foreign_consec"
      : filterMA ? "ma20_breakout"
      : filterRSI ? (filterOversold ? "rsi_oversold" : filterOverbought ? "rsi_oversold" : undefined)
      : undefined;
    const body: Record<string, unknown> = {
      min_volume_lot: filterVolume ? 3000 : 500,
      limit: 100,
    };
    if (strategy) body.strategy = strategy;
    if (filterLimitUp) body.min_change_pct = 9.5;
    if (filterLimitDn) body.max_change_pct = -9.5;
    if (selectedPatterns.length > 0) body.patterns = selectedPatterns.join(",");
    if (selectedPhase !== "全部") body.phase = selectedPhase;
    try {
      const res = await fetch(`${API_BASE}/api/screener/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      setLiveStocks(data.stocks ?? []);
    } catch (e) {
      setLiveError(e instanceof Error ? e.message : "掃描失敗");
    } finally {
      setLiveLoading(false);
    }
  }, [filterForeign, filterMA, filterRSI, filterOversold, filterOverbought, filterVolume, filterLimitUp, filterLimitDn, selectedPatterns, selectedPhase]);

  const handleStarClick = (s: Stock) => {
    if (watchlist.includes(s.code)) {
      // 已收藏 → 直接移除
      const next = watchlist.filter(c => c !== s.code);
      setWatchlist(next);
      localStorage.setItem(WL_KEY, JSON.stringify(next));
    } else {
      // 未收藏 → 開彈窗選群組
      setPickerStock(s);
    }
  };

  const handleGroupPicked = (stock: Stock) => {
    // 加入 screener WL pool（讓按鈕變 ★）
    const next = [...watchlist, stock.code];
    setWatchlist(next);
    localStorage.setItem(WL_KEY, JSON.stringify(next));
    setPickerStock(null);
  };

  let filtered = scanStocks;
  if (tab === "watchlist")     filtered = filtered.filter(s => watchlist.includes(s.code));
  if (industry !== "全部")     filtered = filtered.filter(s => s.industry === industry);
  if (filterMA)                filtered = filtered.filter(s => s.ma_align === true);
  if (filterForeign)           filtered = filtered.filter(s => s.foreign_buy === true);
  if (filterRSI)               filtered = filtered.filter(s => s.rsi != null && s.rsi >= 50 && s.rsi < 70);
  if (filterVolume)            filtered = filtered.filter(s => s.vol_ratio != null && s.vol_ratio >= 3);
  if (filterLimitUp)           filtered = filtered.filter(s => s.limit_up);
  if (filterLimitDn)           filtered = filtered.filter(s => s.limit_down);
  if (filterBigOrder)          filtered = filtered.filter(s => s.big_order_in === true);
  if (filterGapUp)             filtered = filtered.filter(s => s.gap_up === true);
  if (filterOverbought)        filtered = filtered.filter(s => s.rsi != null && s.rsi >= 70);
  if (filterOversold)          filtered = filtered.filter(s => s.rsi != null && s.rsi <= 30);

  // 漲跌停排行優先顯示時按量比排
  const effectiveSort = filterLimitUp || filterLimitDn || filterVolume ? "vol_ratio" : sortBy;
  filtered = [...filtered].sort((a, b) =>
    ((b[effectiveSort as keyof Stock] as number) ?? -Infinity) - ((a[effectiveSort as keyof Stock] as number) ?? -Infinity)
  );

  return (
    <div className="main-scroll" style={{ flex:1, overflowY:"auto", padding: isMobile ? "8px 8px 72px" : "16px 20px" }}>
      {pickerStock && (
        <GroupPickerModal
          stock={pickerStock}
          onClose={() => setPickerStock(null)}
          onPicked={handleGroupPicked}
        />
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h2 style={{ fontSize:18, fontWeight:700, color:"var(--c-text)" }}>📊 選股工作流</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: connected ? "#00c076" : "#555", display: "inline-block" }} />
          <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>即時訊號</span>
          {signals.length > 0 && (
            <span style={{
              background: "#ef4444", color: "#fff", borderRadius: 10,
              fontSize: 11, padding: "1px 7px", fontWeight: 700,
            }}>{signals.length}</span>
          )}
        </div>
      </div>
      {signals.length > 0 && (
        <div style={{
          background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
          borderRadius: 8, padding: "10px 14px", marginBottom: 14,
          maxHeight: 120, overflowY: "auto",
        }}>
          {signals.slice(0, 5).map(s => (
            <div key={s.signal_id} style={{ fontSize: 13, color: "var(--c-text)", marginBottom: 4, display: "flex", gap: 12 }}>
              <span style={{ color: s.action === "buy" ? "#00c076" : "#ef4444", fontWeight: 600 }}>
                {s.action === "buy" ? "▲買" : "▼賣"} {s.symbol}
              </span>
              <span style={{ color: "var(--c-text-dim)" }}>{s.quantity}股 | 信心 {(s.ai_confidence * 100).toFixed(0)}%</span>
              <span style={{ color: "var(--c-text-dim)", fontSize: 11 }}>{s.timestamp}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tab */}
      <div style={{ display:"flex", gap:8, marginBottom:14 }}>
        {(["scan","watchlist"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding:"6px 18px", borderRadius:20, fontSize:13, fontWeight:600, cursor:"pointer",
            background: tab === t ? "#00c076" : "var(--c-bg-deep)",
            color: tab === t ? "#000" : "var(--c-text-dim)",
            border:"1px solid " + (tab === t ? "#00c076" : "var(--c-border)"),
          }}>
            {t === "scan" ? `因子掃描 (${scanStocks.length})` : `自選股池 (${watchlist.length})`}
          </button>
        ))}
      </div>

      {/* ── 篩選列 ── */}
      {isMobile && (
        <button onClick={() => setFilterOpen(v => !v)} style={{
          width:"100%", padding:"8px 14px", borderRadius:8, marginBottom:6,
          background:"var(--c-bg-card)", border:"1px solid var(--c-border)",
          color:"var(--c-text-dim)", fontSize:13, cursor:"pointer", textAlign:"left",
        }}>
          {filterOpen ? "▲ 收起篩選" : "▼ 展開篩選"}
        </button>
      )}
      {(!isMobile || filterOpen) && <div style={{
        background:"var(--c-bg-card)", border:"1px solid var(--c-border)", borderRadius:10,
        padding:"12px 14px", marginBottom:14,
        display:"flex", flexWrap:"wrap", gap:8, alignItems:"center",
      }}>
        {/* 產業 + 排序 */}
        <select value={industry} onChange={e => setIndustry(e.target.value)} style={{
          background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:6,
          color:"var(--c-text)", fontSize:13, padding:"5px 8px",
        }}>
          {INDUSTRIES.map(i => <option key={i}>{i}</option>)}
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
          background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:6,
          color:"var(--c-text)", fontSize:13, padding:"5px 8px",
        }}>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}排序</option>)}
        </select>

        {/* 分隔 */}
        <div style={{ width:1, height:20, background:"var(--c-border)", margin:"0 4px" }} />

        {/* 技術面 */}
        <GroupLabel label="技術▸" />
        <Chip label="均線多排" active={filterMA}      onClick={() => setFilterMA(v => !v)} />
        <Chip label="外資買超" active={filterForeign} onClick={() => setFilterForeign(v => !v)} />
        <Chip label="RSI 50-70" active={filterRSI}    onClick={() => setFilterRSI(v => !v)} />

        {/* 分隔 */}
        <div style={{ width:1, height:20, background:"var(--c-border)", margin:"0 4px" }} />

        {/* 當沖特化 */}
        <GroupLabel label="當沖▸" />
        <Chip label="🔥 量爆 3x+"  active={filterVolume}   onClick={() => setFilterVolume(v => !v)}   accent="#f5a623" />
        <Chip label="🚀 漲停"       active={filterLimitUp}  onClick={() => { setFilterLimitUp(v => !v); setFilterLimitDn(false); }} accent="#ff4d4d" />
        <Chip label="💀 跌停"       active={filterLimitDn}  onClick={() => { setFilterLimitDn(v => !v); setFilterLimitUp(false); }} accent="#00c076" />
        <Chip label="💰 大單流入"   active={filterBigOrder} onClick={() => setFilterBigOrder(v => !v)} accent="#cc44ff" />
        <Chip label="⬆ 開盤跳空"   active={filterGapUp}    onClick={() => setFilterGapUp(v => !v)}    accent="#3d7eff" />
        <Chip label="📈 超買動能"   active={filterOverbought} onClick={() => { setFilterOverbought(v=>!v); setFilterOversold(false); }} accent="#ff6b35" />
        <Chip label="📉 超賣反彈"   active={filterOversold}   onClick={() => { setFilterOversold(v=>!v); setFilterOverbought(false); }} accent="#3d7eff" />

        {/* 分隔 */}
        <div style={{ width:1, height:20, background:"var(--c-border)", margin:"0 4px" }} />

        {/* K線形態 */}
        <GroupLabel label="K線▸" />
        {["吞噬", "錘頭", "射擊之星", "晨星", "暮星", "十字星", "紡錘", "長下影線", "長上影線"].map(p => {
          const active = selectedPatterns.includes(p);
          return (
            <button key={p} onClick={() => setSelectedPatterns(prev =>
              prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
            )} style={{
              padding:"4px 10px", borderRadius:16, fontSize:12, cursor:"pointer",
              background: active ? "#cc44ff22" : "var(--c-bg-deep)",
              color: active ? "#cc44ff" : "var(--c-text-dim)",
              border:`1px solid ${active ? "#cc44ff" : "var(--c-border)"}`,
              fontWeight: active ? 600 : 400,
            }}>
              {active ? "✓ " : ""}{p}
            </button>
          );
        })}

        {/* 分隔 */}
        <div style={{ width:1, height:20, background:"var(--c-border)", margin:"0 4px" }} />

        {/* 主力意圖 */}
        <GroupLabel label="主力▸" />
        <select value={selectedPhase} onChange={e => setSelectedPhase(e.target.value)} style={{
          background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:6,
          color: selectedPhase !== "全部" ? "#f5a623" : "var(--c-text-dim)", fontSize:13, padding:"5px 8px",
        }}>
          {["全部","吸籌","拉抬","出貨","打壓","觀望"].map(p => <option key={p}>{p}</option>)}
        </select>

        <span style={{ marginLeft:"auto", fontSize:12, color:"var(--c-text-dim)" }}>共 {filtered.length} 檔</span>
      </div>}

      {/* ── 卡片列表 ── */}
      {filtered.length === 0 ? (
        <div style={{ textAlign:"center", color:"var(--c-text-dim)", padding:"60px 0", fontSize:15 }}>
          {tab === "watchlist" ? "自選股池是空的，從「因子掃描」點 ☆ 加入" : "沒有符合條件的股票"}
        </div>
      ) : (
        <div style={{
          display:"grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fill, minmax(320px, 1fr))",
          gap:12,
        }}>
          {filtered.map(s => {
            const inWatch = watchlist.includes(s.code);
            const up = s.change_pct >= 0;
            const isLimit = s.limit_up || s.limit_down;
            return (
              <div key={s.code}
                onClick={() => router.push(`/stock?s=${s.code}`)}
                style={{
                background:"var(--c-bg-card)",
                border:`1px solid ${s.limit_up ? "#ff4d4d55" : s.limit_down ? "#00c07655" : "var(--c-border)"}`,
                borderRadius:10, padding:"14px 16px",
                display:"flex", flexDirection:"column", gap:10,
                boxShadow: s.limit_up ? "0 0 12px #ff4d4d22" : s.limit_down ? "0 0 12px #00c07622" : "none",
                cursor:"pointer",
              }}>
                {/* Header */}
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                    <span style={{ fontWeight:700, fontSize:16, color:"var(--c-text)" }}>{s.name}</span>
                    <span style={{ fontSize:13, color:"var(--c-text-dim)" }}>{s.code}</span>
                    <span style={{ fontSize:11, padding:"2px 6px", borderRadius:4, background:"var(--c-bg-deep)", color:"var(--c-text-dim)" }}>{s.industry}</span>
                    {s.limit_up  && <span style={{ fontSize:11, padding:"1px 6px", borderRadius:4, background:"#ff4d4d33", color:"#ff4d4d", fontWeight:700 }}>漲停</span>}
                    {s.limit_down && <span style={{ fontSize:11, padding:"1px 6px", borderRadius:4, background:"#00c07633", color:"#00c076", fontWeight:700 }}>跌停</span>}
                    {s.gap_up    && !isLimit && <span style={{ fontSize:11, padding:"1px 6px", borderRadius:4, background:"#3d7eff33", color:"#3d7eff" }}>跳空</span>}
                  </div>
                  <button onClick={e => { e.stopPropagation(); handleStarClick(s); }} style={{
                    background: inWatch ? "#003d20" : "var(--c-bg-deep)",
                    border:`1px solid ${inWatch ? "#00c076" : "var(--c-border)"}`,
                    borderRadius:6, color: inWatch ? "#00c076" : "var(--c-text-dim)",
                    fontSize:12, padding:"3px 8px", cursor:"pointer", flexShrink:0,
                  }}>
                    {inWatch ? "★ 自選" : "☆ 加入"}
                  </button>
                </div>

                {/* 價格 */}
                <div style={{ display:"flex", gap:16, alignItems:"baseline" }}>
                  <span style={{ fontSize:22, fontWeight:700, color:"var(--c-text)" }}>{s.price != null ? s.price.toLocaleString() : "—"}</span>
                  <span style={{ fontSize:15, color: up ? "#ff4d4d" : "#00c076", fontWeight:600 }}>
                    {up ? "▲" : "▼"} {Math.abs(s.change_pct).toFixed(2)}%
                  </span>
                  {s.volume_bn != null && <span style={{ fontSize:13, color:"var(--c-text-dim)", marginLeft:"auto" }}>量 {s.volume_bn.toFixed(1)}億</span>}
                </div>

                {/* 指標標籤 */}
                <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
                  {s.rsi != null && <Tag label="RSI"   val={s.rsi.toFixed(1)} color={s.rsi>=70?"#ff4d4d":s.rsi<=30?"#3d7eff":"#f5a623"} />}
                  {s.vol_ratio != null && <Tag label="量比"  val={`${s.vol_ratio.toFixed(1)}x`} color={volRatioColor(s.vol_ratio)} />}
                  {s.ma_align != null && <Tag label="均線"  val={s.ma_align?"多排":"空排"}  color={s.ma_align?"#00c076":"#ff4d4d"} />}
                  {s.foreign_buy != null && <Tag label="外資"  val={s.foreign_buy?"連買":"流出"} color={s.foreign_buy?"#00c076":"#ff4d4d"} />}
                  {s.big_order_in && <Tag label="大單" val="流入" color="#cc44ff" />}
                </div>

                {/* AI評分 */}
                {s.ai_score != null ? (
                  <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                    <div style={{ flex:1, height:6, background:"var(--c-bg-deep)", borderRadius:3, overflow:"hidden" }}>
                      <div style={{ width:`${s.ai_score}%`, height:"100%", background:scoreColor(s.ai_score), borderRadius:3 }} />
                    </div>
                    <span style={{ fontSize:13, color:scoreColor(s.ai_score), fontWeight:700, width:28, textAlign:"right" }}>{s.ai_score}</span>
                    <span style={{ fontSize:12, color:scoreColor(s.ai_score), width:54 }}>{scoreLabel(s.ai_score)}</span>
                  </div>
                ) : (
                  <div style={{ fontSize:11, color:"var(--c-text-dim)" }}>AI 評分尚未產生</div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Live 掃描區 */}
      <div style={{ marginTop:20, background:"var(--c-bg-card)", border:"1px solid var(--c-border)", borderRadius:10, padding:"14px 16px" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
          <span style={{ fontSize:13, fontWeight:600, color:"var(--c-text-dim)", letterSpacing:0.8, textTransform:"uppercase" }}>
            Live 全市場掃描
          </span>
          <button onClick={runLiveScan} disabled={liveLoading} style={{
            background: liveLoading ? "var(--c-bg-deep)" : "#001a40",
            border:`1px solid ${liveLoading ? "var(--c-border)" : "#3d7eff55"}`,
            borderRadius:6, color: liveLoading ? "var(--c-text-dim)" : "#3d7eff",
            fontSize:13, padding:"6px 18px", cursor: liveLoading ? "not-allowed" : "pointer", fontWeight:600,
          }}>
            {liveLoading ? "掃描中…" : "▶ 套用條件掃描"}
          </button>
        </div>
        {liveError && <div style={{ fontSize:12, color:"#ff4d4d", marginBottom:8 }}>⚠ {liveError}</div>}
        {liveStocks === null && !liveLoading && (
          <div style={{ fontSize:12, color:"var(--c-text-dim)" }}>
            點擊「套用條件掃描」從後端即時掃描全市場，結果按成交量排序。
          </div>
        )}
        {liveStocks !== null && liveStocks.length === 0 && (
          <div style={{ fontSize:13, color:"var(--c-text-dim)" }}>無符合條件的股票。</div>
        )}
        {liveStocks && liveStocks.length > 0 && (
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
              <thead>
                <tr style={{ color:"var(--c-text-dim)", borderBottom:"1px solid var(--c-border)" }}>
                  {["代號","名稱","收盤","漲跌%","成交(張)"].map(h => (
                    <th key={h} style={{ padding:"4px 10px", textAlign:"right", fontWeight:500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {liveStocks.map(s => {
                  const up = s.change_pct >= 0;
                  return (
                    <tr key={s.symbol} style={{ borderBottom:"1px solid #1a1a2a" }}>
                      <td style={{ padding:"5px 10px", textAlign:"right", color:"#3d7eff", fontWeight:700 }}>{s.symbol}</td>
                      <td style={{ padding:"5px 10px", textAlign:"right", color:"var(--c-text-mid)" }}>{s.name}</td>
                      <td style={{ padding:"5px 10px", textAlign:"right", color:"var(--c-text)" }}>{s.close.toLocaleString()}</td>
                      <td style={{ padding:"5px 10px", textAlign:"right", color: up ? "#ff4d4d" : "#00c076", fontWeight:600 }}>
                        {up ? "+" : ""}{s.change_pct.toFixed(2)}%
                      </td>
                      <td style={{ padding:"5px 10px", textAlign:"right", color:"var(--c-text-dim)" }}>{s.volume_lot.toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div style={{ fontSize:11, color:"var(--c-text-dim)", marginTop:8 }}>共 {liveStocks.length} 檔 · 資料來源：TWSE OpenAPI</div>
          </div>
        )}
      </div>
    </div>
  );
}
