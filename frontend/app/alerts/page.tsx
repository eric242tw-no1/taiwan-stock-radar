"use client";
import { useState, useEffect, useCallback } from "react";

// ── 型別 ──────────────────────────────────────────────────────────
type Metric = "ai_score" | "rsi" | "deviation" | "change_pct" | "days_to_settlement";
type Op     = "gte" | "lte" | "gt" | "lt";

interface Alert {
  id: string;
  symbol: string;
  metric: Metric;
  op: Op;
  threshold: number;
  enabled: boolean;
  triggered: boolean;
}

interface TriggerRecord {
  id: string;
  symbol: string;
  name: string;
  metric: Metric;
  op: Op;
  threshold: number;
  triggeredAt: string;
}

interface LiveSnapshot {
  name: string;
  ai_score: number;
  rsi: number;
  deviation: number;
  change_pct: number;
  days_to_settlement: number;
}

// ── 常數 ──────────────────────────────────────────────────────────
const ALERT_KEY   = "tw_radar_alerts";
const HISTORY_KEY = "tw_radar_alert_history";
const API = "";

const METRIC_LABEL: Record<Metric, string> = {
  ai_score:            "AI 分數",
  rsi:                 "RSI",
  deviation:           "MA20 乖離率 %",
  change_pct:          "當日漲跌幅 %",
  days_to_settlement:  "結算剩餘天數",
};
const OP_LABEL: Record<Op, string> = { gte: "≥", lte: "≤", gt: ">", lt: "<" };

// ── localStorage helpers ──────────────────────────────────────────
function loadAlerts(): Alert[] {
  try { return JSON.parse(localStorage.getItem(ALERT_KEY) || "[]"); } catch { return []; }
}
function saveAlerts(arr: Alert[]) { localStorage.setItem(ALERT_KEY, JSON.stringify(arr)); }

function loadHistory(): TriggerRecord[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); } catch { return []; }
}
function saveHistory(arr: TriggerRecord[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(arr.slice(0, 50)));
}

// ── 規則求值 ──────────────────────────────────────────────────────
function evalAlert(a: Alert, snap: LiveSnapshot): boolean {
  const val = snap[a.metric];
  if (val === undefined) return false;
  if (a.op === "gte") return val >= a.threshold;
  if (a.op === "lte") return val <= a.threshold;
  if (a.op === "gt")  return val >  a.threshold;
  if (a.op === "lt")  return val <  a.threshold;
  return false;
}

// ── 共用卡片外框（與其他頁一致）──────────────────────────────────
function Card({ title, children, extra }: {
  title: string; children: React.ReactNode; extra?: React.ReactNode;
}) {
  return (
    <div style={{ background: "#111118", border: "1px solid #2a2a3a", borderRadius: 8, padding: 14, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: "#8888aa", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase" }}>
          {title}
        </div>
        {extra}
      </div>
      {children}
    </div>
  );
}

// ── Toggle 開關 ───────────────────────────────────────────────────
function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      style={{
        width: 40, height: 22, borderRadius: 11, border: "none", cursor: "pointer",
        background: on ? "#00c07666" : "#2a2a3a", padding: 2,
        display: "flex", alignItems: "center",
        justifyContent: on ? "flex-end" : "flex-start",
        transition: "background 0.2s",
        flexShrink: 0,
      }}
    >
      <span style={{
        width: 18, height: 18, borderRadius: "50%",
        background: on ? "#00c076" : "#555570",
        display: "block", transition: "background 0.2s",
      }} />
    </button>
  );
}

