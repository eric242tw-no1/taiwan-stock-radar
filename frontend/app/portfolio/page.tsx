"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";

// ── 台灣色彩慣例（紅漲綠跌）────────────────────────────────────
const TW_COLORS = {
  up:      "#ff4d4d",   // 漲 / 獲利
  down:    "#00c076",   // 跌 / 虧損
  neutral: "#8888aa",
} as const;

function twColor(val: number) {
  return val > 0 ? TW_COLORS.up : val < 0 ? TW_COLORS.down : TW_COLORS.neutral;
}

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

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── 型別 ────────────────────────────────────────────────────────
interface Holding {
  id: number;
  code: string;
  name: string;
  qty: number;
  cost: number;
  buy_date: string;
  note: string;
  current?: number;
}

interface YuantaPosition {
  symbol: string;
  name?: string;
  quantity: number;
  avg_cost?: number;
  current_price?: number;
  pnl?: number;
}

interface YuantaSummary {
  total_value: number;
  cash: number;
  margin_usage: number;
}

interface ParsedPos { code: string; name: string; qty: number; cost: number; current_price?: number }

function pnl(p: Holding) {
  const cur = p.current ?? p.cost;
  const diff = (cur - p.cost) * p.qty * 1000;
  const pct = ((cur - p.cost) / p.cost) * 100;
  return { diff, pct };
}

function fmt(n: number) {
  return n >= 0 ? `+${n.toLocaleString()}` : n.toLocaleString();
}

