"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

// API calls go through Next.js rewrite proxy → /api/* → fastapi:8000
const API = "";

// ── Types ────────────────────────────────────────────────────────────────────
interface UsIndex { price: number; change_pct: number; level?: string }
interface UsIndicesData { sp500: UsIndex; nasdaq: UsIndex; dji: UsIndex; vix: UsIndex }

interface TwIndex {
  price: number; change: number; change_pct: number;
  trade_value_bn: number; update_time: string;
}
interface TwMarketData { taiex: TwIndex; otc: TwIndex }

interface FuturesData { price: number; change_pct: number; name: string }
interface FxData { price: number; change_pct: number }
interface FuturesFxData { futures: FuturesData; fx: FxData }

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtPrice(p: number, key: string) {
  if (key === "vix") return p.toFixed(2);
  return p.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function fmtPct(p: number) { return (p >= 0 ? "+" : "") + p.toFixed(2) + "%" }

// ── Hooks ────────────────────────────────────────────────────────────────────
function useApi<T>(path: string, interval = 30_000) {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}${path}`);
        if (res.ok) setData(await res.json());
      } catch {}
    };
    load();
    const id = setInterval(load, interval);
    return () => clearInterval(id);
  }, [path, interval]);
  return data;
}

// ── Component ────────────────────────────────────────────────────────────────
export default function Topbar() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const usData = useApi<UsIndicesData>("/api/market/us-indices", 30_000);
  const twData = useApi<TwMarketData>("/api/market/tw", 10_000);
  const fxData = useApi<FuturesFxData>("/api/market/futures-fx", 60_000);

  type IndexItem = {
    label: string; value: string; chg: string; up: boolean; vixLevel?: string;
  };

  const twIndices: IndexItem[] = twData
    ? [
        {
          label: "加權",
          value: twData.taiex.price.toLocaleString("en-US", { maximumFractionDigits: 2 }),
          chg: fmtPct(twData.taiex.change_pct),
          up: twData.taiex.change_pct >= 0,
        },
        {
          label: "OTC",
          value: twData.otc.price.toFixed(2),
          chg: fmtPct(twData.otc.change_pct),
          up: twData.otc.change_pct >= 0,
        },
      ]
    : [
        { label: "加權", value: "---", chg: "---", up: true },
        { label: "OTC",  value: "---", chg: "---", up: true },
      ];

  const midIndices: IndexItem[] = [
    {
      label: "大台期",
      value: fxData ? fxData.futures.price.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "---",
      chg:   fxData ? fmtPct(fxData.futures.change_pct) : "---",
      up:    (fxData?.futures.change_pct ?? 0) >= 0,
    },
    {
      label: "USD/TWD",
      value: fxData ? fxData.fx.price.toFixed(3) : "---",
      chg:   fxData ? fmtPct(fxData.fx.change_pct) : "---",
      up:    (fxData?.fx.change_pct ?? 0) >= 0,
    },
  ];

  const usIndices: IndexItem[] = usData
    ? [
        { label: "S&P500", value: fmtPrice(usData.sp500.price, "sp500"),  chg: fmtPct(usData.sp500.change_pct),  up: usData.sp500.change_pct  >= 0 },
        { label: "Nasdaq", value: fmtPrice(usData.nasdaq.price, "nasdaq"), chg: fmtPct(usData.nasdaq.change_pct), up: usData.nasdaq.change_pct >= 0 },
        { label: "道瓊",   value: fmtPrice(usData.dji.price, "dji"),       chg: fmtPct(usData.dji.change_pct),    up: usData.dji.change_pct    >= 0 },
        { label: "VIX",    value: fmtPrice(usData.vix.price, "vix"),       chg: fmtPct(usData.vix.change_pct),    up: usData.vix.change_pct    >= 0, vixLevel: usData.vix.level },
      ]
    : [
        { label: "S&P500", value: "---", chg: "---", up: true },
        { label: "Nasdaq", value: "---", chg: "---", up: true },
        { label: "道瓊",   value: "---", chg: "---", up: true },
        { label: "VIX",    value: "---", chg: "---", up: false, vixLevel: "low" },
      ];

  const allIndices: IndexItem[] = [...twIndices, ...midIndices, ...usIndices];

  return (
    <header style={{
      height: 50, background: "var(--c-sidebar-bg)", borderBottom: "1px solid #2a2a3a",
      display: "flex", alignItems: "center", padding: "0 16px",
      gap: 0, flexShrink: 0,
    }}>
      <div style={{ display: "flex", gap: 0, flex: 1, overflowX: "auto" }}>
        {allIndices.map((idx) => (
          <div key={idx.label} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "0 14px", borderRight: "1px solid #2a2a3a",
            whiteSpace: "nowrap",
          }}>
            <span style={{ fontSize: 16, color: "var(--c-text-dim)" }}>{idx.label}</span>
            <span style={{ fontSize: 17, fontWeight: 600, color: "var(--c-text)" }}>{idx.value}</span>
            <span style={{
              fontSize: 16,
              color: idx.vixLevel === "low" ? "#00c076"
                   : idx.vixLevel === "high" ? "#ff4d4d"
                   : idx.up ? "#00c076" : "#ff4d4d",
            }}>
              {idx.chg}
              {idx.vixLevel && (
                <span style={{
                  marginLeft: 4, fontSize: 17, padding: "1px 4px", borderRadius: 3,
                  background: idx.vixLevel === "low" ? "#003d20"
                             : idx.vixLevel === "high" ? "#3d0000" : "#3d2a00",
                  color: idx.vixLevel === "low" ? "#00c076"
                        : idx.vixLevel === "high" ? "#ff4d4d" : "#f5a623",
                }}>
                  {idx.vixLevel === "low" ? "低恐慌" : idx.vixLevel === "high" ? "高恐慌" : "中性"}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>

      <input
        className="topbar-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && query.trim()) {
            router.push(`/stock?s=${query.trim()}`);
          }
        }}
        placeholder="輸入代號或名稱..."
        style={{
          background: "var(--c-bg-deep)", border: "1px solid #2a2a3a", borderRadius: 6,
          color: "var(--c-text)", fontSize: 16, padding: "4px 10px", width: 160,
          outline: "none",
        }}
      />
    </header>
  );
}