// ── 單筆警報卡 ────────────────────────────────────────────────────
function AlertCard({
  alert, live, onToggle, onDelete,
}: {
  alert: Alert;
  live: LiveSnapshot | undefined;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const liveVal = live ? live[alert.metric] : undefined;
  const statusColor = alert.triggered ? "#f5a623" : alert.enabled ? "#00c076" : "#555570";
  const statusText  = alert.triggered ? "已觸發" : alert.enabled ? "監控中" : "已停用";
  const borderColor = alert.triggered ? "#f5a62344" : "1px solid #2a2a3a";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      background: "#0d0d15", borderRadius: 8, padding: "10px 12px",
      border: `1px solid ${alert.triggered ? "#f5a62355" : "#2a2a3a"}`,
      opacity: alert.enabled ? 1 : 0.6,
    }}>
      {/* 左：代號 + 條件 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#3d7eff" }}>{alert.symbol}</span>
          <span style={{
            fontSize: 11, padding: "1px 6px", borderRadius: 3,
            background: `${statusColor}22`, border: `1px solid ${statusColor}55`,
            color: statusColor, fontWeight: 600,
          }}>
            {statusText}
          </span>
        </div>
        <div style={{ fontSize: 13, color: "#8888aa" }}>
          {METRIC_LABEL[alert.metric]}{" "}
          <span style={{ color: "#c8c8d8" }}>{OP_LABEL[alert.op]} {alert.threshold}</span>
          {liveVal !== undefined && (
            <span style={{ color: "#555570", marginLeft: 6 }}>（目前 {liveVal}）</span>
          )}
        </div>
      </div>

      {/* 右：toggle + 刪除 */}
      <Toggle on={alert.enabled} onChange={onToggle} />
      <button
        onClick={onDelete}
        style={{
          background: "transparent", border: "1px solid #2a2a3a",
          borderRadius: 6, color: "#555570", cursor: "pointer",
          fontSize: 12, padding: "3px 8px",
        }}
      >
        刪除
      </button>
    </div>
  );
}

// ── RWD hook ──────────────────────────────────────────────────────
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

