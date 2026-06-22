"use client";
import { useEffect, useState } from "react";

const API = "";

const EVENT_TYPE_LABEL: Record<string, string> = {
  dividend: "除息", rights: "除權",
  investor_conference: "法說會", earnings: "財報",
  sentinel: "",
};
const EVENT_TYPE_COLOR: Record<string, string> = {
  dividend: "#00c076", rights: "#3d7eff",
  investor_conference: "#f5a623", earnings: "#cc44ff",
};

interface CalEvent {
  symbol: string; name: string;
  event_type: string; date: string; description: string;
}

function groupByDate(events: CalEvent[]): Record<string, CalEvent[]> {
  return events.reduce((acc, e) => {
    if (!acc[e.date]) acc[e.date] = [];
    acc[e.date].push(e);
    return acc;
  }, {} as Record<string, CalEvent[]>);
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/calendar/events?days=${days}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setEvents((d.events ?? []).filter((e: CalEvent) => e.event_type !== "sentinel")))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  const grouped = groupByDate(events);
  const dates = Object.keys(grouped).sort();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>📅 財報日曆</div>
          <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginTop: 2 }}>
            除息・除權・法說會・財報公布
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {[14, 30, 60].map(d => (
            <button key={d} onClick={() => setDays(d)} style={{
              padding: "5px 14px", borderRadius: 6, cursor: "pointer", fontSize: 13,
              background: days === d ? "var(--c-bg-deep)" : "transparent",
              border: `1px solid ${days === d ? "#00c076" : "var(--c-border)"}`,
              color: days === d ? "#00c076" : "var(--c-text-dim)",
            }}>未來 {d} 天</button>
          ))}
        </div>
      </div>

      {/* 圖例 */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {Object.entries(EVENT_TYPE_LABEL).filter(([k]) => k !== "sentinel").map(([type, label]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--c-text-dim)" }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: EVENT_TYPE_COLOR[type] ?? "var(--c-border)" }} />
            {label}
          </div>
        ))}
      </div>

      {loading && <div style={{ color: "var(--c-text-dim)", fontSize: 14 }}>載入中...</div>}

      {!loading && dates.length === 0 && (
        <div style={{
          background: "var(--c-bg-card)", border: "1px solid var(--c-border)",
          borderRadius: 8, padding: "40px 16px", textAlign: "center",
          color: "var(--c-text-dim)", fontSize: 14,
        }}>
          未來 {days} 天無財報事件。<br />
          需設定 FINMIND_TOKEN 且後端已啟動才能取得資料。
        </div>
      )}

      {/* 事件列表（依日期分組）*/}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {dates.map(date => (
          <div key={date} style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, overflow: "hidden" }}>
            {/* 日期標頭 */}
            <div style={{
              padding: "8px 14px", background: "var(--c-bg-deep)",
              borderBottom: "1px solid var(--c-border)",
              fontSize: 13, fontWeight: 700, color: "var(--c-text-mid)",
            }}>
              {date}
            </div>
            {/* 事件列表 */}
            <div style={{ padding: "8px 0" }}>
              {grouped[date].map((e, i) => {
                const color = EVENT_TYPE_COLOR[e.event_type] ?? "var(--c-text-dim)";
                const label = EVENT_TYPE_LABEL[e.event_type] ?? e.event_type;
                return (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "7px 14px",
                    borderBottom: i < grouped[date].length - 1 ? "1px solid var(--c-border)" : "none",
                  }}>
                    <span style={{
                      fontSize: 11, padding: "2px 7px", borderRadius: 4, fontWeight: 700,
                      background: `${color}22`, border: `1px solid ${color}66`, color,
                      whiteSpace: "nowrap",
                    }}>{label}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#3d7eff", width: 48 }}>{e.symbol}</span>
                    <span style={{ fontSize: 13, color: "var(--c-text-mid)" }}>{e.name}</span>
                    <span style={{ fontSize: 11, color: "var(--c-text-dim)", marginLeft: "auto" }}>{e.description}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
