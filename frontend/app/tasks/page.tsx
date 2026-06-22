"use client";
import { useAppContext } from "@/contexts/AppContext";

const FLOWER_URL = process.env.NEXT_PUBLIC_FLOWER_URL || "http://localhost:5555";

export default function TasksPage() {
  const { theme } = useAppContext();
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid var(--c-border)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "var(--c-bg)",
        flexShrink: 0,
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--c-text)" }}>
            🌸 任務監控
          </h1>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--c-text-dim)" }}>
            Celery Worker · Flower UI
          </p>
        </div>
        <a
          href={FLOWER_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            fontSize: 12, color: "#00c076", textDecoration: "none",
            padding: "4px 10px", border: "1px solid #00c07644",
            borderRadius: 6,
          }}
        >
          ↗ 新分頁開啟
        </a>
      </div>

      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <iframe
          src={FLOWER_URL}
          style={{
            width: "100%",
            height: "100%",
            border: "none",
            filter: theme === "dark" ? "invert(1) hue-rotate(180deg)" : "none",
          }}
          title="Flower Task Monitor"
        />
      </div>
    </div>
  );
}
