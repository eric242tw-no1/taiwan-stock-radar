const BASE = "";  // next.config.ts rewrite 已將 /api/* → localhost:8000

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message ?? err?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Market ──────────────────────────────────────────────
export const api = {
  // 市場總覽
  marketOverview:  () => req("/api/market/overview"),
  marketUS:        () => req("/api/market/us"),

  // 個股分析
  getAnalysis:     (symbol: string) => req(`/api/analysis/${symbol}`),
  refreshAnalysis: (symbol: string) => req(`/api/analysis/${symbol}/refresh`, { method: "POST" }),
  getCooldown:     (symbol: string) => req<{ remaining_seconds: number; can_refresh: boolean }>(`/api/analysis/${symbol}/cooldown`),

  // 選股
  screener: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") q.set(k, String(v));
    }
    return req(`/api/screener?${q}`);
  },

  // 持倉
  getPortfolio:   () => req("/api/portfolio"),
  addHolding:     (body: object) => req("/api/portfolio", { method: "POST", body: JSON.stringify(body) }),
  deleteHolding:  (symbol: string) => req(`/api/portfolio/${symbol}`, { method: "DELETE" }),
  importImage:    (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/portfolio/import-image", { method: "POST", body: fd }).then(r => r.json());
  },

  // 回測
  backtestStrategies: () => req("/api/backtest/strategies"),
  runBacktest:        (body: object) => req("/api/backtest", { method: "POST", body: JSON.stringify(body) }),

  // 股票池
  getStockPool:    () => req("/api/stock-pool"),
  addStockToPool:  (symbol: string, name?: string) => req("/api/stock-pool", { method: "POST", body: JSON.stringify({ symbol, name: name ?? "" }) }),
  removeFromPool:  (symbol: string) => req(`/api/stock-pool/${symbol}`, { method: "DELETE" }),

  // 警報
  getAlerts:   () => req("/api/alerts"),
  addAlert:    (body: object) => req("/api/alerts", { method: "POST", body: JSON.stringify(body) }),
  deleteAlert: (id: number) => req(`/api/alerts/${id}`, { method: "DELETE" }),
  testAlert:   (text: string) => req("/api/alerts/test", { method: "POST", body: JSON.stringify({ text }) }),
};
