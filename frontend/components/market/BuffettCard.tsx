"use client";
import { useEffect, useState } from "react";
import { Card } from "./Card";

interface BuffettData {
  ratio: number;
  market_cap_yi?: number;
  gdp_yi?: number;
  gdp_year?: number;
  updated_at?: string;
  source?: string;
  // legacy
  market_cap_nt?: number;
  gdp_nt?: number;
  date?: string;
}

const BUFFETT_ZONES = [
  { max: 150, label: "低估區間", color: "#3d7eff", bg: "#0a1a3d" },
  { max: 250, label: "合理區間", color: "#00c076", bg: "#003d20" },
  { max: 350, label: "高估區間", color: "#f5a623", bg: "#3d2a00" },
  { max: 999, label: "嚴重過熱", color: "#ff4d4d", bg: "#3d0000" },
];

function buffettZone(ratio: number) {
  return BUFFETT_ZONES.find(z => ratio < z.max) ?? BUFFETT_ZONES[BUFFETT_ZONES.length - 1];
}

export function BuffettCard() {
  const [data, setData] = useState<BuffettData | null | "unavailable">(null);

  useEffect(() => {
    fetch("/api/market/buffett")
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.ratio != null) setData(d);
        else setData("unavailable");
      })
      .catch(() => setData("unavailable"));
  }, []);

  const demo: BuffettData = {
    ratio: 243.5,
    market_cap_yi: 601_450,
    gdp_yi: 247_000,
    gdp_year: 2024,
    source: "demo",
  };
  const d = data === "unavailable" ? demo : (data ?? null);
  const toZhao = (yi?: number) => yi ? (yi / 10_000).toFixed(1) : null;
  const zone = d ? buffettZone(d.ratio) : null;

  const BAR_MAX = 400;
  const segments = [
    { from: 0,   to: 150, color: "#3d7eff33", border: "#3d7eff" },
    { from: 150, to: 250, color: "#00c07633", border: "#00c076" },
    { from: 250, to: 350, color: "#f5a62333", border: "#f5a623" },
    { from: 350, to: 400, color: "#ff4d4d33", border: "#ff4d4d" },
  ];

  return (
    <Card title="巴菲特指標・台股">
      {d === null ? (
        <div style={{ color: "var(--c-text-dim)", fontSize: 13, padding: "40px 0", textAlign: "center" }}>載入中…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* 數值 + 區間標籤 */}
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--c-label)", letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono',monospace", marginBottom: 4 }}>
                市值 / GDP
              </div>
              <div style={{ fontSize: 44, fontWeight: 700, color: zone!.color, fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>
                {d.ratio.toFixed(1)}<span style={{ fontSize: 22 }}>%</span>
              </div>
            </div>
            <div style={{ marginBottom: 6, padding: "4px 12px", borderRadius: 6, background: `${zone!.color}22`, border: `1px solid ${zone!.color}66`, color: zone!.color, fontSize: 14, fontWeight: 700, letterSpacing: 0.5 }}>
              {zone!.label}
            </div>
          </div>

          {/* 橫向量表 */}
          <div>
            <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", height: 12, marginBottom: 6 }}>
              {segments.map((seg, i) => (
                <div key={i} style={{
                  width: `${((seg.to - seg.from) / BAR_MAX) * 100}%`,
                  background: seg.color,
                  borderRight: i < segments.length - 1 ? `1px solid ${seg.border}` : undefined,
                }} />
              ))}
            </div>
            <div style={{ position: "relative", height: 16, marginBottom: 2 }}>
              <div style={{ position: "absolute", left: `${Math.min((d.ratio / BAR_MAX) * 100, 98)}%`, transform: "translateX(-50%)", fontSize: 12, color: zone!.color, fontWeight: 700 }}>▲</div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--c-text-dim)" }}>
              {[0, 150, 250, 350, 400].map(v => <span key={v}>{v}%</span>)}
            </div>
          </div>

          {/* 細節 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 5, borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
            {[
              { label: "台股總市值", value: toZhao(d.market_cap_yi) ? `${toZhao(d.market_cap_yi)} 兆` : (d.market_cap_nt ? `${d.market_cap_nt.toFixed(1)} 兆` : "---") },
              { label: "台灣 GDP",   value: toZhao(d.gdp_yi) ? `${toZhao(d.gdp_yi)} 兆 (${d.gdp_year ?? ""})` : (d.gdp_nt ? `${d.gdp_nt.toFixed(1)} 兆` : "---") },
              { label: "資料來源",   value: d.source === "twse" ? "TWSE 官方" : d.source === "taiex_estimated" ? "指數估算" : "估算" },
            ].map(r => (
              <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 17 }}>
                <span style={{ color: "var(--c-text-dim)" }}>{r.label}</span>
                <span style={{ color: "var(--c-text)", fontFamily: "'JetBrains Mono',monospace" }}>{r.value}</span>
              </div>
            ))}
          </div>

          {/* 說明 */}
          <div style={{ fontSize: 14, color: "var(--c-text-dim)", lineHeight: 1.6, borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
            {data === "unavailable" && <span style={{ color: "#f5a623" }}>⚠ 使用估算數據 · </span>}
            台灣標準：&lt;150% 低估｜150-250% 合理｜250-350% 高估｜&gt;350% 過熱
          </div>
        </div>
      )}
    </Card>
  );
}
