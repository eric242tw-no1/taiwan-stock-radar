"use client";
import React, { createContext, useContext, useEffect, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────
export type Theme = "dark" | "light";

export interface StockEntry {
  code: string;   // e.g. "2330"
  name: string;   // e.g. "台積電"
}

interface AppContextValue {
  theme: Theme;
  toggleTheme: () => void;
  stockPool: StockEntry[];
  setStockPool: (pool: StockEntry[]) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (v: boolean) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be inside AppProvider");
  return ctx;
}

// ── Default stock pool ─────────────────────────────────────────────────────
const DEFAULT_POOL: StockEntry[] = [
  { code: "2330", name: "台積電" },
  { code: "2317", name: "鴻海" },
  { code: "2454", name: "聯發科" },
  { code: "2308", name: "台達電" },
  { code: "3711", name: "日月光投控" },
  { code: "2303", name: "聯電" },
  { code: "6505", name: "台塑石化" },
  { code: "2882", name: "國泰金" },
  { code: "1303", name: "南亞" },
  { code: "2412", name: "中華電" },
];

// ── Provider ───────────────────────────────────────────────────────────────
export function AppProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [stockPool, setStockPoolState] = useState<StockEntry[]>(DEFAULT_POOL);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Load persisted values
  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem("app-theme") as Theme | null;
      if (saved === "light" || saved === "dark") setTheme(saved);
      const savedPool = localStorage.getItem("stock-pool");
      if (savedPool) setStockPoolState(JSON.parse(savedPool));
    } catch {}
  }, []);

  // Apply theme to <html>
  useEffect(() => {
    if (!mounted) return;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("app-theme", theme);
  }, [theme, mounted]);

  const toggleTheme = () => setTheme(t => (t === "dark" ? "light" : "dark"));

  const setStockPool = (pool: StockEntry[]) => {
    setStockPoolState(pool);
    try { localStorage.setItem("stock-pool", JSON.stringify(pool)); } catch {}
  };

  return (
    <AppContext.Provider
      value={{ theme, toggleTheme, stockPool, setStockPool, isSettingsOpen, setIsSettingsOpen }}
    >
      {children}
    </AppContext.Provider>
  );
}
