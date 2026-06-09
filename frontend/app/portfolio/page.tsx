"use client";
import { useEffect, useState } from "react";

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

// ── 型別 ────────────────────────────────────────────────────
interface Position {
  id: string;
  code: string;
  name: string;
  qty: number;       // 張數
  cost: number;      // 成本價
  current: number;   // 現價（demo）
  buy_date: string;
  note: string;
}

const POS_KEY = "tw_radar_positions";

function loadPositions(): Position[] {
  try { return JSON.parse(localStorage.getItem(POS_KEY) || "[]"); } catch { return []; }
}
function savePositions(list: Position[]) {
  localStorage.setItem(POS_KEY, JSON.stringify(list));
}

// Demo 預設持倉
const DEMO_POSITIONS: Position[] = [
  { id: "1", code: "2330", name: "台積電",  qty: 2, cost: 1020, current: 1082, buy_date: "2026-05-15", note: "MACD 金叉進場" },
  { id: "2", code: "2382", name: "廣達",    qty: 5, cost:  308, current:  322, buy_date: "2026-05-22", note: "AI伺服器題材" },
  { id: "3", code: "2603", name: "長榮",    qty: 3, cost:  225, current:  218, buy_date: "2026-05-28", note: "航運季節性佈局" },
];

function pnl(p: Position) {
  const diff = (p.current - p.cost) * p.qty * 1000;
  const pct = ((p.current - p.cost) / p.cost) * 100;
  return { diff, pct };
}

function fmt(n: number) {
  return n >= 0 ? `+${n.toLocaleString()}` : n.toLocaleString();
}

// ── 截圖辨識 Modal ────────────────────────────────────────────────────────────
interface ParsedPos { code: string; name: string; qty: number; cost: number; current_price?: number }