// ── 主頁面 ────────────────────────────────────────────────────────
export default function AlertsPage() {
  const isMobile = useIsMobile();
  const [alerts,  setAlerts]  = useState<Alert[]>([]);
  const [history, setHistory] = useState<TriggerRecord[]>([]);
  const [live,    setLive]    = useState<Record<string, LiveSnapshot>>({});

  // 表單狀態
  const [symbol,    setSymbol]    = useState("");
  const [metric,    setMetric]    = useState<Metric>("ai_score");
  const [op,        setOp]        = useState<Op>("gte");
  const [threshold, setThreshold] = useState("");
  const [hint,      setHint]      = useState<{ msg: string; ok: boolean } | null>(null);

  // ── 初始載入 ──────────────────────────────────────────────────
  useEffect(() => {
    const stored = loadAlerts();
    if (stored.length === 0) {
      // 植入三筆 demo 讓使用者立刻看到效果
      const demo: Alert[] = [
        { id: "d1", symbol: "2330", metric: "deviation",  op: "gte", threshold: 10,  enabled: true,  triggered: false },
        { id: "d2", symbol: "2317", metric: "ai_score",   op: "lte", threshold: 45,  enabled: true,  triggered: false },
        { id: "d3", symbol: "2454", metric: "rsi",        op: "gte", threshold: 70,  enabled: false, triggered: false },
      ];
      saveAlerts(demo);
      setAlerts(demo);
    } else {
      setAlerts(stored);
    }
    setHistory(loadHistory());
  }, []);

  // ── 拉即時快照（/api/market/leaders 已有 ai_score + rsi）────────
  const fetchLive = useCallback(async () => {
    try {
      const [leadersRes, moversRes] = await Promise.all([
        fetch(`${API}/api/market/leaders?limit=20`),
        fetch(`${API}/api/market/top-movers?limit=20`),
      ]);
      const merged: Record<string, LiveSnapshot> = {};
      if (leadersRes.ok) {
        const d = await leadersRes.json();
        (d.results ?? []).forEach((r: { code: string; name: string; score: number; rsi: number }) => {
          merged[r.code] = {
            name: r.name,
            ai_score: r.score,
            rsi: r.rsi,
            deviation: 0,
            change_pct: 0,
            days_to_settlement: 0,
          };
        });
      }
      if (moversRes.ok) {
        const d = await moversRes.json();
        (d.results ?? []).forEach((r: { code: string; name: string; price: number; chg_pct: number }) => {
          if (merged[r.code]) {
            merged[r.code].change_pct = r.chg_pct;
          } else {
            merged[r.code] = { name: r.name, ai_score: 0, rsi: 0, deviation: 0, change_pct: r.chg_pct, days_to_settlement: 0 };
          }
        });
      }
      if (Object.keys(merged).length > 0) setLive(merged);
    } catch {}
  }, []);

  useEffect(() => {
    fetchLive();
    const id = setInterval(fetchLive, 60_000);
    return () => clearInterval(id);
  }, [fetchLive]);

  // ── 每 30 秒跑規則引擎 ───────────────────────────────────────
  useEffect(() => {
    const check = () => {
      const current = loadAlerts();
      const hist    = loadHistory();
      let changed   = false;

      current.forEach((a) => {
        if (!a.enabled) return;
        const snap = live[a.symbol];
        if (!snap) return;
        const fired = evalAlert(a, snap);
        if (fired && !a.triggered) {
          a.triggered = true;
          hist.unshift({
            id: a.id, symbol: a.symbol, name: snap.name,
            metric: a.metric, op: a.op, threshold: a.threshold,
            triggeredAt: new Date().toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          });
          changed = true;
        } else if (!fired && a.triggered) {
          a.triggered = false;
          changed = true;
        }
      });

      if (changed) {
        saveAlerts(current);
        saveHistory(hist);
        setAlerts([...current]);
        setHistory([...hist]);
      }
    };

    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, [live]);

  // ── 表單新增 ──────────────────────────────────────────────────
  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const sym = symbol.trim().toUpperCase();
    const thr = parseFloat(threshold);
    if (!sym || isNaN(thr)) {
      setHint({ msg: "請填寫股票代號與有效閾值", ok: false });
      return;
    }
    const next: Alert = { id: Date.now().toString(), symbol: sym, metric, op, threshold: thr, enabled: true, triggered: false };
    const updated = [next, ...alerts];
    saveAlerts(updated);
    setAlerts(updated);
    setSymbol(""); setThreshold("");
    setHint({ msg: `已新增 ${sym} 的 ${METRIC_LABEL[metric]} 警報`, ok: true });
    fetchLive();
  }

  function toggle(id: string) {
    const updated = alerts.map((a) =>
      a.id === id ? { ...a, enabled: !a.enabled, triggered: a.enabled ? false : a.triggered } : a
    );
    saveAlerts(updated); setAlerts(updated);
  }

  function del(id: string) {
    const updated = alerts.filter((a) => a.id !== id);
    saveAlerts(updated); setAlerts(updated);
  }

  function clearTriggered() {
    const updated = alerts.map((a) => ({ ...a, triggered: false }));
    saveAlerts(updated); setAlerts(updated);
  }

  function clearHistory() {
    saveHistory([]); setHistory([]);
  }

  const triggeredCount = alerts.filter((a) => a.triggered).length;

  // ── input / select 共用樣式 ───────────────────────────────────
  const inputStyle: React.CSSProperties = {
    background: "#0d0d15", border: "1px solid #2a2a3a", borderRadius: 6,
    color: "#e8e8f0", padding: "6px 10px", fontSize: 13, width: "100%",
  };

  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>

      {/* ── 頁首 ── */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: "#3d7eff", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Alerts</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h1 style={{ margin: 0, fontSize: 24, color: "#e8e8f0", fontWeight: 700 }}>警報設定</h1>
          <div style={{ fontSize: 11, color: "#555570", background: "#111118", border: "1px solid #2a2a3a", borderRadius: 6, padding: "4px 10px" }}>
            <span style={{ color: "#00c076", marginRight: 4 }}>●</span>本地規則引擎 · 30 秒掃描
          </div>
        </div>
      </div>

      {/* ── 新增警報 ── */}
      <Card title="新增條件警報">
        <form onSubmit={handleAdd}>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "110px 1fr 1fr 100px", gap: 8, marginBottom: 8 }}>
            <div>
              <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>股票代號</div>
              <input style={inputStyle} placeholder="2330" maxLength={6}
                value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>警報條件</div>
              <select style={inputStyle} value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
                {(Object.entries(METRIC_LABEL) as [Metric, string][]).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>比較</div>
              <select style={inputStyle} value={op} onChange={(e) => setOp(e.target.value as Op)}>
                <option value="gte">≥ 大於等於</option>
                <option value="lte">≤ 小於等於</option>
                <option value="gt">&gt; 大於</option>
                <option value="lt">&lt; 小於</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#555570", marginBottom: 4 }}>閾值</div>
              <input style={inputStyle} type="number" step="any" placeholder="70"
                value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: isMobile ? "flex-start" : "center", flexDirection: isMobile ? "column" : "row", gap: 10 }}>
            <button type="submit" style={{
              background: "#003d20", border: "1px solid #00c07655", borderRadius: 6,
              color: "#00c076", fontSize: 13, padding: "7px 18px", cursor: "pointer", fontWeight: 600,
            }}>
              ＋ 新增警報
            </button>
            {hint && (
              <span style={{ fontSize: 12, color: hint.ok ? "#00c076" : "#ff4d4d" }}>{hint.msg}</span>
            )}
          </div>
        </form>
      </Card>

      {/* ── 警報清單 ── */}
      <Card
        title={`警報清單（${alerts.length}）${triggeredCount > 0 ? ` · ${triggeredCount} 筆已觸發` : ""}`}
        extra={
          <button onClick={clearTriggered} style={{
            background: "transparent", border: "1px solid #2a2a3a", borderRadius: 6,
            color: "#555570", cursor: "pointer", fontSize: 12, padding: "3px 8px",
          }}>
            清除觸發狀態
          </button>
        }
      >
        {alerts.length === 0 ? (
          <div style={{ fontSize: 13, color: "#555570", textAlign: "center", padding: "20px 0" }}>
            尚未設定任何警報，請使用上方表單新增。
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {alerts.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                live={live[a.symbol]}
                onToggle={() => toggle(a.id)}
                onDelete={() => del(a.id)}
              />
            ))}
          </div>
        )}
      </Card>

      {/* ── 觸發紀錄 ── */}
      <Card
        title="近期觸發紀錄"
        extra={
          <button onClick={clearHistory} style={{
            background: "transparent", border: "1px solid #2a2a3a", borderRadius: 6,
            color: "#555570", cursor: "pointer", fontSize: 12, padding: "3px 8px",
          }}>
            清除紀錄
          </button>
        }
      >
        {history.length === 0 ? (
          <div style={{ fontSize: 13, color: "#555570", textAlign: "center", padding: "20px 0" }}>
            尚無觸發紀錄。
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {history.map((h, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: "#0d0d15", border: "1px solid #f5a62333", borderRadius: 8, padding: "9px 12px",
              }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#3d7eff" }}>{h.symbol}</span>
                    <span style={{ fontSize: 12, color: "#8888aa" }}>{h.name}</span>
                    <span style={{ fontSize: 11, padding: "1px 6px", borderRadius: 3,
                      background: "#f5a62322", border: "1px solid #f5a62355", color: "#f5a623" }}>
                      已觸發
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "#555570" }}>
                    {METRIC_LABEL[h.metric]} {OP_LABEL[h.op]} {h.threshold}
                  </div>
                </div>
                <span style={{ fontSize: 12, color: "#555570", flexShrink: 0 }}>{h.triggeredAt}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
