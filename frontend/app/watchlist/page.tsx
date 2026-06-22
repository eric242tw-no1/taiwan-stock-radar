"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

// ── Demo 股票池（與 screener 共用）──────────────────────────────
const STOCK_POOL: Record<string, { name: string; price: number; change_pct: number; industry: string }> = {
  "2330": { name:"台積電",     price:1082, change_pct: 2.15, industry:"半導體"   },
  "2382": { name:"廣達",       price: 322, change_pct: 1.86, industry:"電子製造"  },
  "2454": { name:"聯發科",     price: 940, change_pct: 1.38, industry:"半導體"   },
  "2603": { name:"長榮",       price: 218, change_pct: 2.83, industry:"航運"     },
  "2317": { name:"鴻海",       price: 218, change_pct: 0.92, industry:"電子製造"  },
  "3711": { name:"日月光投控", price: 158, change_pct: 1.29, industry:"半導體"   },
  "2308": { name:"台達電",     price: 392, change_pct: 3.20, industry:"電子零組件"},
  "2303": { name:"聯電",       price:  52, change_pct: 0.97, industry:"半導體"   },
  "2881": { name:"富邦金",     price: 102, change_pct: 0.49, industry:"金融"     },
  "2886": { name:"兆豐金",     price:  44, change_pct:-0.22, industry:"金融"     },
  "2412": { name:"中華電",     price: 128, change_pct: 0.08, industry:"電信"     },
  "1301": { name:"台塑",       price:  68, change_pct:-0.44, industry:"石化"     },
  "3034": { name:"聯詠",       price: 465, change_pct: 4.72, industry:"半導體"   },
  "6770": { name:"力積電",     price:  39, change_pct: 9.97, industry:"半導體"   },
  "3481": { name:"群創",       price:  18, change_pct: 9.89, industry:"光電"     },
  "2615": { name:"萬海",       price:  98, change_pct:-9.91, industry:"航運"     },
  "2609": { name:"陽明",       price:  72, change_pct:-9.86, industry:"航運"     },
  "8454": { name:"富邦媒",     price: 622, change_pct: 6.32, industry:"電商"     },
  "3037": { name:"欣興",       price: 168, change_pct: 3.85, industry:"PCB"      },
  "2376": { name:"技嘉",       price: 312, change_pct: 5.41, industry:"電腦"     },
  "6669": { name:"緯穎",       price:3450, change_pct: 2.08, industry:"伺服器"   },
  "6531": { name:"愛普",       price: 895, change_pct:10.00, industry:"半導體"   },
  "2227": { name:"裕日車",     price: 248, change_pct:-9.95, industry:"汽車"     },
  "0050": { name:"元大台灣50", price: 208, change_pct:-1.33, industry:"ETF"      },
  "00878":{ name:"國泰永續高股息", price: 22, change_pct:-0.45, industry:"ETF"  },
};

// ── localStorage 結構 ────────────────────────────────────────
const GROUPS_KEY = "tw_radar_wl_groups";
const DEFAULT_GROUPS = [
  { id: "g1", name: "短線當沖",   stocks: [] as string[] },
  { id: "g2", name: "中長線持股", stocks: [] as string[] },
  { id: "g3", name: "觀察名單",   stocks: [] as string[] },
  { id: "g4", name: "指數ETF",    stocks: [] as string[] },
  { id: "g5", name: "自定義 5",   stocks: [] as string[] },
];

type Group = { id: string; name: string; stocks: string[] };

function loadGroups(): Group[] {
  try {
    const raw = localStorage.getItem(GROUPS_KEY);
    if (!raw) return DEFAULT_GROUPS.map(g => ({ ...g }));
    const parsed = JSON.parse(raw) as Group[];
    // 確保始終有 5 組
    while (parsed.length < 5) parsed.push({ ...DEFAULT_GROUPS[parsed.length] });
    return parsed.slice(0, 5);
  } catch { return DEFAULT_GROUPS.map(g => ({ ...g })); }
}

function saveGroups(groups: Group[]) {
  localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
}