function OcrModal({
  onClose,
  onImport,
}: {
  onClose: () => void;
  onImport: (list: ParsedPos[]) => void;
}) {
  const [file, setFile]       = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState<ParsedPos[] | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const handleFile = (f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
    const url = URL.createObjectURL(f);
    setPreview(url);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith("image/")) handleFile(f);
  };

  const upload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/portfolio/parse-screenshot", { method: "POST", body: fd });
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

  const toggleSel = (i: number) => {
    setSelected(prev => {
      const s = new Set(prev);
      s.has(i) ? s.delete(i) : s.add(i);
      return s;
    });
  };

  const doImport = () => {
    if (!result) return;
    onImport(result.filter((_, i) => selected.has(i)));
    onClose();
  };

  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"#00000099", zIndex:1000,
      display:"flex", alignItems:"center", justifyContent:"center", padding:16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background:"#111118", border:"1px solid #3a3a5a", borderRadius:14,
        padding:"24px", width:"100%", maxWidth:520,
        boxShadow:"0 8px 40px #000c", overflowY:"auto", maxHeight:"90vh",
      }}>
        {/* 標題 */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:18 }}>
          <div>
            <div style={{ fontSize:16, fontWeight:800, color:"#e8e8f0" }}>📷 上傳對帳單截圖</div>
            <div style={{ fontSize:11, color:"#8888aa", marginTop:2 }}>支援元大、富邦等券商 App 截圖，自動辨識持倉</div>
          </div>
          <button onClick={onClose} style={{
            background:"transparent", border:"none", color:"#555570",
            fontSize:18, cursor:"pointer",
          }}
            onMouseEnter={e => (e.currentTarget.style.color="#e8e8f0")}
            onMouseLeave={e => (e.currentTarget.style.color="#555570")}
          >✕</button>
        </div>

        {/* 拖放區 / 預覽 */}
        {!preview ? (
          <div
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            style={{
              border:"2px dashed #3a3a5a", borderRadius:10, padding:"32px 16px",
              textAlign:"center", cursor:"pointer", marginBottom:16,
              transition:"border-color 0.15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor="#3d7eff")}
            onMouseLeave={e => (e.currentTarget.style.borderColor="#3a3a5a")}
            onClick={() => document.getElementById("ocr-file-input")?.click()}
          >
            <div style={{ fontSize:32, marginBottom:8 }}>📂</div>
            <div style={{ fontSize:14, color:"#8888aa" }}>點擊或拖曳圖片至此</div>
            <div style={{ fontSize:11, color:"#555570", marginTop:4 }}>PNG / JPG，最大 10MB</div>
            <input
              id="ocr-file-input" type="file" accept="image/*"
              style={{ display:"none" }}
              onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
          </div>
        ) : (
          <div style={{ marginBottom:16, position:"relative" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="preview" style={{
              width:"100%", borderRadius:8, border:"1px solid #2a2a3a",
              maxHeight:220, objectFit:"contain", background:"#0d0d15",
            }} />
            <button
              onClick={() => { setPreview(null); setFile(null); setResult(null); setError(null); }}
              style={{
                position:"absolute", top:6, right:6, background:"#00000099",
                border:"none", color:"#e8e8f0", borderRadius:20, width:24, height:24,
                cursor:"pointer", fontSize:12, display:"flex", alignItems:"center", justifyContent:"center",
              }}
            >✕</button>
          </div>
        )}

        {/* 辨識按鈕 */}
        {file && !result && (
          <button onClick={upload} disabled={loading} style={{
            width:"100%", padding:"10px 0", borderRadius:8,
            background: loading ? "#1a1a24" : "#3d7eff",
            color: loading ? "#555570" : "#fff",
            border:"none", fontSize:14, fontWeight:700, cursor: loading ? "not-allowed" : "pointer",
            marginBottom:16,
          }}>
            {loading ? "⏳ AI 辨識中…" : "🔍 開始辨識"}
          </button>
        )}

        {/* 錯誤 */}
        {error && (
          <div style={{
            padding:"10px 14px", borderRadius:8, marginBottom:16,
            background:"#3d0000", border:"1px solid #ff4d4d44",
            fontSize:13, color:"#ff4d4d",
          }}>{error}</div>
        )}

        {/* 辨識結果 */}
        {result && (
          <>
            <div style={{ fontSize:13, color:"#8888aa", marginBottom:8 }}>
              辨識到 <span style={{ color:"#00c076", fontWeight:700 }}>{result.length}</span> 筆持倉，勾選後匯入：
            </div>
            <div style={{ display:"flex", flexDirection:"column", gap:6, marginBottom:16 }}>
              {result.map((p, i) => (
                <div key={i} onClick={() => toggleSel(i)} style={{
                  display:"flex", alignItems:"center", gap:10,
                  background: selected.has(i) ? "#1a2a3a" : "#0d0d15",
                  border:`1px solid ${selected.has(i) ? "#3d7eff44" : "#2a2a3a"}`,
                  borderRadius:8, padding:"10px 12px", cursor:"pointer",
                  transition:"all 0.1s",
                }}>
                  <div style={{
                    width:16, height:16, borderRadius:3,
                    border:`2px solid ${selected.has(i) ? "#3d7eff" : "#3a3a5a"}`,
                    background: selected.has(i) ? "#3d7eff" : "transparent",
                    flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize:10, color:"#fff",
                  }}>{selected.has(i) ? "✓" : ""}</div>
                  <div style={{ flex:1 }}>
                    <span style={{ fontSize:14, fontWeight:700, color:"#3d7eff" }}>{p.code}</span>
                    <span style={{ fontSize:13, color:"#c8c8d8", marginLeft:8 }}>{p.name}</span>
                  </div>
                  <div style={{ fontSize:12, color:"#8888aa", textAlign:"right" }}>
                    <div>{p.qty} 張</div>
                    <div>成本 {p.cost.toLocaleString()}</div>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={doImport} disabled={selected.size === 0} style={{
              width:"100%", padding:"10px 0", borderRadius:8,
              background: selected.size > 0 ? "#00c076" : "#1a1a24",
              color: selected.size > 0 ? "#000" : "#555570",
              border:"none", fontSize:14, fontWeight:700,
              cursor: selected.size > 0 ? "pointer" : "not-allowed",
            }}>
              匯入 {selected.size} 筆持倉
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const isMobile = useIsMobile();
  const [positions, setPositions] = useState<Position[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", qty: "", cost: "", note: "" });
  const [editId, setEditId] = useState<string | null>(null);
  const [showOcr, setShowOcr] = useState(false);

  useEffect(() => {
    const saved = loadPositions();
    setPositions(saved.length ? saved : DEMO_POSITIONS);
  }, []);

  const totalCost = positions.reduce((s, p) => s + p.cost * p.qty * 1000, 0);
  const totalVal  = positions.reduce((s, p) => s + p.current * p.qty * 1000, 0);
  const totalPnL  = totalVal - totalCost;
  const totalPct  = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

  const submitForm = () => {
    if (!form.code || !form.qty || !form.cost) return;
    // 用 demo current 價格（真實版會打 API）
    const demoPrice: Record<string, number> = {
      "2330": 1082, "2317": 218, "2454": 940, "0050": 185,
      "2308": 392, "2382": 322, "2603": 218, "2615": 98,
    };
    const current = demoPrice[form.code] ?? Number(form.cost);
    const today = new Date().toISOString().slice(0, 10);

    if (editId) {
      const next = positions.map(p => p.id === editId
        ? { ...p, code: form.code, name: form.name || form.code, qty: Number(form.qty), cost: Number(form.cost), current, note: form.note }
        : p
      );
      setPositions(next);
      savePositions(next);
    } else {
      const next = [...positions, {
        id: Date.now().toString(),
        code: form.code, name: form.name || form.code,
        qty: Number(form.qty), cost: Number(form.cost),
        current, buy_date: today, note: form.note,
      }];
      setPositions(next);
      savePositions(next);
    }
    setForm({ code: "", name: "", qty: "", cost: "", note: "" });
    setShowForm(false);
    setEditId(null);
  };

  const deletePos = (id: string) => {
    const next = positions.filter(p => p.id !== id);
    setPositions(next);
    savePositions(next);
  };

  const startEdit = (p: Position) => {
    setForm({ code: p.code, name: p.name, qty: String(p.qty), cost: String(p.cost), note: p.note });
    setEditId(p.id);
    setShowForm(true);
  };

  const handleOcrImport = (list: ParsedPos[]) => {
    const today = new Date().toISOString().slice(0, 10);
    const newPositions = list.map(p => ({
      id: Date.now().toString() + Math.random().toString(36).slice(2),
      code: p.code,
      name: p.name || p.code,
      qty: p.qty,
      cost: p.cost,
      current: p.current_price ?? p.cost,
      buy_date: today,
      note: "截圖匯入",
    }));
    const next = [...positions, ...newPositions];
    setPositions(next);
    savePositions(next);
  };

  return (
    <div className="main-scroll" style={{ flex: 1, overflowY: "auto", padding: isMobile ? "8px 8px 72px" : "16px 20px" }}>
      {showOcr && <OcrModal onClose={() => setShowOcr(false)} onImport={handleOcrImport} />}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#e8e8f0" }}>💼 持倉追蹤</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShowOcr(true)} style={{
            background: "#1a2a3a", color: "#3d7eff", border: "1px solid #3d7eff44",
            borderRadius: 8, padding: "7px 14px", fontSize: 13, fontWeight: 700, cursor: "pointer",
          }}>
            📷 截圖匯入
          </button>
          <button onClick={() => { setShowForm(v => !v); setEditId(null); setForm({ code: "", name: "", qty: "", cost: "", note: "" }); }} style={{
            background: "#00c076", color: "#000", border: "none", borderRadius: 8,
            padding: "7px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer",
          }}>
            + 新增持倉
          </button>
        </div>
      </div>

      {/* 總覽卡片 */}
      <div style={{
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4, 1fr)",
        gap: 10, marginBottom: 16,
      }}>
        {[
          { label: "持倉市值", val: `${(totalVal / 10000).toFixed(1)}萬`, color: "#e8e8f0" },
          { label: "總損益",   val: fmt(Math.round(totalPnL)), color: totalPnL >= 0 ? "#ff4d4d" : "#00c076" },
          { label: "報酬率",   val: `${totalPct >= 0 ? "+" : ""}${totalPct.toFixed(2)}%`, color: totalPct >= 0 ? "#ff4d4d" : "#00c076" },
          { label: "持倉檔數", val: `${positions.length} 檔`, color: "#8888aa" },
        ].map(c => (
          <div key={c.label} style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 10, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "#8888aa", marginBottom: 4 }}>{c.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: c.color }}>{c.val}</div>
          </div>
        ))}
      </div>

      {/* 新增 / 編輯表單 */}
      {showForm && (
        <div style={{
          background: "#111118", border: "1px solid #3d7eff", borderRadius: 10,
          padding: "16px", marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#3d7eff", marginBottom: 12 }}>
            {editId ? "✏️ 編輯持倉" : "➕ 新增持倉"}
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr 1fr" : "120px 160px 100px 120px 1fr",
            gap: 10, alignItems: "end",
          }}>
            {[
              { key: "code", label: "股票代號", ph: "2330" },
              { key: "name", label: "名稱（選填）", ph: "台積電" },
              { key: "qty",  label: "張數", ph: "1" },
              { key: "cost", label: "成本價", ph: "1000" },
              { key: "note", label: "備註", ph: "進場原因" },
            ].map(f => (
              <div key={f.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label style={{ fontSize: 11, color: "#8888aa" }}>{f.label}</label>
                <input
                  value={form[f.key as keyof typeof form]}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.ph}
                  style={{
                    background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 6,
                    color: "#e8e8f0", fontSize: 14, padding: "6px 10px", outline: "none",
                  }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button onClick={submitForm} style={{
              background: "#00c076", color: "#000", border: "none", borderRadius: 6,
              padding: "7px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer",
            }}>確認</button>
            <button onClick={() => { setShowForm(false); setEditId(null); }} style={{
              background: "#1a1a24", color: "#8888aa", border: "1px solid #2a2a3a",
              borderRadius: 6, padding: "7px 16px", fontSize: 13, cursor: "pointer",
            }}>取消</button>
          </div>
        </div>
      )}

      {/* 持倉列表 */}
      {positions.length === 0 ? (
        <div style={{ textAlign: "center", color: "#8888aa", padding: "60px 0", fontSize: 15 }}>
          尚無持倉，點「+ 新增持倉」開始記錄
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {positions.map(p => {
            const { diff, pct } = pnl(p);
            const up = diff >= 0;
            return (
              <div key={p.id} style={{
                background: "#111118", border: "1px solid #2a2a3a", borderRadius: 10,
                padding: "14px 16px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
                  {/* 左側：股票資訊 */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                      <span style={{ fontWeight: 700, fontSize: 16, color: "#e8e8f0" }}>{p.name}</span>
                      <span style={{ fontSize: 13, color: "#8888aa" }}>{p.code}</span>
                    </div>
                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 13, color: "#8888aa" }}>
                        {p.qty}張 × 成本 <span style={{ color: "#e8e8f0" }}>{p.cost.toLocaleString()}</span>
                      </span>
                      <span style={{ fontSize: 13, color: "#8888aa" }}>
                        現價 <span style={{ color: "#e8e8f0", fontWeight: 600 }}>{p.current.toLocaleString()}</span>
                      </span>
                      <span style={{ fontSize: 12, color: "#8888aa" }}>買入 {p.buy_date}</span>
                    </div>
                    {p.note && (
                      <span style={{ fontSize: 12, color: "#8888aa", fontStyle: "italic" }}>📝 {p.note}</span>
                    )}
                  </div>

                  {/* 右側：損益 */}
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: up ? "#ff4d4d" : "#00c076" }}>
                      {fmt(Math.round(diff))} 元
                    </div>
                    <div style={{ fontSize: 14, color: up ? "#ff4d4d" : "#00c076" }}>
                      {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
                    </div>
                    <div style={{ display: "flex", gap: 6, marginTop: 8, justifyContent: "flex-end" }}>
                      <button onClick={() => startEdit(p)} style={{
                        background: "#1a1a24", border: "1px solid #2a2a3a",
                        borderRadius: 5, color: "#8888aa", fontSize: 11, padding: "3px 8px", cursor: "pointer",
                      }}>編輯</button>
                      <button onClick={() => deletePos(p.id)} style={{
                        background: "#1a1a24", border: "1px solid #3d0000",
                        borderRadius: 5, color: "#ff4d4d", fontSize: 11, padding: "3px 8px", cursor: "pointer",
                      }}>刪除</button>
                    </div>
                  </div>
                </div>

                {/* 損益進度條 */}
                <div style={{ marginTop: 10 }}>
                  <div style={{ height: 4, background: "#1a1a24", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      width: `${Math.min(Math.abs(pct) * 3, 100)}%`,
                      height: "100%",
                      background: up ? "#ff4d4d" : "#00c076",
                      borderRadius: 2,
                    }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{
        marginTop: 20, padding: "12px 14px", borderRadius: 8,
        background: "#0d0d15", border: "1px solid #2a2a3a", fontSize: 12, color: "#8888aa", lineHeight: 1.8,
      }}>
        <span style={{ color: "#f5a623", fontWeight: 600 }}>⚠️ 目前現價為 Demo 資料</span>
        　Phase 2 串接元大 API 後自動同步即時損益。持倉資料儲存於本機 localStorage。
      </div>
    </div>
  );
}
