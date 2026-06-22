"use client";
import { useEffect, useState, useCallback } from "react";

const API = "";

interface Notification {
  id: number;
  message: string;
  source: string;
  created_at: string;
  is_read: boolean;
}

const SOURCE_LABEL: Record<string, string> = {
  morning_brief: "晨報", alert: "警報", stop_loss: "停損",
  system: "系統", failed: "失敗", risk_manager: "風控",
};

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [totalUnread, setTotalUnread] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = useCallback(() => {
    fetch(`${API}/api/notifications?limit=100`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setItems(d.notifications ?? []);
          setTotalUnread(d.total_unread ?? 0);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchNotifications(); }, [fetchNotifications]);

  const markRead = async (id: number) => {
    await fetch(`${API}/api/notifications/${id}/read`, { method: "PATCH" });
    setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setTotalUnread(prev => Math.max(0, prev - 1));
  };

  const markAllRead = async () => {
    await fetch(`${API}/api/notifications/read-all`, { method: "PATCH" });
    setItems(prev => prev.map(n => ({ ...n, is_read: true })));
    setTotalUnread(0);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            🔔 通知中心
            {totalUnread > 0 && (
              <span style={{
                marginLeft: 8, fontSize: 12, padding: "2px 8px", borderRadius: 10,
                background: "#ff4d4d", color: "#fff", fontWeight: 700,
              }}>{totalUnread}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginTop: 2 }}>
            Telegram 警報歷史紀錄
          </div>
        </div>
        {totalUnread > 0 && (
          <button onClick={markAllRead} style={{
            padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 13,
            background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
            color: "var(--c-text-dim)",
          }}>全部標記已讀</button>
        )}
      </div>

      {loading && <div style={{ color: "var(--c-text-dim)", fontSize: 14 }}>載入中...</div>}

      {!loading && items.length === 0 && (
        <div style={{
          background: "var(--c-bg-card)", border: "1px solid var(--c-border)",
          borderRadius: 8, padding: "40px 16px", textAlign: "center",
          color: "var(--c-text-dim)", fontSize: 14,
        }}>
          尚無通知紀錄。觸發警報或 AI 分析後，訊息將自動記錄於此。
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {items.map(n => (
          <div
            key={n.id}
            onClick={() => !n.is_read && markRead(n.id)}
            style={{
              background: n.is_read ? "var(--c-bg-card)" : "var(--c-bg-deep)",
              border: `1px solid ${n.is_read ? "var(--c-border)" : "#3d7eff44"}`,
              borderLeft: `3px solid ${n.is_read ? "var(--c-border)" : "#3d7eff"}`,
              borderRadius: 8, padding: "10px 14px",
              cursor: n.is_read ? "default" : "pointer",
              transition: "all 0.15s",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{
                  fontSize: 10, padding: "1px 6px", borderRadius: 4, fontWeight: 700,
                  background: "var(--c-bg-main)", border: "1px solid var(--c-border)",
                  color: n.source === "failed" ? "#ff4d4d" : "var(--c-text-dim)",
                }}>
                  {SOURCE_LABEL[n.source] ?? n.source}
                </span>
                {!n.is_read && (
                  <span style={{ fontSize: 10, color: "#3d7eff", fontWeight: 700 }}>● 未讀</span>
                )}
              </div>
              <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>
                {n.created_at?.slice(0, 16).replace("T", " ")}
              </span>
            </div>
            <div style={{
              fontSize: 12, color: "var(--c-text-mid)", lineHeight: 1.6,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {n.message.slice(0, 300)}{n.message.length > 300 ? "…" : ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
