"use client";
import { useState, useEffect, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EMOTIONS = ["冷靜", "貪婪", "恐懼", "猶豫", "自信", "衝動"];

interface Entry {
  id: number; symbol: string; direction: string; quantity: number;
  entry_price: number; exit_price: number | null;
  entry_at: string; strategy: string | null; emotion: string | null; note: string | null;
}

interface Stats {
  total: number; closed: number; win_rate: number; avg_pnl: number;
  emotion_distribution: { emotion: string; count: number }[];
}

const emptyForm = () => ({
  symbol: "", direction: "buy", quantity: 100, entry_price: 0,
  exit_price: "", strategy: "", emotion: "", note: "",
});

function StatCard({ label, value, color = "var(--c-text)" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
      borderRadius: 10, padding: "14px 20px", minWidth: 140,
    }}>
      <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

export default function JournalPage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Entry | null>(null);
  const [form, setForm] = useState(emptyForm());
  const PAGE_SIZE = 15;

  const loadEntries = useCallback(async (p = page) => {
    const res = await fetch(`${API}/api/journal/entries?page=${p}&page_size=${PAGE_SIZE}`);
    const data = await res.json();
    setEntries(data.entries ?? []);
    setTotal(data.total ?? 0);
  }, [page]);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/journal/stats`);
      setStats(await res.json());
    } catch {}
  }, []);

  useEffect(() => { loadEntries(); loadStats(); }, [page]);

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (e: Entry) => {
    setEditing(e);
    setForm({
      symbol: e.symbol, direction: e.direction, quantity: e.quantity,
      entry_price: e.entry_price, exit_price: e.exit_price?.toString() ?? "",
      strategy: e.strategy ?? "", emotion: e.emotion ?? "", note: e.note ?? "",
    });
    setShowForm(true);
  };

  const submit = async () => {
    const body = {
      ...form, quantity: Number(form.quantity), entry_price: Number(form.entry_price),
      exit_price: form.exit_price ? Number(form.exit_price) : null,
      strategy: form.strategy || null, emotion: form.emotion || null, note: form.note || null,
    };
    if (editing) {
      await fetch(`${API}/api/journal/entries/${editing.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } else {
      await fetch(`${API}/api/journal/entries`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    }
    setShowForm(false);
    loadEntries(1); setPage(1); loadStats();
  };

  const deleteEntry = async (id: number) => {
    if (!confirm("確定刪除？")) return;
    await fetch(`${API}/api/journal/entries/${id}`, { method: "DELETE" });
    loadEntries(); loadStats();
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--c-text)" }}>📝 交易日誌</h1>
        <button onClick={openAdd} style={{ padding: "8px 20px", borderRadius: 8, background: "#00c076", border: "none", color: "#000", cursor: "pointer", fontWeight: 600 }}>
          + 新增記錄
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
          <StatCard label="總記錄" value={String(stats.total)} />
          <StatCard label="已平倉" value={String(stats.closed)} />
          <StatCard label="勝率" value={`${(stats.win_rate * 100).toFixed(1)}%`} color="#00c076" />
          <StatCard label="平均損益" value={`${stats.avg_pnl > 0 ? "+" : ""}${stats.avg_pnl}`} color={stats.avg_pnl >= 0 ? "#00c076" : "#ef4444"} />
          {stats.emotion_distribution.length > 0 && (
            <div style={{ background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 10, padding: "14px 20px", flex: 1, minWidth: 260 }}>
              <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginBottom: 8 }}>情緒分布</div>
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={stats.emotion_distribution} margin={{ top: 0, bottom: 0, left: -20, right: 0 }}>
                  <XAxis dataKey="emotion" tick={{ fontSize: 11, fill: "var(--c-text-dim)" }} />
                  <YAxis hide />
                  <Tooltip contentStyle={{ background: "var(--c-bg-deep)", border: "1px solid var(--c-border)" }} />
                  <Bar dataKey="count" fill="#00c076" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div style={{ background: "var(--c-bg-deep)", borderRadius: 10, border: "1px solid var(--c-border)", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--c-border)" }}>
              {["股票", "方向", "數量", "進場價", "出場價", "情緒", "策略", "備註", "日期", "操作"].map(h => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: "var(--c-text-dim)", fontWeight: 500, fontSize: 12 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map(e => {
              const pnl = e.exit_price ? ((e.exit_price - e.entry_price) * (e.direction === "buy" ? 1 : -1) * e.quantity) : null;
              return (
                <tr key={e.id} style={{ borderBottom: "1px solid var(--c-border)22" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "var(--c-text)" }}>{e.symbol}</td>
                  <td style={{ padding: "10px 12px", color: e.direction === "buy" ? "#00c076" : "#ef4444" }}>
                    {e.direction === "buy" ? "買" : "賣"}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text)" }}>{e.quantity}</td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text)" }}>{e.entry_price}</td>
                  <td style={{ padding: "10px 12px", color: pnl !== null ? (pnl >= 0 ? "#00c076" : "#ef4444") : "var(--c-text-dim)" }}>
                    {e.exit_price ?? "-"}
                    {pnl !== null && <span style={{ fontSize: 11, marginLeft: 4 }}>({pnl > 0 ? "+" : ""}{pnl.toFixed(0)})</span>}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text-dim)" }}>{e.emotion ?? "-"}</td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text-dim)", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis" }}>{e.strategy ?? "-"}</td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text-dim)", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis" }}>{e.note ?? "-"}</td>
                  <td style={{ padding: "10px 12px", color: "var(--c-text-dim)", fontSize: 12 }}>{e.entry_at.slice(0, 10)}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <button onClick={() => openEdit(e)} style={{ marginRight: 8, cursor: "pointer", background: "none", border: "none", color: "#3b82f6", fontSize: 13 }}>編輯</button>
                    <button onClick={() => deleteEntry(e.id)} style={{ cursor: "pointer", background: "none", border: "none", color: "#ef4444", fontSize: 13 }}>刪除</button>
                  </td>
                </tr>
              );
            })}
            {entries.length === 0 && (
              <tr><td colSpan={10} style={{ padding: 32, textAlign: "center", color: "var(--c-text-dim)" }}>尚無記錄，點擊「+ 新增記錄」開始</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: "6px 14px", borderRadius: 6, cursor: "pointer", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", color: "var(--c-text)" }}>
            上一頁
          </button>
          <span style={{ padding: "6px 0", color: "var(--c-text-dim)", fontSize: 14 }}>{page} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            style={{ padding: "6px 14px", borderRadius: 6, cursor: "pointer", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", color: "var(--c-text)" }}>
            下一頁
          </button>
        </div>
      )}

      {/* Modal */}
      {showForm && (
        <div style={{
          position: "fixed", inset: 0, background: "#00000088", display: "flex",
          alignItems: "center", justifyContent: "center", zIndex: 1000,
        }} onClick={() => setShowForm(false)}>
          <div style={{
            background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 12,
            padding: 28, width: 480, maxWidth: "90vw",
          }} onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--c-text)", marginBottom: 20 }}>
              {editing ? "編輯記錄" : "新增交易記錄"}
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { label: "股票代號", key: "symbol", type: "text" },
                { label: "數量（股）", key: "quantity", type: "number" },
                { label: "進場價", key: "entry_price", type: "number" },
                { label: "出場價（可留空）", key: "exit_price", type: "number" },
              ].map(f => (
                <div key={f.key}>
                  <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>{f.label}</label>
                  <input type={f.type} value={(form as any)[f.key]}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    style={{ width: "100%", padding: "8px 10px", borderRadius: 6, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14 }} />
                </div>
              ))}
              <div>
                <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>方向</label>
                <select value={form.direction} onChange={e => setForm(prev => ({ ...prev, direction: e.target.value }))}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: 6, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14 }}>
                  <option value="buy">買進</option>
                  <option value="sell">賣出</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>情緒</label>
                <select value={form.emotion} onChange={e => setForm(prev => ({ ...prev, emotion: e.target.value }))}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: 6, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14 }}>
                  <option value="">未記錄</option>
                  {EMOTIONS.map(em => <option key={em} value={em}>{em}</option>)}
                </select>
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>策略</label>
              <input value={form.strategy} onChange={e => setForm(prev => ({ ...prev, strategy: e.target.value }))}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14 }} />
            </div>
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>備註</label>
              <textarea value={form.note} onChange={e => setForm(prev => ({ ...prev, note: e.target.value }))} rows={3}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14, resize: "vertical" }} />
            </div>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 20 }}>
              <button onClick={() => setShowForm(false)}
                style={{ padding: "8px 20px", borderRadius: 8, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text-dim)", cursor: "pointer" }}>
                取消
              </button>
              <button onClick={submit}
                style={{ padding: "8px 20px", borderRadius: 8, background: "#00c076", border: "none", color: "#000", cursor: "pointer", fontWeight: 600 }}>
                {editing ? "更新" : "新增"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
