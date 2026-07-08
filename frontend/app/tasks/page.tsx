"use client";
import { useEffect, useState } from "react";

const API = "";

interface Job { id: string; trigger: string; next_run: string | null }

// 任務 id → 中文說明（對照 backend/main.py 的排程註冊）
const JOB_LABELS: Record<string, string> = {
  us_indices_refresh:        "美股指數更新",
  tw_market_refresh:         "台股大盤 + 警報檢查",
  futures_fx_refresh:        "期指/匯率更新",
  chip_refresh:              "三大法人籌碼（FinMind）",
  indicator_refresh:         "技術指標 + 日K 計算",
  sectors_refresh:           "產業指數更新",
  gov_funds_refresh:         "八大官股動向",
  self_audit:                "系統自我稽核",
  correlation_refresh:       "台美連動係數",
  tdcc_refresh:              "TDCC 大戶集保",
  stop_loss_polling:         "停損守衛輪詢",
  ai_self_audit:             "AI 評分自審計",
  earnings_calendar_refresh: "財報/除權息日曆",
  notifications_cleanup:     "通知清理",
  morning_brief:             "AI 晨報",
  chip_and_anomaly_open:     "開盤籌碼 + 異常掃描",
  anomaly_intraday:          "盤中異常掃描",
  factor_scan_and_snapshot:  "因子掃描 + AI 批次評分 + 帳戶快照",
};

export default function TasksPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [running, setRunning] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");

  const load = () => {
    fetch(`${API}/api/tasks/jobs`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => {
        setJobs(d.jobs ?? []);
        setRunning(d.running ?? null);
        setError("");
        setUpdatedAt(new Date().toLocaleTimeString("zh-TW", { hour12: false }));
      })
      .catch((e) => setError(`無法取得排程狀態（${e}）— 後端未啟動？`));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ maxWidth: 860, margin: "0 auto", padding: "16px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "var(--c-text)" }}>🌸 任務監控</h1>
          <p style={{ margin: "3px 0 0", fontSize: 12, color: "var(--c-text-dim)" }}>
            APScheduler 排程任務（行程內執行，Celery/Flower 已於 2026-07 移除）
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {running !== null && (
            <span style={{
              fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 12,
              color: running ? "#00c076" : "#ff4d4d",
              background: running ? "#003d2044" : "#3d000044",
              border: `1px solid ${running ? "#00c07644" : "#ff4d4d44"}`,
            }}>
              {running ? "● 排程器運行中" : "● 排程器停止"}
            </span>
          )}
          {updatedAt && <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>更新 {updatedAt}</span>}
        </div>
      </div>

      {error && (
        <div style={{ fontSize: 13, color: "#ff4d4d", background: "var(--c-bg-card)", border: "1px solid #ff4d4d44", borderRadius: 8, padding: "12px 16px", marginBottom: 12 }}>
          ⚠ {error}
        </div>
      )}

      <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 14 }}>
        <div style={{ fontSize: 13, color: "var(--c-text-dim)", fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 10 }}>
          排程任務（{jobs.length}）
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: "var(--c-text-dim)", borderBottom: "1px solid var(--c-border)" }}>
                {["任務", "id", "觸發規則", "下次執行"].map((h) => (
                  <th key={h} style={{ padding: "5px 10px", textAlign: "left", fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} style={{ borderBottom: "1px solid #1a1a2a" }}>
                  <td style={{ padding: "7px 10px", color: "var(--c-text)", fontWeight: 600 }}>
                    {JOB_LABELS[j.id] ?? j.id}
                  </td>
                  <td style={{ padding: "7px 10px", color: "var(--c-text-dim)", fontFamily: "monospace", fontSize: 12 }}>{j.id}</td>
                  <td style={{ padding: "7px 10px", color: "var(--c-text-dim)", fontFamily: "monospace", fontSize: 11 }}>{j.trigger}</td>
                  <td style={{ padding: "7px 10px", color: "#3d7eff", fontWeight: 600 }}>{j.next_run ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginTop: 10 }}>
          每 30 秒自動更新。排程僅在後端行程存活時執行；若某任務長期未跑（如 08:00 日曆），啟動暖身機制會於後端開機時補抓。
        </div>
      </div>
    </div>
  );
}
