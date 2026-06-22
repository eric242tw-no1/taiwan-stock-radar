"use client";
import { useState } from "react";

export default function PositionSizer() {
  const [capital, setCapital] = useState(1000000);
  const [riskPct, setRiskPct] = useState(2);
  const [entryPrice, setEntryPrice] = useState(500);
  const [stopPrice, setStopPrice] = useState(480);

  const riskAmount = capital * (riskPct / 100);
  const priceRisk = Math.abs(entryPrice - stopPrice);
  const shares = priceRisk > 0 ? Math.floor(riskAmount / priceRisk / 1000) * 1000 : 0;
  const cost = shares * entryPrice;
  const positionPct = capital > 0 ? (cost / capital) * 100 : 0;

  const inputStyle = {
    width: "100%", padding: "8px 10px", borderRadius: 8,
    background: "var(--c-bg)", border: "1px solid var(--c-border)",
    color: "var(--c-text)", fontSize: 15,
  };

  return (
    <div style={{ background: "var(--c-bg-deep)", border: "1px solid var(--c-border)", borderRadius: 12, padding: 20 }}>
      <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--c-text)", marginBottom: 16 }}>🎯 部位計算器</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>總資金（元）</label>
          <input type="number" value={capital} onChange={e => setCapital(Number(e.target.value))} step="10000" style={inputStyle} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>單次風險（%）</label>
          <input type="number" value={riskPct} onChange={e => setRiskPct(Number(e.target.value))} step="0.1" min="0.1" max="10" style={inputStyle} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>進場價</label>
          <input type="number" value={entryPrice} onChange={e => setEntryPrice(Number(e.target.value))} step="0.5" style={inputStyle} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>停損價</label>
          <input type="number" value={stopPrice} onChange={e => setStopPrice(Number(e.target.value))} step="0.5" style={inputStyle} />
        </div>
      </div>

      <div style={{ background: "var(--c-bg)", borderRadius: 8, padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--c-text-dim)" }}>建議股數</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#00c076" }}>{shares.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--c-text-dim)" }}>總成本</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--c-text)" }}>{cost.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--c-text-dim)" }}>倉位比例</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: positionPct > 30 ? "#ef4444" : "var(--c-text)" }}>
            {positionPct.toFixed(1)}%
          </div>
        </div>
      </div>
      <div style={{ marginTop: 10, fontSize: 12, color: "var(--c-text-dim)" }}>
        單次風險金額：{riskAmount.toLocaleString()} 元　每股風險：{priceRisk.toFixed(2)} 元
      </div>
    </div>
  );
}