// ── 搜尋對話框 ───────────────────────────────────────────────
function AddStockModal({ onAdd, onClose }: { onAdd: (code: string) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { inputRef.current?.focus(); }, []);

  const results = Object.entries(STOCK_POOL).filter(([code, s]) =>
    code.includes(q) || s.name.includes(q) || s.industry.includes(q)
  ).slice(0, 8);

  return (
    <div style={{
      position:"fixed", inset:0, background:"#00000088", zIndex:200,
      display:"flex", alignItems:"center", justifyContent:"center",
    }} onClick={onClose}>
      <div style={{
        background:"var(--c-bg-card)", border:"1px solid var(--c-border)", borderRadius:12,
        padding:"20px", width:360, maxHeight:"70vh", display:"flex", flexDirection:"column",
      }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize:15, fontWeight:700, color:"var(--c-text)", marginBottom:12 }}>新增股票</div>
        <input
          ref={inputRef} value={q} onChange={e => setQ(e.target.value)}
          placeholder="輸入代號或名稱…"
          style={{
            background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:8,
            color:"var(--c-text)", fontSize:14, padding:"8px 12px", outline:"none", marginBottom:10,
          }}
        />
        <div style={{ overflowY:"auto", flex:1 }}>
          {results.length === 0 ? (
            <div style={{ color:"var(--c-text-dim)", textAlign:"center", padding:"20px 0", fontSize:13 }}>無符合結果</div>
          ) : results.map(([code, s]) => (
            <div key={code} onClick={() => { onAdd(code); onClose(); }}
              style={{
                display:"flex", justifyContent:"space-between", alignItems:"center",
                padding:"9px 8px", borderRadius:7, cursor:"pointer",
                borderBottom:"1px solid #1a1a2a",
              }}
              onMouseEnter={e => (e.currentTarget.style.background="var(--c-bg-deep)")}
              onMouseLeave={e => (e.currentTarget.style.background="transparent")}
            >
              <div>
                <span style={{ fontSize:14, fontWeight:600, color:"var(--c-text)" }}>{s.name}</span>
                <span style={{ fontSize:12, color:"var(--c-text-dim)", marginLeft:6 }}>{code}</span>
              </div>
              <span style={{ fontSize:11, color:"var(--c-text-dim)", background:"var(--c-bg-deep)", padding:"2px 6px", borderRadius:4 }}>{s.industry}</span>
            </div>
          ))}
        </div>
        <button onClick={onClose} style={{
          marginTop:12, padding:"7px", borderRadius:8, background:"var(--c-bg-deep)",
          border:"1px solid var(--c-border)", color:"var(--c-text-dim)", cursor:"pointer", fontSize:13,
        }}>取消</button>
      </div>
    </div>
  );
}

// ── 股票卡片 ─────────────────────────────────────────────────
function StockCard({ code, onRemove, onClick }: { code: string; onRemove: () => void; onClick: () => void }) {
  const s = STOCK_POOL[code];
  if (!s) return null;
  const up = s.change_pct >= 0;
  return (
    <div style={{
      background:"var(--c-bg-card)", border:"1px solid var(--c-border)", borderRadius:9,
      padding:"10px 12px", display:"flex", justifyContent:"space-between", alignItems:"center",
      cursor:"pointer",
    }} onClick={onClick}>
      <div>
        <span style={{ fontSize:14, fontWeight:700, color:"var(--c-text)" }}>{s.name}</span>
        <span style={{ fontSize:12, color:"var(--c-text-dim)", marginLeft:6 }}>{code}</span>
        <span style={{ fontSize:11, color:"var(--c-text-dim)", background:"var(--c-bg-deep)", padding:"1px 6px", borderRadius:4, marginLeft:6 }}>{s.industry}</span>
      </div>
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        <div style={{ textAlign:"right" }}>
          <div style={{ fontSize:15, fontWeight:700, color:"var(--c-text)" }}>{s.price.toLocaleString()}</div>
          <div style={{ fontSize:12, color: up ? "#ff4d4d" : "#00c076" }}>
            {up ? "▲" : "▼"} {Math.abs(s.change_pct).toFixed(2)}%
          </div>
        </div>
        <button onClick={e => { e.stopPropagation(); onRemove(); }} style={{
          background:"transparent", border:"none", color:"#444460",
          fontSize:16, cursor:"pointer", padding:"0 4px", lineHeight:1,
        }} title="移除">✕</button>
      </div>
    </div>
  );
}

