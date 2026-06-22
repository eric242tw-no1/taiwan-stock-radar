"use client";
import { useEffect, useState } from "react";

const API = "";

interface StrategyVersion {
  id: number;
  name: string;
  prompt_template: string;
  is_active: boolean;
  created_at: string;
}

export default function StrategyPage() {
  const [versions, setVersions] = useState<StrategyVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [formName, setFormName] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formNameErr, setFormNameErr] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitErr, setSubmitErr] = useState("");

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/strategies/versions`);
      if (!r.ok) throw new Error();
      const d = await r.json();
      setVersions(d.versions ?? d ?? []);
    } catch { setError("載入失敗"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchVersions(); }, []);

  const handleSubmit = async () => {
    if (!formName.trim()) { setFormNameErr("版本名稱不能為空"); return; }
    setFormNameErr(""); setSubmitErr(""); setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/strategies/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: formName.trim(), prompt_template: formPrompt }),
      });
      if (!r.ok) throw new Error();
      setFormName(""); setFormPrompt("");
      await fetchVersions();
    } catch { setSubmitErr("儲存失敗，請重試"); }
    finally { setSubmitting(false); }
  };

  return (
    <div style={{ padding: "20px 24px", maxWidth: 800 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>📋 策略版本管理</h1>
      <p style={{ fontSize: 13, color: "var(--c-text-dim)", marginBottom: 24 }}>
        管理 AI 分析使用的 prompt 版本，active 版本會套用於所有 AI 分析。
      </p>

      {/* 新增版本表單 */}
      <div style={{ background: "var(--c-bg-card)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>新增策略版本</div>

        <div style={{ marginBottom: 10 }}>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>版本名稱 *</label>
          <input
            value={formName}
            onChange={e => { setFormName(e.target.value); setFormNameErr(""); }}
            placeholder="e.g. v2-conservative"
            style={{
              width: "100%", padding: "7px 10px", fontSize: 13,
              background: "var(--c-bg-deep)", border: `1px solid ${formNameErr ? "#ff4d4d" : "var(--c-border)"}`,
              borderRadius: 5, color: "var(--c-text)", outline: "none", boxSizing: "border-box",
            }}
          />
          {formNameErr && <div style={{ fontSize: 11, color: "#ff4d4d", marginTop: 3 }}>{formNameErr}</div>}
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, color: "var(--c-text-dim)", display: "block", marginBottom: 4 }}>Prompt Template</label>
          <textarea
            value={formPrompt}
            onChange={e => setFormPrompt(e.target.value)}
            placeholder="輸入 prompt template 內容（可留空使用預設）"
            rows={5}
            style={{
              width: "100%", padding: "7px 10px", fontSize: 12,
              background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
              borderRadius: 5, color: "var(--c-text)", outline: "none",
              resize: "vertical", fontFamily: "monospace", boxSizing: "border-box",
            }}
          />
        </div>

        {submitErr && <div style={{ fontSize: 12, color: "#ff4d4d", marginBottom: 8 }}>{submitErr}</div>}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          style={{
            padding: "8px 20px", fontSize: 13, fontWeight: 600,
            background: submitting ? "var(--c-border)" : "#3d7eff",
            border: "none", borderRadius: 5, color: "#fff",
            cursor: submitting ? "not-allowed" : "pointer",
          }}
        >
          {submitting ? "儲存中..." : "新增版本"}
        </button>
      </div>

      {/* 版本列表 */}
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>現有版本</div>

      {loading && <div style={{ fontSize: 13, color: "var(--c-text-dim)" }}>載入中...</div>}
      {error && <div style={{ fontSize: 13, color: "#ff4d4d" }}>{error}</div>}
      {!loading && !error && versions.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--c-text-dim)", padding: "20px 0", textAlign: "center" }}>
          尚無策略版本，請新增第一個版本
        </div>
      )}

      {versions.map(v => (
        <div key={v.id} style={{
          background: "var(--c-bg-card)", border: `1px solid ${v.is_active ? "#3d7eff66" : "var(--c-border)"}`,
          borderRadius: 8, padding: "12px 16px", marginBottom: 10,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 700 }}>{v.name}</span>
              {v.is_active && (
                <span style={{ fontSize: 11, padding: "1px 7px", borderRadius: 3, background: "#3d7eff22", color: "#3d7eff", border: "1px solid #3d7eff44" }}>
                  Active
                </span>
              )}
            </div>
            <span style={{ fontSize: 11, color: "var(--c-text-dim)" }}>
              {new Date(v.created_at).toLocaleString("zh-TW")}
            </span>
          </div>
          {v.prompt_template && (
            <pre style={{ fontSize: 11, color: "var(--c-text-dim)", background: "var(--c-bg-deep)", padding: "6px 10px", borderRadius: 4, overflow: "auto", maxHeight: 80, margin: 0, whiteSpace: "pre-wrap" }}>
              {v.prompt_template.slice(0, 300)}{v.prompt_template.length > 300 ? "..." : ""}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
