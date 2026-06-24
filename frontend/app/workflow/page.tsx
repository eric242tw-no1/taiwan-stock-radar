"use client";
import dynamic from "next/dynamic";
import { useState, useCallback, useRef } from "react";

const ReactFlow = dynamic(() => import("@xyflow/react").then(m => m.ReactFlow), { ssr: false });
const Background = dynamic(() => import("@xyflow/react").then(m => m.Background), { ssr: false });
const Controls = dynamic(() => import("@xyflow/react").then(m => m.Controls), { ssr: false });
const MiniMap = dynamic(() => import("@xyflow/react").then(m => m.MiniMap), { ssr: false });

import "@xyflow/react/dist/style.css";

const NODE_TYPES_CONFIG = [
  { type: "trigger", label: "觸發條件", color: "#00c076" },
  { type: "filter", label: "篩選器", color: "#3b82f6" },
  { type: "signal", label: "訊號輸出", color: "#f59e0b" },
  { type: "action", label: "執行動作", color: "#ef4444" },
  { type: "notify", label: "通知", color: "#8b5cf6" },
];

function NodePalette({ onAdd }: { onAdd: (type: string, label: string) => void }) {
  return (
    <div style={{
      width: 180, background: "var(--c-bg-deep)", borderRight: "1px solid var(--c-border)",
      padding: 12, display: "flex", flexDirection: "column", gap: 8,
    }}>
      <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginBottom: 4 }}>節點類型</div>
      {NODE_TYPES_CONFIG.map(n => (
        <button key={n.type} onClick={() => onAdd(n.type, n.label)}
          style={{
            padding: "8px 12px", borderRadius: 8, border: `1px solid ${n.color}44`,
            background: `${n.color}11`, color: n.color, fontSize: 13,
            cursor: "pointer", textAlign: "left",
          }}>
          + {n.label}
        </button>
      ))}
    </div>
  );
}

let nodeId = 0;
const newNode = (type: string, label: string) => ({
  id: `node_${++nodeId}`,
  type: "default",
  position: { x: 200 + Math.random() * 200, y: 100 + Math.random() * 200 },
  data: { label: `${label}\n(雙擊編輯)` },
  style: {
    background: NODE_TYPES_CONFIG.find(n => n.type === type)?.color + "22",
    border: `1px solid ${NODE_TYPES_CONFIG.find(n => n.type === type)?.color ?? "#555"}`,
    borderRadius: 8, color: "var(--c-text)", fontSize: 13, padding: "8px 12px",
  },
});

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function WorkflowPage() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [name, setName] = useState("新工作流程");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const addNode = useCallback((type: string, label: string) => {
    setNodes(prev => [...prev, newNode(type, label)]);
  }, []);

  const onNodesChange = useCallback((changes: any[]) => {
    setNodes(prev => {
      let next = [...prev];
      changes.forEach(c => {
        if (c.type === "position" && c.dragging) {
          const idx = next.findIndex(n => n.id === c.id);
          if (idx !== -1) next[idx] = { ...next[idx], position: c.position };
        } else if (c.type === "remove") {
          next = next.filter(n => n.id !== c.id);
        }
      });
      return next;
    });
  }, []);

  const onEdgesChange = useCallback((changes: any[]) => {
    setEdges(prev => {
      let next = [...prev];
      changes.forEach(c => {
        if (c.type === "remove") next = next.filter(e => e.id !== c.id);
      });
      return next;
    });
  }, []);

  const onConnect = useCallback((params: any) => {
    setEdges(prev => [...prev, { ...params, id: `e_${Date.now()}` }]);
  }, []);

  const onNodeDoubleClick = useCallback((_: React.MouseEvent, node: any) => {
    const newLabel = window.prompt("編輯節點名稱", node.data.label);
    if (newLabel === null) return;
    setNodes(prev => prev.map(n => n.id === node.id ? { ...n, data: { ...n.data, label: newLabel } } : n));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/workflow/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, nodes, edges }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMsg(`✅ 已儲存（ID: ${data.id}）`);
    } catch (e: any) {
      setMsg(`❌ 儲存失敗：${e?.message ?? e}`);
      console.error(e);
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(""), 3000);
    }
  };

  const exportJSON = () => {
    try {
      const blob = new Blob([JSON.stringify({ name, nodes, edges }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setMsg("✅ 匯出成功");
      setTimeout(() => setMsg(""), 3000);
    } catch {
      setMsg("❌ 匯出失敗");
      setTimeout(() => setMsg(""), 3000);
    }
  };

  const importJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const data = JSON.parse(ev.target?.result as string);
        if (data.name) setName(data.name);
        if (data.nodes) setNodes(data.nodes);
        if (data.edges) setEdges(data.edges);
        setMsg("✅ 匯入成功");
      } catch { setMsg("❌ 匯入失敗"); }
      setTimeout(() => setMsg(""), 3000);
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--c-bg)" }}>
      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
        borderBottom: "1px solid var(--c-border)", background: "var(--c-bg-deep)",
      }}>
        <input value={name} onChange={e => setName(e.target.value)}
          style={{
            background: "var(--c-bg)", border: "1px solid var(--c-border)", borderRadius: 6,
            color: "var(--c-text)", padding: "6px 10px", fontSize: 14, width: 200,
          }} />
        <button onClick={save} disabled={saving}
          style={{ padding: "6px 16px", borderRadius: 6, background: "#00c076", border: "none", color: "#000", cursor: "pointer", fontSize: 13 }}>
          {saving ? "儲存中..." : "💾 儲存"}
        </button>
        <button onClick={exportJSON}
          style={{ padding: "6px 14px", borderRadius: 6, background: "transparent", border: "1px solid var(--c-border)", color: "var(--c-text-dim)", cursor: "pointer", fontSize: 13 }}>
          📤 匯出
        </button>
        <label style={{ padding: "6px 14px", borderRadius: 6, background: "transparent", border: "1px solid var(--c-border)", color: "var(--c-text-dim)", cursor: "pointer", fontSize: 13 }}>
          📥 匯入
          <input type="file" accept=".json" onChange={importJSON} style={{ display: "none" }} />
        </label>
        {msg && <span style={{ fontSize: 13, color: msg.startsWith("✅") ? "#00c076" : "#ef4444" }}>{msg}</span>}
      </div>

      {/* Editor */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <NodePalette onAdd={addNode} />
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onNodeDoubleClick={onNodeDoubleClick}
            fitView
          >
            <Background color="#333" gap={16} />
            <Controls />
            <MiniMap nodeColor="#00c076" style={{ background: "var(--c-bg-deep)" }} />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}
