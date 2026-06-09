"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppContext } from "@/contexts/AppContext";

const navItems = [
  { href: "/",           icon: "🏠", label: "市場總覽" },
  { href: "/stock",      icon: "📈", label: "個股分析" },
  { href: "/screener",   icon: "🔍", label: "選股工作流" },
  { href: "/watchlist",  icon: "⭐", label: "我的自選收藏" },
  { href: "/portfolio",  icon: "💼", label: "持倉追蹤" },
  { href: "/backtest",   icon: "📊", label: "回測" },
  { href: "/alerts",     icon: "🔔", label: "警報設定" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme, setIsSettingsOpen } = useAppContext();

  return (
    <aside style={{
      width: 200, minHeight: "100vh",
      background: "var(--c-sidebar-bg)",
      borderRight: "1px solid var(--c-sidebar-border)",
      display: "flex", flexDirection: "column", flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid var(--c-sidebar-border)" }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: "#00c076", letterSpacing: 1 }}>
          🟢 台股AI雷達
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "8px 0" }}>
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 16px", textDecoration: "none",
              color: active ? "var(--c-sidebar-text)" : "var(--c-text-dim)",
              background: active ? "var(--c-sidebar-active)" : "transparent",
              borderLeft: active ? "2px solid #00c076" : "2px solid transparent",
              fontSize: 15, transition: "all 0.15s",
            }}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom buttons */}
      <div style={{
        padding: "10px 12px 14px",
        borderTop: "1px solid var(--c-sidebar-border)",
        display: "flex", gap: 8,
      }}>
        <button
          onClick={() => setIsSettingsOpen(true)}
          title="股票池設定"
          style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            gap: 6, padding: "8px 0",
            background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
            borderRadius: 8, color: "var(--c-text-dim)", fontSize: 13,
            cursor: "pointer", transition: "all 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = "var(--c-text)";
            e.currentTarget.style.borderColor = "#00c07644";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = "var(--c-text-dim)";
            e.currentTarget.style.borderColor = "var(--c-border)";
          }}
        >
          <span>⚙️</span><span>設定</span>
        </button>

        <button
          onClick={toggleTheme}
          title={theme === "dark" ? "切換亮色模式" : "切換暗色模式"}
          style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            gap: 6, padding: "8px 0",
            background: "var(--c-bg-deep)", border: "1px solid var(--c-border)",
            borderRadius: 8, color: "var(--c-text-dim)", fontSize: 13,
            cursor: "pointer", transition: "all 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = "var(--c-text)";
            e.currentTarget.style.borderColor = "#ffd60044";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = "var(--c-text-dim)";
            e.currentTarget.style.borderColor = "var(--c-border)";
          }}
        >
          <span>{theme === "dark" ? "☀️" : "🌙"}</span>
          <span>{theme === "dark" ? "亮色" : "暗色"}</span>
        </button>
      </div>
    </aside>
  );
}
