"use client";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const COLORS = ["#00c076", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

interface Strategy {
  id: number; symbol: string; period_start: string; period_end: string;
  win_rate: number; total_return: number; max_drawdown: number;
  sharpe_ratio: number; trade_count: number; equity_curve: number[];
  created_at: string;
}

function MetricBadge({ label, value, color = "var(--c-text)" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "var(--c-text-dim)" }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function StrategyCard({ strategy, selected, onToggle, colorIdx }: {
  strategy: Strategy; selected: boolean; onToggle: () => void; colorIdx: number;
}) {
  const color = COLORS[colorIdx % COLORS.length];
  return (
    <div onClick={onToggle} style={{
      background: "var(--c-bg-deep)", border: `1px solid ${selected ? color : "var(--c-border)"}`,
      borderRadius: 10, padding: "14px 16px", cursor: "pointer",
      transition: "border-color 0.2s", marginBottom: 12,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: selected ? color : "var(--c-border)" }} />
          <span style={{ fontWeight: 600, color: "var(--c-text)" }}>{strategy.symbol}</span>
          <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>{strategy.period_start} ~ {strategy.period_end}</span>
        </div>
        <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>{strategy.trade_count} 筆</span>
      </div>
      <div style={{ display: "flex", gap: 16, justifyContent: "space-around" }}>
        <MetricBadge label="總報酬" value={`${strategy.total_return > 0 ? "+" : ""}${(strategy.total_return * 100).toFixed(1)}%`}
          color={strategy.total_return >= 0 ? "#00c076" : "#ef4444"} />
        <MetricBadge label="最大回撤" value={`${(strategy.max_drawdown * 100).toFixed(1)}%`} color="#ef4444" />
        <MetricBadge label="勝率" value={`${(strategy.win_rate * 100).toFixed(1)}%`} />
        <MetricBadge label="Sharpe" value={strategy.sharpe_ratio.toFixed(2)}
          color={strategy.sharpe_ratio >= 1 ? "#00c076" : strategy.sharpe_ratio >= 0 ? "var(--c-text)" : "#ef4444"} />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [symbolFilter, setSymbolFilter] = useState("");

  useEffect(() => {
    const load = async () => {
      const url = symbolFilter ? `${API}/api/analytics/strategies?symbol=${symbolFilter}` : `${API}/api/analytics/strategies`;
      try {
        const res = await fetch(url);
        const data = await res.json();
        setStrategies(data.strategies ?? []);
      } catch {}
      setLoading(false);
    };
    load();
  }, [symbolFilter]);

  const toggle = (id: number) => setSelected(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const chartData = (() => {
    const visible = strategies.filter(s => selected.has(s.id));
    if (visible.length === 0) return [];
    const maxLen = Math.max(...visible.map(s => s.equity_curve.length));
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { index: i + 1 };
      visible.forEach(s => {
        if (i < s.equity_curve.length) pt[`${s.symbol}#${s.id}`] = s.equity_curve[i];
      });
      return pt;
    });
  })();

  const visibleStrategies = strategies.filter(s => selected.has(s.id));

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--c-text)" }}>📉 策略分析</h1>
        <input placeholder="篩選股票代號" value={symbolFilter} onChange={e => setSymbolFilter(e.target.value)}
          style={{
            padding: "8px 12px", borderRadius: 8, background: "var(--c-bg-deep)",
            border: "1px solid var(--c-border)", color: "var(--c-text)", fontSize: 14, width: 180,
          }} />
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--c-text-dim)" }}>載入中...</div>
      ) : strategies.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--c-text-dim)" }}>尚無回測結果。先至「回測」頁面執行回測。</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 20 }}>
          {/* Strategy list */}
          <div style={{ overflowY: "auto", maxHeight: "70vh" }}>
            <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginBottom: 10 }}>
              點擊策略加入比較（共 {strategies.length} 筆）
            </div>
            {strategies.map((s, i) => (
              <StrategyCard key={s.id} strategy={s} selected={selected.has(s.id)}
                onToggle={() => toggle(s.id)} colorIdx={i} />
            ))}
          </div>

          {/* Chart */}
          <div>
            {visibleStrategies.length === 0 ? (
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                height: 400, background: "var(--c-bg-deep)", borderRadius: 10,
                border: "1px solid var(--c-border)", color: "var(--c-text-dim)",
              }}>
                點擊左側策略顯示權益曲線
              </div>
            ) : (
              <div style={{ background: "var(--c-bg-deep)", borderRadius: 10, border: "1px solid var(--c-border)", padding: "16px 8px 8px" }}>
                <div style={{ fontSize: 14, color: "var(--c-text-dim)", marginBottom: 8, paddingLeft: 12 }}>權益曲線比較</div>
                <ResponsiveContainer width="100%" height={380}>
                  <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 4, left: 0 }}>
                    <XAxis dataKey="index" tick={{ fontSize: 11, fill: "var(--c-text-dim)" }} label={{ value: "交易次數", position: "insideBottom", offset: -2, fill: "var(--c-text-dim)", fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--c-text-dim)" }} tickFormatter={v => v.toFixed(2)} />
                    <Tooltip contentStyle={{ background: "var(--c-bg-deep)", border: "1px solid var(--c-border)" }}
                      formatter={(v: any) => [`${((v - 1) * 100).toFixed(2)}%`, ""]} />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                    {visibleStrategies.map((s, i) => (
                      <Line key={s.id} type="monotone" dataKey={`${s.symbol}#${s.id}`}
                        name={`${s.symbol} (${s.period_start})`}
                        stroke={COLORS[strategies.indexOf(s) % COLORS.length]}
                        dot={false} strokeWidth={2} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
