"use client";
import { useState } from "react";
import { TradingViewModal } from "@/components/TradingViewModal";

export type UsStock = {
  label: string;
  full_name?: string;
  symbol?: string;
  chg: number;
  price?: number;
  is_crypto?: boolean;
};

export function UsStockModal({ stock, onClose }: { stock: UsStock; onClose: () => void }) {
  const up = stock.chg >= 0;
  const color = up ? "#00c076" : "#ff4d4d";
  const tvSym = stock.is_crypto
    ? `BINANCE:${(stock.symbol ?? stock.label).replace("USD", "")}USD`
    : (stock.symbol ?? stock.label);
  const [showTv, setShowTv] = useState(false);
  if (showTv) {
    return <TradingViewModal symbol={tvSym} title={stock.label} onClose={() => setShowTv(false)} />;
  }
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "#00000099", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={e => e.stopPropagation()} style={{ background: "var(--c-bg-modal)", border: "1px solid #3a3a5a", borderRadius: 14, padding: "24px 28px", minWidth: 280, boxShadow: "0 8px 40px #000c" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "var(--c-text)" }}>{stock.label}</div>
            {stock.full_name && <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 2 }}>{stock.full_name}</div>}
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--c-text-dim)", fontSize: 18, cursor: "pointer", padding: "0 4px" }}>✕</button>
        </div>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 30, fontWeight: 700, color: "var(--c-text)" }}>
            {stock.is_crypto
              ? `$${Number(stock.price).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
              : `$${stock.price?.toLocaleString("en-US", { maximumFractionDigits: 2 }) ?? "--"}`}
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color, marginTop: 4 }}>
            {up ? "▲ +" : "▼ "}{Math.abs(stock.chg).toFixed(2)}%
            <span style={{ fontSize: 13, color: "var(--c-text-dim)", marginLeft: 8 }}>較前日收盤</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, padding: "3px 10px", borderRadius: 20, background: stock.is_crypto ? "#2a1a3a" : "#1a2a3a", color: stock.is_crypto ? "#cc44ff" : "#3d7eff", border: `1px solid ${stock.is_crypto ? "#cc44ff44" : "#3d7eff44"}` }}>
            {stock.is_crypto ? "🪙 加密貨幣" : "🇺🇸 美股"}
          </span>
          <span style={{ fontSize: 12, padding: "3px 10px", borderRadius: 20, background: up ? "#003d20" : "#3d0000", color, border: `1px solid ${color}44` }}>
            {up ? "上漲" : "下跌"}
          </span>
        </div>
        <button onClick={() => setShowTv(true)}
          style={{ display: "block", width: "100%", textAlign: "center", padding: "10px 0", background: "var(--c-bg-deep)", border: "1px solid #3d7eff44", borderRadius: 8, color: "#3d7eff", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          onMouseEnter={e => (e.currentTarget.style.background = "#222240")}
          onMouseLeave={e => (e.currentTarget.style.background = "var(--c-bg-deep)")}
        >
          📈 查看 TradingView 圖表 →
        </button>
      </div>
    </div>
  );
}

export function UsHeatCell({
  label, chg, price, full_name, symbol, is_crypto, onClick,
}: UsStock & { onClick: () => void }) {
  const color = chg > 2 ? "#00c076" : chg > 0 ? "#009955" : chg > -2 ? "#cc3333" : "#ff4d4d";
  const bg    = chg > 2 ? "#003d20" : chg > 0 ? "#002210" : chg > -2 ? "#2a0a0a" : "#3d0000";
  return (
    <div
      onClick={onClick}
      style={{ background: bg, border: `1px solid ${color}55`, borderRadius: 6, padding: "8px 6px", textAlign: "center", cursor: "pointer", transition: "all 0.15s" }}
      onMouseEnter={e => { e.currentTarget.style.filter = "brightness(1.35)"; e.currentTarget.style.boxShadow = `0 0 10px ${color}55`; }}
      onMouseLeave={e => { e.currentTarget.style.filter = "brightness(1)"; e.currentTarget.style.boxShadow = "none"; }}
      title={full_name}
    >
      <div style={{ fontSize: 14, color: "var(--c-text-mid)", marginBottom: 1 }}>
        {is_crypto ? "₿ " : ""}{label}
      </div>
      {price !== undefined && (
        <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginBottom: 1, fontFamily: "'JetBrains Mono', monospace" }}>
          {is_crypto ? `$${Number(price).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : `$${price}`}
        </div>
      )}
      <div style={{ fontSize: 15, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {chg > 0 ? "+" : ""}{chg.toFixed(2)}%
      </div>
    </div>
  );
}
