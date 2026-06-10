"use client";
import { useEffect, useState } from "react";

export function fngColor(v: number) {
  return v >= 75 ? "#00e676" : v >= 55 ? "#69f0ae" : v >= 45 ? "#ffd600" : v >= 25 ? "#ff6d00" : "#ff1744";
}
export function fngLabel(v: number) {
  return v >= 75 ? "極度貪婪" : v >= 55 ? "貪婪" : v >= 45 ? "中性" : v >= 25 ? "恐懼" : "極度恐懼";
}

export function FearGreedGauge({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDisplayed(value), 300);
    return () => clearTimeout(t);
  }, [value]);
  const cx = 160, cy = 140;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  function arcPath(a1: number, a2: number, innerR: number, outerR: number) {
    const p1o = { x: cx + outerR * Math.cos(toRad(a1)), y: cy + outerR * Math.sin(toRad(a1)) };
    const p2o = { x: cx + outerR * Math.cos(toRad(a2)), y: cy + outerR * Math.sin(toRad(a2)) };
    const p1i = { x: cx + innerR * Math.cos(toRad(a1)), y: cy + innerR * Math.sin(toRad(a1)) };
    const p2i = { x: cx + innerR * Math.cos(toRad(a2)), y: cy + innerR * Math.sin(toRad(a2)) };
    return `M ${p1o.x} ${p1o.y} A ${outerR} ${outerR} 0 0 1 ${p2o.x} ${p2o.y} L ${p2i.x} ${p2i.y} A ${innerR} ${innerR} 0 0 0 ${p1i.x} ${p1i.y} Z`;
  }
  const needleAngle = 180 + (displayed / 100) * 180;
  const nX = cx + 90 * Math.cos(toRad(needleAngle));
  const nY = cy + 90 * Math.sin(toRad(needleAngle));
  const color = fngColor(displayed);
  return (
    <svg viewBox="0 0 320 155" style={{ width: "100%", overflow: "visible" }}>
      <defs>
        <filter id="fng-glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <path d={arcPath(180, 360, 88, 118)} fill="var(--c-border)" />
      <path d={arcPath(180, 207, 90, 116)} fill="#b71c1c" opacity={0.85} />
      <path d={arcPath(207, 234, 90, 116)} fill="#f44336" opacity={0.85} />
      <path d={arcPath(234, 261, 90, 116)} fill="#ff6d00" opacity={0.85} />
      <path d={arcPath(261, 288, 90, 116)} fill="#ffd600" opacity={0.85} />
      <path d={arcPath(288, 315, 90, 116)} fill="#69f0ae" opacity={0.85} />
      <path d={arcPath(315, 360, 90, 116)} fill="#00e676" opacity={0.85} />
      <path d={arcPath(180, 360, 82, 92)} fill="var(--c-bg-deep)" opacity={0.6} />
      {([0, 25, 50, 75, 100] as const).map(t => {
        const a = 180 + (t / 100) * 180;
        return (
          <text key={`tick-${t}`}
            x={cx + 130 * Math.cos(toRad(a))} y={cy + 130 * Math.sin(toRad(a))}
            textAnchor="middle" dominantBaseline="middle" fontSize="12"
            fill="var(--c-label)" fontFamily="'JetBrains Mono', monospace">{t}</text>
        );
      })}
      <line x1={cx} y1={cy} x2={nX} y2={nY}
        stroke={color} strokeWidth="3" strokeLinecap="round"
        filter="url(#fng-glow)"
        style={{ transition: "all 1.2s cubic-bezier(.34,1.56,.64,1)" }} />
      <circle cx={cx} cy={cy} r="8" fill={color} filter="url(#fng-glow)" />
      <circle cx={cx} cy={cy} r="4" fill="var(--c-bg-deep)" />
      <text x={cx} y={cy - 28} textAnchor="middle" fontSize="38" fontWeight="700"
        fill={color} fontFamily="'JetBrains Mono', monospace" filter="url(#fng-glow)">{displayed}</text>
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize="15"
        fill={color} fontFamily="'Noto Sans TC', sans-serif" fontWeight="600">{fngLabel(displayed)}</text>
    </svg>
  );
}

export function VixCard({
  value,
  chg,
  level,
}: {
  value: string;
  chg: string;
  level: "low" | "medium" | "high";
}) {
  const map = {
    low:    { color: "#00c076", bg: "#003d20", text: "低恐慌", note: "VIX < 20 多頭有利" },
    medium: { color: "#f5a623", bg: "#3d2a00", text: "中性波動", note: "VIX 20-30 謹慎操作" },
    high:   { color: "#ff4d4d", bg: "#3d0000", text: "高恐慌", note: "VIX > 30 注意風險" },
  };
  const { color, bg, text, note } = map[level];
  return (
    <div style={{ background: bg, border: `1px solid ${color}55`, borderRadius: 10, padding: "20px 24px", width: "100%" }}>
      <div style={{ fontSize: 14, color: "var(--c-text-dim)", marginBottom: 8, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono',monospace" }}>
        VIX 恐慌指數
      </div>
      <div style={{ fontSize: 42, fontWeight: 700, color: "var(--c-text)", fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 18, color, marginTop: 6, fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{chg}</div>
      <div style={{ marginTop: 12, fontSize: 15, color, fontWeight: 700, padding: "4px 12px", background: `${color}22`, borderRadius: 6, border: `1px solid ${color}66`, display: "inline-block", letterSpacing: 0.5 }}>
        {text}
      </div>
      <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>{note}</div>
    </div>
  );
}
