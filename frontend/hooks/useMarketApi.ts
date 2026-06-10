"use client";
import { useEffect, useState } from "react";

// API calls go through Next.js rewrite proxy → /api/* → fastapi:8000
export const API = "";

// ── Interfaces ─────────────────────────────────────────────────────────
export interface UsIndex { price: number; change_pct: number; level?: string }
export interface UsIndicesData { sp500: UsIndex; nasdaq: UsIndex; dji: UsIndex; vix: UsIndex }

export interface TwIndex {
  price: number; change: number; change_pct: number;
  trade_value_bn: number; update_time: string;
}
export interface TwBreadth { up: number; down: number; flat: number; source: string }
export interface TwMarketData { taiex: TwIndex; otc: TwIndex; breadth: TwBreadth }

export interface ChipTotals { foreign: number; trust: number; dealer: number }
export interface ChipData { totals: ChipTotals }

// ── Formatters ─────────────────────────────────────────────────────────
export function fmtPrice(p: number, key: string) {
  if (key === "vix") return p.toFixed(2);
  return p.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
export function fmtPct(p: number) { return (p >= 0 ? "+" : "") + p.toFixed(2) + "%"; }
export function fmtShares(n: number): string {
  const lots = Math.round(n / 1000);
  const sign = lots >= 0 ? "+" : "";
  return `${sign}${lots.toLocaleString()}張`;
}

// ── Generic polling hook ───────────────────────────────────────────────
export function useApi<T>(path: string, interval: number) {
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

// ── Named hooks ────────────────────────────────────────────────────────
export function useUsIndices() { return useApi<UsIndicesData>("/api/market/us-indices", 30_000); }
export function useTwMarket()  { return useApi<TwMarketData>("/api/market/tw", 10_000); }
export function useChip()      { return useApi<ChipData>("/api/market/chip", 300_000); }
