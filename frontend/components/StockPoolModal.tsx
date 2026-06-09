"use client";
import { useState } from "react";
import { useAppContext, StockEntry } from "@/contexts/AppContext";

export default function StockPoolModal() {
  const { isSettingsOpen, setIsSettingsOpen, stockPool, setStockPool } = useAppContext();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  if (!isSettingsOpen) return null;

  function addStock() {
    const c = code.trim();
    const n = name.trim() || c;
    if (!c) { setError("請輸入股票代碼"); return; }
    if (!/^\d{4,6}$/.test(c)) { setError("代碼格式：4-6位數字"); return; }
    if (stockPool.find(s => s.code === c)) { setError("已在股票池中"); return; }
    setStockPool([...stockPool, { code: c, name: n }]);
    setCode(""); setName(""); setError("");
  }

  function removeStock(code: string) {
    setStockPool(stockPool.filter(s => s.code !== code));
  }

  function resetDefault() {
    const DEFAULT: StockEntry[] = [
      { code: "2330", name: "台積電" }, { code: "2317", name: "鴻海" },
      { code: "2454", name: "聯發科" }, { code: "2308", name: "台達電" },
      { code: "3711", name: "日月光投控" }, { code: "2303", name: "聯電" },
      { code: "6505", name: "台塑石化" }, { code: "2882", name: "國泰金" },
      { code: "1303", name: "南亞" }, { code: "2412", name: "中華電" },
    ];
    setStockPool(DEFAULT);
  }

  return (
    <div
      onClick={() => setIsSettingsOpen(false)}
      style={{
        position: "fixed", inset: 0, background: "#00000088",
        zIndex: 2000, display: "flex", alignItems: "center", justifyContent: "center",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--c-bg-modal)", border: "1px solid var(--c-border)",
          borderRadius: 14, padding: "24px 28px", width: "min(480px, 92vw)",
          maxHeight: "80vh", display: "flex", flexDirection: "column",
          boxShadow: "0 16px 60px #0008",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--c-text)" }}>⚙️ 股票池設定</div>
            <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 3 }}>
              設定追蹤的個股，用於波段領頭羊與漲幅排行
            </div>
          </div>
          <button
            onClick={() => setIsSettingsOpen(false)}
            style={{
              background: "transparent", border: "none", color: "var(--c-text-dim)",
              fontSize: 20, cursor: "pointer", lineHeight: 1,
            }}
          >✕</button>
        </div>

        {/* Add form */}
        <div style={{
          display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap",
        }}>
          <input
            value={code}
            onChange={e => { setCode(e.target.value); setError(""); }}
            onKeyDown={e => e.key === "Enter" && addStock()}
            placeholder="股票代碼（如 2330）"
            style={{
              flex: "1 1 120px", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
              borderRadius: 6, padding: "8px 12px", color: "var(--c-text)", fontSize: 14,
              outline: "none", fontFamily: "'JetBrains Mono', monospace",
            }}
          />
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addStock()}
            placeholder="名稱（選填）"
            style={{
              flex: "1 1 100px", background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
              borderRadius: 6, padding: "8px 12px", color: "var(--c-text)", fontSize: 14,
              outline: "none",
            }}
          />
          <button
            onClick={addStock}
            style={{
              background: "#00c076", border: "none", borderRadius: 6, padding: "8px 16px",
              color: "#000", fontSize: 14, fontWeight: 700, cursor: "pointer",
              flexShrink: 0,
            }}
          >＋ 新增</button>
        </div>

        {error && (
          <div style={{ fontSize: 13, color: "#ff4d4d", marginBottom: 10 }}>{error}</div>
        )}

        {/* List */}
        <div style={{
          overflowY: "auto", flex: 1, borderTop: "1px solid var(--c-border)",
          paddingTop: 12, display: "flex", flexDirection: "column", gap: 6,
        }}>
          {stockPool.length === 0 && (
            <div style={{ color: "var(--c-text-dim)", fontSize: 14, textAlign: "center", padding: "24px 0" }}>
              尚未設定任何股票，請新增
            </div>
          )}
          {stockPool.map(s => (
            <div key={s.code} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
              borderRadius: 8, padding: "8px 12px",
            }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 15,
                  color: "#00c076", fontWeight: 700,
                }}>{s.code}</span>
                <span style={{ fontSize: 14, color: "var(--c-text)" }}>{s.name}</span>
              </div>
              <button
                onClick={() => removeStock(s.code)}
                style={{
                  background: "transparent", border: "1px solid #ff4d4d44",
                  borderRadius: 4, color: "#ff4d4d", fontSize: 13, cursor: "pointer",
                  padding: "2px 10px",
                }}
              >移除</button>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          borderTop: "1px solid var(--c-border)", paddingTop: 14, marginTop: 12,
        }}>
          <span style={{ fontSize: 13, color: "var(--c-text-dim)" }}>共 {stockPool.length} 支股票</span>
          <button
            onClick={resetDefault}
            style={{
              background: "transparent", border: "1px solid var(--c-border)",
              borderRadius: 6, padding: "6px 14px", color: "var(--c-text-dim)",
              fontSize: 13, cursor: "pointer",
            }}
          >重設預設</button>
        </div>
      </div>
    </div>
  );
}