// ── 主頁面 ───────────────────────────────────────────────────
export default function WatchlistPage() {
  const router = useRouter();
  const [groups, setGroups]     = useState<Group[]>([]);
  const [activeId, setActiveId] = useState("g1");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [showAdd, setShowAdd]   = useState(false);

  useEffect(() => {
    const g = loadGroups();
    setGroups(g);
  }, []);

  const update = (next: Group[]) => { setGroups(next); saveGroups(next); };

  const renameGroup = (id: string) => {
    update(groups.map(g => g.id === id ? { ...g, name: editName.trim() || g.name } : g));
    setEditingId(null);
  };

  const addStock = (code: string) => {
    update(groups.map(g =>
      g.id === activeId && !g.stocks.includes(code)
        ? { ...g, stocks: [...g.stocks, code] }
        : g
    ));
  };

  const removeStock = (groupId: string, code: string) => {
    update(groups.map(g =>
      g.id === groupId ? { ...g, stocks: g.stocks.filter(c => c !== code) } : g
    ));
  };

  const activeGroup = groups.find(g => g.id === activeId);
  const totalStocks = groups.reduce((s, g) => s + g.stocks.length, 0);

  return (
    <div style={{ maxWidth:900, margin:"0 auto", padding:"16px 20px" }}>
      {/* 頁頭 */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:700, color:"var(--c-text)", margin:0 }}>⭐ 我的自選收藏</h2>
          <div style={{ fontSize:12, color:"var(--c-text-dim)", marginTop:3 }}>共 {totalStocks} 支股票 · 5 個群組</div>
        </div>
        <button onClick={() => setShowAdd(true)} style={{
          background:"#00c076", color:"#000", fontWeight:700,
          border:"none", borderRadius:8, padding:"8px 16px", fontSize:14, cursor:"pointer",
        }}>+ 新增股票</button>
      </div>

      {/* 群組 Tab */}
      <div style={{ display:"flex", gap:0, marginBottom:16, borderBottom:"1px solid var(--c-border)", overflowX:"auto" }}>
        {groups.map(g => {
          const active = g.id === activeId;
          return (
            <div key={g.id} style={{ display:"flex", alignItems:"center", flexShrink:0 }}>
              {editingId === g.id ? (
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  onBlur={() => renameGroup(g.id)}
                  onKeyDown={e => { if (e.key === "Enter") renameGroup(g.id); if (e.key === "Escape") setEditingId(null); }}
                  autoFocus
                  style={{
                    background:"var(--c-bg-deep)", border:"1px solid #00c076", borderRadius:"6px 6px 0 0",
                    color:"var(--c-text)", fontSize:13, padding:"7px 10px", outline:"none", width:100,
                  }}
                />
              ) : (
                <button
                  onClick={() => setActiveId(g.id)}
                  onDoubleClick={() => { setEditingId(g.id); setEditName(g.name); }}
                  style={{
                    padding:"8px 16px", background:"transparent", border:"none",
                    borderBottom: active ? "2px solid #00c076" : "2px solid transparent",
                    color: active ? "var(--c-text)" : "var(--c-text-dim)",
                    fontSize:13, fontWeight: active ? 600 : 400,
                    cursor:"pointer", whiteSpace:"nowrap",
                  }}
                >
                  {g.name}
                  <span style={{ marginLeft:5, fontSize:11, color: active ? "#00c076" : "#444460" }}>
                    ({g.stocks.length})
                  </span>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* 群組操作列 */}
      {activeGroup && (
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
          <div style={{ fontSize:13, color:"var(--c-text-dim)" }}>
            雙擊分頁標籤可更改群組名稱
          </div>
          <button
            onClick={() => { setEditingId(activeGroup.id); setEditName(activeGroup.name); }}
            style={{
              background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:6,
              color:"var(--c-text-dim)", fontSize:12, padding:"4px 10px", cursor:"pointer",
            }}
          >✏️ 改名</button>
        </div>
      )}

      {/* 股票列表 */}
      {activeGroup && (
        activeGroup.stocks.length === 0 ? (
          <div style={{
            textAlign:"center", padding:"60px 20px",
            border:"2px dashed var(--c-border)", borderRadius:12, color:"var(--c-text-dim)",
          }}>
            <div style={{ fontSize:36, marginBottom:12 }}>⭐</div>
            <div style={{ fontSize:15, marginBottom:8 }}>此群組尚無股票</div>
            <div style={{ fontSize:13, marginBottom:20 }}>點擊「+ 新增股票」加入觀察清單</div>
            <button onClick={() => setShowAdd(true)} style={{
              background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:8,
              color:"var(--c-text-dim)", fontSize:13, padding:"8px 20px", cursor:"pointer",
            }}>+ 新增股票</button>
          </div>
        ) : (
          <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
            {activeGroup.stocks.map(code => (
              <StockCard
                key={code}
                code={code}
                onRemove={() => removeStock(activeGroup.id, code)}
                onClick={() => router.push(`/stock?s=${code}`)}
              />
            ))}
          </div>
        )
      )}

      {/* 快速從選股工作流同步 */}
      <div style={{
        marginTop:24, padding:"12px 16px", borderRadius:8,
        background:"var(--c-bg-main)", border:"1px solid var(--c-border)",
        display:"flex", justifyContent:"space-between", alignItems:"center",
      }}>
        <span style={{ fontSize:13, color:"var(--c-text-dim)" }}>從「選股工作流」的自選股池同步</span>
        <button onClick={() => {
          try {
            const wl: string[] = JSON.parse(localStorage.getItem("tw_radar_watchlist") || "[]");
            if (!wl.length) return;
            update(groups.map(g =>
              g.id === activeId
                ? { ...g, stocks: [...new Set([...g.stocks, ...wl])] }
                : g
            ));
          } catch { /* empty */ }
        }} style={{
          background:"var(--c-bg-deep)", border:"1px solid var(--c-border)", borderRadius:6,
          color:"var(--c-text-dim)", fontSize:13, padding:"5px 14px", cursor:"pointer",
        }}>同步到此群組</button>
      </div>

      {showAdd && <AddStockModal onAdd={addStock} onClose={() => setShowAdd(false)} />}
    </div>
  );
}
