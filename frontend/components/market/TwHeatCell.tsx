"use client";
import { useRouter } from "next/navigation";

export function TwHeatCell({ label, chg }: { label: string; chg: number }) {
  const router = useRouter();
  const color = chg > 2 ? "#ff4d4d" : chg > 0 ? "#cc3333" : chg > -2 ? "#009955" : "#00c076";
  const bg    = chg > 2 ? "#3d0000" : chg > 0 ? "#2a0a0a" : chg > -2 ? "#002210" : "#003d20";
  return (
    <div
      onClick={() => router.push(`/industry?s=${encodeURIComponent(label)}`)}
      style={{ background: bg, border: `1px solid ${color}55`, borderRadius: 6, padding: "8px 6px", textAlign: "center", cursor: "pointer", transition: "all 0.15s" }}
      onMouseEnter={e => { e.currentTarget.style.filter = "brightness(1.3)"; e.currentTarget.style.boxShadow = `0 0 10px ${color}55`; }}
      onMouseLeave={e => { e.currentTarget.style.filter = "brightness(1)"; e.currentTarget.style.boxShadow = "none"; }}
      title={`查看${label}產業個股`}
    >
      <div style={{ fontSize: 14, color: "var(--c-text-mid)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {chg > 0 ? "+" : ""}{chg}%
      </div>
    </div>
  );
}
