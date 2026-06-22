"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

const API = "";

interface BySymbol {
  total: number;
  correct: number;
  accuracy: number;
}

interface RecentRow {
  symbol: string;
  direction: string;
  is_correct: number | null;
  confidence: number;
  predicted_at: string;
}

interface Report {
  days: number;
  total: number;
  correct: number;
  accuracy: number | null;
  by_symbol: Record<string, BySymbol>;
  recent: RecentRow[];
}

const DIRECTION_LABEL: Record<string, string> = { up: "看多", down: "看空", neutral: "中性" };
const DIRECTION_COLOR: Record<string, string> = { up: "#ff4d4d", down: "#00c076", neutral: "var(--c-text-dim)" };

export default function AuditPage() {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`${API}/api/audit/accuracy?days=${days}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setReport)
      .catch(() => setError("無法取得審計資料"))
      .finally(() => setLoading(false));
  }, [days]);

  // 將 recent 資料轉換為折線圖格式（按日期聚合準確率）
  const chartData = (() => {
    if (!report?.recent?.length) return [];
    const byDate: Record<string, { total: number; correct: number }> = {};
    for (const r of report.recent) {
      const date = r.predicted_at.slice(0, 10);
      if (!byDate[date]) byDate[date] = { total: 0, correct: 0 };
      byDate[date].total += 1;
      if (r.is_correct === 1) byDate[date].correct += 1;
    }
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, { total, correct }]) => ({
        date,
        accuracy: total > 0 ? Math.round(correct / total * 100) : 0,
      }));
  })();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>🎯 AI 自審計</div>
          <div style={{ fontSize: 12, color: "var(--c-text-dim)", marginTop: 2 }}>
            追蹤 AI 預測準確率，評估模型表現
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setDays(d)} style={{
              padding: "5px 14px", borderRadius: 6, cursor: "pointer", fontSize: 13,
              background: days === d ? "var(--c-bg-deep)" : "transparent",
              border: `1px solid ${days === d ? "#00c076" : "var(--c-border)"}`,
              color: days === d ? "#00c076" : "var(--c-text-dim)",
            }}>近 {d} 天</button>
          ))}
        </div>
      </div>

      {loading && <div style={{ color: "var(--c-text-dim)", fontSize: 14 }}>載入中...</div>}
      {error && <div style={{ color: "#ff4d4d", fontSize: 14 }}>{error}</div>}

      {report && (
        <>
          {/* 總覽 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              { label: "總預測數", value: report.total, color: "var(--c-text)" },
              { label: "命中數", value: report.correct, color: "#00c076" },
              { label: "準確率", value: report.accuracy != null ? `${report.accuracy}%` : "—", color: report.accuracy != null && report.accuracy >= 60 ? "#00c076" : "#f5a623" },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                background: "var(--c-bg-card)", border: "1px solid var(--c-border)",
                borderRadius: 8, padding: "14px 16px", textAlign: "center",
              }}>
                <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
              </div>
            ))}
          </div>

          {/* 準確率折線圖 */}
          {chartData.length > 0 && (
            <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--c-text-dim)", marginBottom: 12 }}>每日準確率趨勢</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="var(--c-border)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--c-text-dim)" }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "var(--c-text-dim)" }} unit="%" />
                  <Tooltip
                    contentStyle={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 6 }}
                    labelStyle={{ color: "var(--c-text-dim)", fontSize: 11 }}
                    itemStyle={{ color: "#00c076" }}
                    formatter={(v: number) => [`${v}%`, "準確率"]}
                  />
                  <Line type="monotone" dataKey="accuracy" stroke="#00c076" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 個股準確率表格 */}
          {Object.keys(report.by_symbol).length > 0 && (
            <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--c-text-dim)", marginBottom: 10 }}>個股準確率</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto auto", gap: "6px 16px", alignItems: "center" }}>
                {["個股", "預測", "命中", "準確率"].map(h => (
                  <div key={h} style={{ fontSize: 10, color: "var(--c-text-dim)", fontWeight: 600 }}>{h}</div>
                ))}
                {Object.entries(report.by_symbol)
                  .sort(([, a], [, b]) => b.accuracy - a.accuracy)
                  .map(([sym, s]) => (
                    <>
                      <div key={`${sym}-s`} style={{ fontSize: 13, color: "#3d7eff", fontWeight: 700 }}>{sym}</div>
                      <div key={`${sym}-t`} style={{ fontSize: 13, color: "var(--c-text-dim)", textAlign: "right" }}>{s.total}</div>
                      <div key={`${sym}-c`} style={{ fontSize: 13, color: "#00c076", textAlign: "right" }}>{s.correct}</div>
                      <div key={`${sym}-a`} style={{ fontSize: 13, fontWeight: 700, textAlign: "right", color: s.accuracy >= 60 ? "#00c076" : s.accuracy >= 40 ? "#f5a623" : "#ff4d4d" }}>
                        {s.accuracy}%
                      </div>
                    </>
                  ))}
              </div>
            </div>
          )}

          {/* 最近 20 筆預測紀錄 */}
          {report.recent.length > 0 && (
            <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--c-text-dim)", marginBottom: 10 }}>最近預測紀錄</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {report.recent.map((r, i) => (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "7px 10px", background: "var(--c-bg-deep)", borderRadius: 6,
                    borderLeft: `3px solid ${r.is_correct === 1 ? "#00c076" : r.is_correct === 0 ? "#ff4d4d" : "var(--c-border)"}`,
                  }}>
                    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: "#3d7eff", width: 40 }}>{r.symbol}</span>
                      <span style={{ fontSize: 12, color: DIRECTION_COLOR[r.direction] ?? "var(--c-text)" }}>
                        {DIRECTION_LABEL[r.direction] ?? r.direction}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>信心 {Math.round(r.confidence * 100)}%</span>
                    </div>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>{r.predicted_at.slice(0, 10)}</span>
                      <span style={{
                        fontSize: 11, padding: "1px 6px", borderRadius: 4, fontWeight: 700,
                        background: r.is_correct === 1 ? "#00c07622" : r.is_correct === 0 ? "#ff4d4d22" : "var(--c-border)",
                        color: r.is_correct === 1 ? "#00c076" : r.is_correct === 0 ? "#ff4d4d" : "var(--c-text-dim)",
                      }}>
                        {r.is_correct === 1 ? "✓ 命中" : r.is_correct === 0 ? "✗ 未中" : "待審計"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.total === 0 && (
            <div style={{
              background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8,
              padding: "40px 16px", textAlign: "center", color: "var(--c-text-dim)", fontSize: 14,
            }}>
              近 {days} 天尚無審計資料。使用 AI 分析功能後，預測紀錄將自動累積。
            </div>
          )}
        </>
      )}
    </div>
  );
}