// ── 截圖辨識 Modal ────────────────────────────────────────────────────────────
function OcrModal({ onClose, onImport }: { onClose: () => void; onImport: (list: ParsedPos[]) => void }) {
  const [file, setFile]         = useState<File | null>(null);
  const [preview, setPreview]   = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<ParsedPos[] | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const handleFile = (f: File) => {
    setFile(f); setResult(null); setError(null);
    setPreview(URL.createObjectURL(f));
  };

  const upload = async () => {
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/api/portfolio/parse-screenshot`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "解析失敗");
      setResult(data.positions);
      setSelected(new Set(data.positions.map((_: unknown, i: number) => i)));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const toggleSel = (i: number) => setSelected(prev => { const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s; });

  return (
    <div onClick={onClose} style={{ position:"fixed", inset:0, background:"#00000099", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center", padding:16 }}>
      <div onClick={e => e.stopPropagation()} style={{ background:"#111118", border:"1px solid #3a3a5a", borderRadius:14, padding:"24px", width:"100%", maxWidth:520, boxShadow:"0 8px 40px #000c", overflowY:"auto", maxHeight:"90vh" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:18 }}>
          <div>
            <div style={{ fontSize:16, fontWeight:800, color:"#e8e8f0" }}>📷 上傳對帳單截圖</div>
            <div style={{ fontSize:11, color:"#8888aa", marginTop:2 }}>支援元大、富邦等券商 App 截圖，自動辨識持倉</div>
          </div>
          <button onClick={onClose} style={{ background:"transparent", border:"none", color:"#555570", fontSize:18, cursor:"pointer" }}
            onMouseEnter={e => (e.currentTarget.style.color="#e8e8f0")} onMouseLeave={e => (e.currentTarget.style.color="#555570")}>✕</button>
        </div>

        {!preview ? (
          <div onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith("image/")) handleFile(f); }}
            onDragOver={e => e.preventDefault()}
            style={{ border:"2px dashed #3a3a5a", borderRadius:10, padding:"32px 16px", textAlign:"center", cursor:"pointer", marginBottom:16 }}
            onMouseEnter={e => (e.currentTarget.style.borderColor="#3d7eff")} onMouseLeave={e => (e.currentTarget.style.borderColor="#3a3a5a")}
            onClick={() => document.getElementById("ocr-file-input")?.click()}>
            <div style={{ fontSize:32, marginBottom:8 }}>📂</div>
            <div style={{ fontSize:14, color:"#8888aa" }}>點擊或拖曳圖片至此</div>
            <div style={{ fontSize:11, color:"#555570", marginTop:4 }}>PNG / JPG，最大 10MB</div>
            <input id="ocr-file-input" type="file" accept="image/*" style={{ display:"none" }}
              onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
          </div>
        ) : (
          <div style={{ marginBottom:16, position:"relative" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="preview" style={{ width:"100%", borderRadius:8, border:"1px solid #2a2a3a", maxHeight:220, objectFit:"contain", background:"#0d0d15" }} />
            <button onClick={() => { setPreview(null); setFile(null); setResult(null); setError(null); }}
              style={{ position:"absolute", top:6, right:6, background:"#00000099", border:"none", color:"#e8e8f0", borderRadius:20, width:24, height:24, cursor:"pointer", fontSize:12 }}>✕</button>
          </div>
        )}

        {file && !result && (
          <button onClick={upload} disabled={loading} style={{ width:"100%", padding:"10px 0", borderRadius:8, background: loading ? "#1a1a24" : "#3d7eff", color: loading ? "#555570" : "#fff", border:"none", fontSize:14, fontWeight:700, cursor: loading ? "not-allowed" : "pointer", marginBottom:16 }}>
            {loading ? "⏳ AI 辨識中…" : "🔍 開始辨識"}
          </button>
        )}
        {error && <div style={{ padding:"10px 14px", borderRadius:8, marginBottom:16, background:"#3d0000", border:"1px solid #ff4d4d44", fontSize:13, color:"#ff4d4d" }}>{error}</div>}

        {result && (
          <>
            <div style={{ fontSize:13, color:"#8888aa", marginBottom:8 }}>辨識到 <span style={{ color:TW_COLORS.down, fontWeight:700 }}>{result.length}</span> 筆持倉，勾選後匯入：</div>
            <div style={{ display:"flex", flexDirection:"column", gap:6, marginBottom:16 }}>
              {result.map((p, i) => (
                <div key={i} onClick={() => toggleSel(i)} style={{ display:"flex", alignItems:"center", gap:10, background: selected.has(i) ? "#1a2a3a" : "#0d0d15", border:`1px solid ${selected.has(i) ? "#3d7eff44" : "#2a2a3a"}`, borderRadius:8, padding:"10px 12px", cursor:"pointer" }}>
                  <div style={{ width:16, height:16, borderRadius:3, border:`2px solid ${selected.has(i) ? "#3d7eff" : "#3a3a5a"}`, background: selected.has(i) ? "#3d7eff" : "transparent", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, color:"#fff" }}>{selected.has(i) ? "✓" : ""}</div>
                  <div style={{ flex:1 }}>
                    <span style={{ fontSize:14, fontWeight:700, color:"#3d7eff" }}>{p.code}</span>
                    <span style={{ fontSize:13, color:"#c8c8d8", marginLeft:8 }}>{p.name}</span>
                  </div>
                  <div style={{ fontSize:12, color:"#8888aa", textAlign:"right" }}>
                    <div>{p.qty} 張</div><div>成本 {p.cost.toLocaleString()}</div>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={() => { if (result) onImport(result.filter((_, i) => selected.has(i))); onClose(); }} disabled={selected.size === 0}
              style={{ width:"100%", padding:"10px 0", borderRadius:8, background: selected.size > 0 ? TW_COLORS.down : "#1a1a24", color: selected.size > 0 ? "#000" : "#555570", border:"none", fontSize:14, fontWeight:700, cursor: selected.size > 0 ? "pointer" : "not-allowed" }}>
              匯入 {selected.size} 筆持倉
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Yuanta 即時持倉 Tab ────────────────────────────────────────────
function YuantaTab() {
  const [positions, setPositions]   = useState<YuantaPosition[]>([]);
  const [summary, setSummary]       = useState<YuantaSummary | null>(null);
  const [simulation, setSimulation] = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [updatedAt, setUpdatedAt]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const esRef = useRef<EventSource | null>(null);

  const fetchOnce = useCallback(async () => {
    try {
      const [posRes, sumRes] = await Promise.all([
        fetch(`${API}/api/portfolio/positions`),
        fetch(`${API}/api/portfolio/summary`),
      ]);
      const posData = await posRes.json();
      const sumData = await sumRes.json();
      setPositions(posData.positions ?? []);
      setSummary({ total_value: sumData.total_value, cash: sumData.cash, margin_usage: sumData.margin_usage });
      setSimulation(posData.simulation ?? true);
      setUpdatedAt(posData.updated_at ?? null);
      setError(posData.error || sumData.error || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "連線失敗");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOnce();

    // 30s polling fallback
    const timer = setInterval(fetchOnce, 30_000);

    // SSE push（優先）
    const es = new EventSource(`${API}/api/stream/portfolio`);
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        setPositions(d.positions ?? []);
        if (d.summary) setSummary(d.summary);
        setSimulation(d.simulation ?? true);
        setUpdatedAt(d.updated_at ?? null);
        setError(d.error || null);
        setLoading(false);
      } catch { /* ignore parse error */ }
    };
    es.onerror = () => setError("SSE 連線中斷，使用輪詢模式");

    return () => {
      clearInterval(timer);
      es.close();
    };
  }, [fetchOnce]);

  if (loading) return <div style={{ textAlign:"center", color:"#8888aa", padding:"60px 0" }}>載入元大持倉…</div>;

  const totalPnL = positions.reduce((s, p) => s + (p.pnl ?? 0), 0);

  return (
    <div>
      {/* Simulation / 錯誤 Badge */}
      <div style={{ display:"flex", gap:8, marginBottom:12, alignItems:"center", flexWrap:"wrap" }}>
        {simulation && (
          <span style={{ fontSize:11, background:"#1a2a1a", border:"1px solid #00c07644", borderRadius:20, padding:"2px 10px", color:TW_COLORS.down }}>
            模擬模式
          </span>
        )}
        {error && (
          <span style={{ fontSize:11, background:"#3d0000", border:"1px solid #ff4d4d44", borderRadius:20, padding:"2px 10px", color:TW_COLORS.up }}>
            ⚠ {error}
          </span>
        )}
        {updatedAt && (
          <span style={{ fontSize:11, color:"#555570", marginLeft:"auto" }}>更新：{updatedAt}</span>
        )}
      </div>

      {/* 帳戶摘要 */}
      {summary && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:10, marginBottom:16 }}>
          {[
            { label:"帳戶市值", val:`${(summary.total_value/10000).toFixed(1)}萬`, color:"#e8e8f0" },
            { label:"可用現金", val:`${(summary.cash/10000).toFixed(1)}萬`,         color:"#e8e8f0" },
            { label:"保證金",   val:`${(summary.margin_usage*100).toFixed(1)}%`,    color: summary.margin_usage > 0.8 ? TW_COLORS.up : "#e8e8f0" },
          ].map(c => (
            <div key={c.label} style={{ background:"#111118", border:"1px solid #2a2a3a", borderRadius:10, padding:"12px 14px" }}>
              <div style={{ fontSize:11, color:"#8888aa", marginBottom:4 }}>{c.label}</div>
              <div style={{ fontSize:18, fontWeight:700, color:c.color }}>{c.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* 持倉列表 */}
      {positions.length === 0 ? (
        <div style={{ textAlign:"center", color:"#8888aa", padding:"40px 0" }}>
          {simulation ? "模擬模式無持倉資料" : "目前無持倉"}
        </div>
      ) : (
        <>
          <div style={{ fontSize:13, color:"#8888aa", marginBottom:8 }}>
            共 {positions.length} 檔　總損益：
            <span style={{ fontWeight:700, color:twColor(totalPnL) }}>{fmt(Math.round(totalPnL))}</span>
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {positions.map((p, i) => {
              const cost = p.avg_cost ?? 0;
              const cur  = p.current_price ?? cost;
              const diff = (cur - cost) * p.quantity;
              const pct  = cost > 0 ? ((cur - cost) / cost) * 100 : 0;
              return (
                <div key={i} style={{ background:"#111118", border:"1px solid #2a2a3a", borderRadius:10, padding:"14px 16px" }}>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
                    <div>
                      <span style={{ fontWeight:700, fontSize:15, color:"#e8e8f0" }}>{p.name || p.symbol}</span>
                      <span style={{ fontSize:13, color:"#8888aa", marginLeft:8 }}>{p.symbol}</span>
                      <div style={{ fontSize:12, color:"#8888aa", marginTop:4 }}>
                        {p.quantity} 股　成本 <span style={{ color:"#e8e8f0" }}>{cost.toLocaleString()}</span>
                        　現價 <span style={{ color:"#e8e8f0" }}>{cur.toLocaleString()}</span>
                      </div>
                    </div>
                    <div style={{ textAlign:"right" }}>
                      <div style={{ fontSize:18, fontWeight:700, color:twColor(diff) }}>{fmt(Math.round(diff))}</div>
                      <div style={{ fontSize:13, color:twColor(pct) }}>{pct >= 0 ? "+" : ""}{pct.toFixed(2)}%</div>
                    </div>
                  </div>
                  {cur !== cost && (
                    <div style={{ marginTop:8, height:4, background:"#1a1a24", borderRadius:2, overflow:"hidden" }}>
                      <div style={{ width:`${Math.min(Math.abs(pct)*3,100)}%`, height:"100%", background:twColor(pct), borderRadius:2 }} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── 主頁面 ────────────────────────────────────────────────────────
export default function PortfolioPage() {
  const isMobile = useIsMobile();
  const router   = useRouter();

  const [tab, setTab]           = useState<"manual" | "yuanta">("manual");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm]         = useState({ code:"", name:"", qty:"", cost:"", buy_date:"", note:"" });
  const [editId, setEditId]     = useState<number | null>(null);
  const [showOcr, setShowOcr]   = useState(false);
  const [saving, setSaving]     = useState(false);

  const loadHoldings = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/portfolio`);
      if (!res.ok) return;
      const data = await res.json();
      const list: Holding[] = data.holdings ?? [];
      if (list.length > 0) {
        const codes = list.map(h => h.code).join(",");
        const qRes = await fetch(`${API}/api/market/batch-quotes?codes=${codes}`);
        if (qRes.ok) {
          const qData = await qRes.json();
          const quotes = qData.quotes as Record<string, { price: number; name: string }>;
          for (const h of list) {
            if (quotes[h.code]?.price) {
              h.current = quotes[h.code].price;
              if (!h.name && quotes[h.code].name) h.name = quotes[h.code].name;
            }
          }
        }
      }
      setHoldings(list);
    } catch { /* backend 未啟動時靜默 */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadHoldings(); }, [loadHoldings]);

  const totalCost = holdings.reduce((s, p) => s + p.cost * p.qty * 1000, 0);
  const totalVal  = holdings.reduce((s, p) => s + (p.current ?? p.cost) * p.qty * 1000, 0);
  const totalPnL  = totalVal - totalCost;
  const totalPct  = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

  const submitForm = async () => {
    if (!form.code || !form.qty || !form.cost) return;
    setSaving(true);
    const body = { code:form.code, name:form.name, qty:Number(form.qty), cost:Number(form.cost), buy_date:form.buy_date||null, note:form.note };
    try {
      const url    = editId ? `${API}/api/portfolio/${editId}` : `${API}/api/portfolio`;
      const method = editId ? "PUT" : "POST";
      const res    = await fetch(url, { method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) });
      if (!res.ok) throw new Error((await res.json()).detail || "儲存失敗");
      setShowForm(false); setEditId(null); setForm({ code:"", name:"", qty:"", cost:"", buy_date:"", note:"" });
      loadHoldings();
    } catch (e) {
      alert(e instanceof Error ? e.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  const deleteHolding = async (id: number) => {
    if (!confirm("確定刪除此持倉？")) return;
    await fetch(`${API}/api/portfolio/${id}`, { method:"DELETE" });
    loadHoldings();
  };

  const startEdit = (p: Holding) => {
    setForm({ code:p.code, name:p.name, qty:String(p.qty), cost:String(p.cost), buy_date:p.buy_date??"", note:p.note });
    setEditId(p.id); setShowForm(true);
  };

  const handleOcrImport = async (list: ParsedPos[]) => {
    const today = new Date().toISOString().slice(0, 10);
    for (const p of list) {
      await fetch(`${API}/api/portfolio`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ code:p.code, name:p.name||p.code, qty:p.qty, cost:p.cost, buy_date:today, note:"截圖匯入" }),
      });
    }
    loadHoldings();
  };

  return (
    <div className="main-scroll" style={{ flex:1, overflowY:"auto", padding: isMobile ? "8px 8px 72px" : "16px 20px" }}>
      {showOcr && <OcrModal onClose={() => setShowOcr(false)} onImport={handleOcrImport} />}

      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
        <h2 style={{ fontSize:18, fontWeight:700, color:"#e8e8f0" }}>💼 持倉追蹤</h2>
        {tab === "manual" && (
          <div style={{ display:"flex", gap:8 }}>
            <button onClick={() => setShowOcr(true)} style={{ background:"#1a2a3a", color:"#3d7eff", border:"1px solid #3d7eff44", borderRadius:8, padding:"7px 14px", fontSize:13, fontWeight:700, cursor:"pointer" }}>
              📷 截圖匯入
            </button>
            <button onClick={() => { setShowForm(v => !v); setEditId(null); setForm({ code:"", name:"", qty:"", cost:"", buy_date:"", note:"" }); }}
              style={{ background:TW_COLORS.down, color:"#000", border:"none", borderRadius:8, padding:"7px 16px", fontSize:13, fontWeight:700, cursor:"pointer" }}>
              + 新增持倉
            </button>
          </div>
        )}
      </div>

      {/* Tab 切換 */}
      <div style={{ display:"flex", gap:4, marginBottom:16, background:"#0d0d15", borderRadius:8, padding:4 }}>
        {(["manual","yuanta"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ flex:1, padding:"6px 0", borderRadius:6, border:"none", fontSize:13, fontWeight:600, cursor:"pointer",
              background: tab===t ? "#1a1a24" : "transparent",
              color: tab===t ? "#e8e8f0" : "#555570" }}>
            {t === "manual" ? "手動記帳" : "元大即時"}
          </button>
        ))}
      </div>

      {/* Yuanta 即時 Tab */}
      {tab === "yuanta" && <YuantaTab />}

      {/* 手動記帳 Tab */}
      {tab === "manual" && (
        <>
          {/* 總覽卡片 */}
          <div style={{ display:"grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4,1fr)", gap:10, marginBottom:16 }}>
            {[
              { label:"持倉市值", val:`${(totalVal/10000).toFixed(1)}萬`,                                   color:"#e8e8f0" },
              { label:"總損益",   val:fmt(Math.round(totalPnL)),                                             color:twColor(totalPnL) },
              { label:"報酬率",   val:`${totalPct>=0?"+":""}${totalPct.toFixed(2)}%`,                        color:twColor(totalPct) },
              { label:"持倉檔數", val:`${holdings.length} 檔`,                                               color:"#8888aa" },
            ].map(c => (
              <div key={c.label} style={{ background:"#111118", border:"1px solid #2a2a3a", borderRadius:10, padding:"12px 14px" }}>
                <div style={{ fontSize:11, color:"#8888aa", marginBottom:4 }}>{c.label}</div>
                <div style={{ fontSize:18, fontWeight:700, color:c.color }}>{c.val}</div>
              </div>
            ))}
          </div>

          {/* 新增 / 編輯表單 */}
          {showForm && (
            <div style={{ background:"#111118", border:"1px solid #3d7eff", borderRadius:10, padding:"16px", marginBottom:16 }}>
              <div style={{ fontSize:14, fontWeight:700, color:"#3d7eff", marginBottom:12 }}>{editId ? "✏️ 編輯持倉" : "➕ 新增持倉"}</div>
              <div style={{ display:"grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "120px 160px 80px 100px 140px 1fr", gap:10, alignItems:"end" }}>
                {[
                  { key:"code",     label:"股票代號",    ph:"2330" },
                  { key:"name",     label:"名稱（選填）", ph:"台積電" },
                  { key:"qty",      label:"張數",        ph:"1" },
                  { key:"cost",     label:"成本價",       ph:"1000" },
                  { key:"buy_date", label:"買入日期",     ph:"2026-01-01" },
                  { key:"note",     label:"備註",         ph:"進場原因" },
                ].map(f => (
                  <div key={f.key} style={{ display:"flex", flexDirection:"column", gap:4 }}>
                    <label style={{ fontSize:11, color:"#8888aa" }}>{f.label}</label>
                    <input value={form[f.key as keyof typeof form]}
                      onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.ph}
                      style={{ background:"#1a1a24", border:"1px solid #2a2a3a", borderRadius:6, color:"#e8e8f0", fontSize:14, padding:"6px 10px", outline:"none" }} />
                  </div>
                ))}
              </div>
              <div style={{ display:"flex", gap:8, marginTop:12 }}>
                <button onClick={submitForm} disabled={saving}
                  style={{ background: saving ? "#1a1a24" : TW_COLORS.down, color: saving ? "#555570" : "#000", border:"none", borderRadius:6, padding:"7px 20px", fontSize:13, fontWeight:700, cursor: saving?"not-allowed":"pointer" }}>
                  {saving ? "儲存中…" : "確認"}
                </button>
                <button onClick={() => { setShowForm(false); setEditId(null); }}
                  style={{ background:"#1a1a24", color:"#8888aa", border:"1px solid #2a2a3a", borderRadius:6, padding:"7px 16px", fontSize:13, cursor:"pointer" }}>取消</button>
              </div>
            </div>
          )}

          {/* 持倉列表 */}
          {loading ? (
            <div style={{ textAlign:"center", color:"#8888aa", padding:"60px 0", fontSize:15 }}>載入中…</div>
          ) : holdings.length === 0 ? (
            <div style={{ textAlign:"center", color:"#8888aa", padding:"60px 0", fontSize:15 }}>尚無持倉，點「+ 新增持倉」開始記錄</div>
          ) : (
            <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
              {holdings.map(p => {
                const { diff, pct } = pnl(p);
                return (
                  <div key={p.id} style={{ background:"#111118", border:"1px solid #2a2a3a", borderRadius:10, padding:"14px 16px" }}>
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", flexWrap:"wrap", gap:8 }}>
                      <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                        <div style={{ display:"flex", gap:8, alignItems:"baseline" }}>
                          <span style={{ fontWeight:700, fontSize:16, color:"#e8e8f0", cursor:"pointer" }}
                            onClick={() => router.push(`/stock?s=${p.code}`)}
                            onMouseEnter={e => (e.currentTarget.style.color="#3d7eff")}
                            onMouseLeave={e => (e.currentTarget.style.color="#e8e8f0")}>
                            {p.name || p.code}
                          </span>
                          <span style={{ fontSize:13, color:"#8888aa" }}>{p.code}</span>
                        </div>
                        <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
                          <span style={{ fontSize:13, color:"#8888aa" }}>
                            {p.qty}張 × 成本 <span style={{ color:"#e8e8f0" }}>{p.cost.toLocaleString()}</span>
                          </span>
                          <span style={{ fontSize:13, color:"#8888aa" }}>
                            現價 <span style={{ color:"#e8e8f0", fontWeight:600 }}>{p.current ? p.current.toLocaleString() : "---"}</span>
                          </span>
                          {p.buy_date && <span style={{ fontSize:12, color:"#8888aa" }}>買入 {p.buy_date}</span>}
                        </div>
                        {p.note && <span style={{ fontSize:12, color:"#8888aa", fontStyle:"italic" }}>📝 {p.note}</span>}
                      </div>
                      <div style={{ textAlign:"right" }}>
                        {p.current ? (
                          <>
                            <div style={{ fontSize:20, fontWeight:700, color:twColor(diff) }}>{fmt(Math.round(diff))} 元</div>
                            <div style={{ fontSize:14, color:twColor(pct) }}>{pct>=0?"+":""}{pct.toFixed(2)}%</div>
                          </>
                        ) : (
                          <div style={{ fontSize:13, color:"#555570" }}>現價取得中…</div>
                        )}
                        <div style={{ display:"flex", gap:6, marginTop:8, justifyContent:"flex-end" }}>
                          <button onClick={() => startEdit(p)} style={{ background:"#1a1a24", border:"1px solid #2a2a3a", borderRadius:5, color:"#8888aa", fontSize:11, padding:"3px 8px", cursor:"pointer" }}>編輯</button>
                          <button onClick={() => deleteHolding(p.id)} style={{ background:"#1a1a24", border:"1px solid #3d0000", borderRadius:5, color:TW_COLORS.up, fontSize:11, padding:"3px 8px", cursor:"pointer" }}>刪除</button>
                        </div>
                      </div>
                    </div>
                    {p.current && (
                      <div style={{ marginTop:10 }}>
                        <div style={{ height:4, background:"#1a1a24", borderRadius:2, overflow:"hidden" }}>
                          <div style={{ width:`${Math.min(Math.abs(pct)*3,100)}%`, height:"100%", background:twColor(pct), borderRadius:2 }} />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
