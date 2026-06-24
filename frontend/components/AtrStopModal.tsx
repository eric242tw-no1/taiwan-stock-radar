"use client";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface AtrResult {
  symbol: string; atr_14: number; multiplier: number;
  ref_price: number; stop_loss: number; stop_pct: number;
}

interface Props {
  symbol: string;
  onClose: () => void;
}

export default function AtrStopModal({ symbol, onClose }: Props) {
  const [multiplier, setMultiplier] = useState(2.0);
  const [entryPrice, setEntryPrice] = useState("");
  const [result, setResult] = useState<AtrResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const calculate = async () => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ multiplier: String(multiplier) });
      if (entryPrice) params.set("entry_price", entryPrice);
      const res = await fetch(`${API}/api/risk/atr-stop/${symbol}?${params}`);
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "計算失敗"); }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message ?? "計算失敗");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "#00000088", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
        borderRadius: 14, padding: 28, width: 400, maxWidth: "90vw",
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--c-text)" }}>ATR 停損計算 — {symbol}</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--c-text-dim)", fontSize: 20, cursor: "pointer" }}>×</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>ATR 倍數</label>
            <input type="number" step="0.1" min="0.5" max="5" value={multiplier}
              onChange={e => setMultiplier(Number(e.target.value))}
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 15 }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>進場價（留空用最新收盤價）</label>
            <input type="number" step="0.1" value={entryPrice} onChange={e => setEntryPrice(e.target.value)}
              placeholder="自動使用最新收盤價"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 15 }} />
          </div>
          <button onClick={calculate} disabled={loading}
            style={{ padding: "10px 0", borderRadius: 8, background: "#00c076", border: "none", color: "#000", cursor: "pointer", fontWeight: 600, fontSize: 15 }}>
            {loading ? "計算中..." : "計算停損"}
          </button>
        </div>

        {error && <div style={{ marginTop: 16, color: "#ef4444", fontSize: 14 }}>{error}</div>}

        {result && (
          <div style={{ marginTop: 20, background: "var(--c-bg)", borderRadius: 10, padding: 16, border: "1px solid var(--c-border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { label: "ATR(14)", value: result.atr_14.toFixed(4) },
                { label: "參考價", value: result.ref_price },
                { label: "停損價", value: result.stop_loss, color: "#ef4444" },
                { label: "停損幅度", value: `${result.stop_pct}%`, color: "#ef4444" },
              ].map(item => (
                <div key={item.label} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginBottom: 2 }}>{item.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: (item as any).color ?? "var(--c-text)" }}>{item.value}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: "var(--c-text-dim)", textAlign: "center" }}>
              停損距離 = ATR(14) × {result.multiplier} = {(result.atr_14 * result.multiplier).toFixed(4)} 元
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
