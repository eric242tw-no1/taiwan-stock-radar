"use client";
import { useEffect } from "react";

/**
 * 在 app 內嵌 TradingView 進階圖表（iframe widget）。
 * Tauri WebView 無法開外部 target="_blank" 連結，改用內嵌方式，
 * 桌面/瀏覽器皆可用。
 *
 * symbol 範例：
 *   台股   → "TWSE:2330"
 *   美股   → "AAPL" 或 "NASDAQ:AAPL"
 *   加密   → "BINANCE:BTCUSD"
 */
export function TradingViewModal({
  symbol,
  title,
  theme = "dark",
  onClose,
}: {
  symbol: string;
  title?: string;
  theme?: "dark" | "light";
  onClose: () => void;
}) {
  // Esc 關閉
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const src =
    `https://s.tradingview.com/widgetembed/?frameElementId=tv_chart` +
    `&symbol=${encodeURIComponent(symbol)}` +
    `&interval=D&theme=${theme}&style=1&locale=zh_TW` +
    `&hide_side_toolbar=0&allow_symbol_change=1&withdateranges=1`;

  const tvFullUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "#000000cc", zIndex: 2000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "var(--c-bg-card)", border: "1px solid #3a3a5a", borderRadius: 12,
        width: "100%", maxWidth: 1000, height: "82vh", display: "flex", flexDirection: "column",
        overflow: "hidden", boxShadow: "0 8px 40px #000c",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--c-border)" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--c-text)" }}>
            📈 {title ?? symbol} · TradingView
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <a href={tvFullUrl} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: "#3d7eff", textDecoration: "none" }}>在瀏覽器開啟 ↗</a>
            <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--c-text-dim)", fontSize: 20, cursor: "pointer", lineHeight: 1 }}>✕</button>
          </div>
        </div>
        <iframe
          src={src}
          title="TradingView"
          style={{ flex: 1, width: "100%", border: "none" }}
          allow="clipboard-write"
        />
      </div>
    </div>
  );
}

/** 將內部代號轉成 TradingView symbol */
export function toTvSymbol(opts: { code: string; market?: "tw" | "us" | "crypto" }): string {
  const { code, market = "tw" } = opts;
  if (market === "crypto") return `BINANCE:${code.replace("USD", "")}USD`;
  if (market === "us") return code;            // TradingView 可解析裸美股代號
  return `TWSE:${code}`;                        // 台股
}
