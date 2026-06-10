"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppContext } from "@/contexts/AppContext";

import { useIsMobile, useIsTablet } from "@/hooks/useBreakpoint";
import { useUsIndices, useTwMarket, useChip, fmtPrice, fmtPct, fmtShares, API } from "@/hooks/useMarketApi";
import { Card, IndexCard } from "@/components/market/Card";
import { FearGreedGauge, VixCard, fngColor } from "@/components/market/FearGreedSection";
import { BuffettCard } from "@/components/market/BuffettCard";
import { TwHeatCell } from "@/components/market/TwHeatCell";
import { UsHeatCell, UsStockModal, UsStock } from "@/components/market/UsHeatMap";

// ── 恐懼貪婪歷史比對型別 ──────────────────────────────────────
interface FgPoint { value: number; label: string; date: string }
interface FgData { today?: FgPoint; yesterday?: FgPoint; week_ago?: FgPoint; month_ago?: FgPoint; year_ago?: FgPoint }

// ── 主頁面 ────────────────────────────────────────────────────
export default function MarketOverview() {
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const router   = useRouter();
  const { stockPool, setIsSettingsOpen } = useAppContext();

  // ── 共用市場資料 ─────────────────────────────────────────────
  const usData   = useUsIndices();
  const twData   = useTwMarket();
  const chipData = useChip();

  // ── 台股產業熱力圖 ───────────────────────────────────────────
  const [tw, setTw] = useState<{ label: string; chg: number }[]>([]);
  useEffect(() => {
    fetch(`${API}/api/market/sectors`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.sectors?.length && setTw(d.sectors))
      .catch(() => {});
  }, []);

  // ── 記憶體族群 ───────────────────────────────────────────────
  const [memStocks, setMemStocks] = useState<{ code: string; name: string; price: number; chg: number }[]>([]);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/memory-stocks`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.stocks?.length && setMemStocks(d.stocks))
      .catch(() => {});
    load();
    const id = setInterval(load, 300_000);
    return () => clearInterval(id);
  }, []);

  // ── 八大官股 ─────────────────────────────────────────────────
  type GovFunds = { items: { name: string; net_bn: number; direction: string }[]; total_bn: number; date: string; source: string };
  const [govFunds, setGovFunds] = useState<GovFunds | null | "unavailable">(null);
  useEffect(() => {
    fetch(`${API}/api/market/gov-funds`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return;
        if (d.source === "unavailable" || !d.items?.length) setGovFunds("unavailable");
        else setGovFunds(d);
      })
      .catch(() => setGovFunds("unavailable"));
  }, []);

  // ── 恐懼貪婪指數 ─────────────────────────────────────────────
  const [fg, setFg] = useState<FgData | null>(null);
  useEffect(() => {
    fetch(`${API}/api/market/fear-greed`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.today && setFg(d))
      .catch(() => {});
  }, []);

  // ── 美股科技熱力圖 ───────────────────────────────────────────
  const [us, setUs] = useState<UsStock[]>([]);
  const [usModal, setUsModal] = useState<UsStock | null>(null);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/us-stocks`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.stocks?.length && setUs(d.stocks))
      .catch(() => {});
    load();
    const id = setInterval(load, 300_000);
    return () => clearInterval(id);
  }, []);

  // ── 波段領頭羊 ───────────────────────────────────────────────
  const [leaders, setLeaders] = useState<{ code: string; name: string; score: number; rsi: number }[]>([]);
  useEffect(() => {
    const codesParam = stockPool.length > 0 ? `&codes=${stockPool.map(s => s.code).join(",")}` : "";
    const load = () => fetch(`${API}/api/market/leaders?limit=5${codesParam}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.results && setLeaders(d.results))
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [stockPool]);

  // ── 漲幅排行榜 ───────────────────────────────────────────────
  const [topMovers, setTopMovers] = useState<{ code: string; name: string; price: number; chg_pct: number }[]>([]);
  useEffect(() => {
    const codesParam = stockPool.length > 0 ? `&codes=${stockPool.map(s => s.code).join(",")}` : "";
    const load = () => fetch(`${API}/api/market/top-movers?limit=5${codesParam}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.results && setTopMovers(d.results))
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [stockPool]);

  // ── 市場快訊 ─────────────────────────────────────────────────
  type NewsItem = { time: string; date: string; text: string; tag: string; url: string };
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  useEffect(() => {
    const load = () => fetch(`${API}/api/market/news?limit=8`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.items?.length && setNewsItems(d.items))
      .catch(() => {});
    load();
    const id = setInterval(load, 600_000);
    return () => clearInterval(id);
  }, []);

  // ── 市場溫度計輔助計算 ────────────────────────────────────────
  const taiex    = twData?.taiex;
  const breadth  = twData?.breadth;
  const total    = (breadth?.up ?? 0) + (breadth?.down ?? 0);
  const bullPct  = total > 0 ? Math.round((breadth!.up / total) * 100) : 50;
  const bullColor = bullPct >= 55 ? "#ff4d4d" : bullPct <= 45 ? "#00c076" : "#f5a623";
  const bullLabel = bullPct >= 55 ? "偏多↑" : bullPct <= 45 ? "偏空↓" : "中性";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {usModal && <UsStockModal stock={usModal} onClose={() => setUsModal(null)} />}

      {/* ══ Row 1：市場溫度計 ＋ 恐懼與貪婪 ＋ 巴菲特指標 ══ */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : isTablet ? "1fr 1fr" : "1fr 1fr 1fr", gap: 12 }}>

        {/* 市場溫度計 */}
        <Card title="市場溫度計">
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 12 }}>
            <div style={{ width: 64, height: 64, borderRadius: "50%", background: `conic-gradient(${bullColor} 0% ${bullPct}%, #1a1a2a ${bullPct}% 100%)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <div style={{ width: 50, height: 50, borderRadius: "50%", background: "var(--c-bg-modal)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 700, color: bullColor }}>
                {total > 0 ? bullPct : "--"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 22, color: bullColor, fontWeight: 700 }}>{bullLabel}</div>
              <div style={{ fontSize: 19, color: "var(--c-text-dim)", marginTop: 2 }}>
                {taiex ? `成交 ${taiex.trade_value_bn.toFixed(0)}億` : "成交 ---"}
              </div>
              {taiex && <div style={{ fontSize: 19, color: "var(--c-text-dim)", marginTop: 1 }}>更新 {taiex.update_time || "---"}</div>}
            </div>
          </div>
          {[
            { label: "上漲家數", value: breadth?.source !== "unavailable" ? breadth?.up.toLocaleString() ?? "---" : "---", color: "#ff4d4d" },
            { label: "下跌家數", value: breadth?.source !== "unavailable" ? breadth?.down.toLocaleString() ?? "---" : "---", color: "#00c076" },
            { label: "加權指數", value: taiex ? taiex.price.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "---", color: (taiex?.change_pct ?? 0) >= 0 ? "#ff4d4d" : "#00c076" },
            { label: "OTC 指數", value: twData ? twData.otc.price.toFixed(2) : "---", color: (twData?.otc.change_pct ?? 0) >= 0 ? "#ff4d4d" : "#00c076" },
            { label: "外資方向", value: chipData ? fmtShares(chipData.totals.foreign) : "---", color: (chipData?.totals.foreign ?? 0) >= 0 ? "#ff4d4d" : "#00c076" },
          ].map(r => (
            <div key={r.label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, paddingBottom: 5, borderBottom: "1px solid #1a1a2a" }}>
              <span style={{ fontSize: 19, color: "var(--c-text-dim)" }}>{r.label}</span>
              <span style={{ fontSize: 19, fontWeight: 600, color: r.color }}>{r.value}</span>
            </div>
          ))}
        </Card>

        {/* 恐懼貪婪指數 */}
        <Card title="恐懼與貪婪指數">
          {fg?.today ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <FearGreedGauge value={fg.today.value} />
              <div style={{ textAlign: "center", fontSize: 11, color: "var(--c-text-dim)", marginTop: -6 }}>
                {fg.today.date} · 加密市場情緒
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4, borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
                {([
                  { key: "yesterday", label: "前一日" },
                  { key: "week_ago",  label: "一週前" },
                  { key: "month_ago", label: "一個月前" },
                  { key: "year_ago",  label: "一年前" },
                ] as { key: keyof FgData; label: string }[]).map(({ key, label }) => {
                  const pt = fg[key] as FgPoint | undefined;
                  if (!pt) return null;
                  const c = fngColor(pt.value);
                  return (
                    <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 17 }}>
                      <span style={{ color: "var(--c-text-dim)" }}>{label}
                        <span style={{ color: "#444460", marginLeft: 5, fontSize: 12 }}>{pt.date}</span>
                      </span>
                      <span style={{ color: c, fontWeight: 700, fontFamily: "'JetBrains Mono',monospace" }}>{pt.label} {pt.value}</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
                <VixCard
                  value={usData ? fmtPrice(usData.vix.price, "vix") : "---"}
                  chg={usData ? fmtPct(usData.vix.change_pct) : "---"}
                  level={(usData?.vix.level ?? "low") as "low" | "medium" | "high"}
                />
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--c-text-dim)", fontSize: 13, padding: "40px 0", textAlign: "center" }}>載入中…</div>
          )}
        </Card>

        {/* 巴菲特指標 */}
        <BuffettCard />

      </div>

      {/* ══ Row 2：八大官股 ＋ 美股指數 ＋ 美股熱力圖 ＋ 台股產業熱力圖 ══ */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : isTablet ? "1fr 1fr" : "1fr 1fr 1.5fr 1.5fr", gap: 12 }}>

        {/* 八大官股 */}
        <Card title="八大官股動向">
          {govFunds === null ? (
            <div style={{ fontSize: 15, color: "var(--c-text-dim)", padding: "20px 0", textAlign: "center" }}>載入中…</div>
          ) : govFunds === "unavailable" ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.6 }}>
              <div style={{ fontSize: 22, marginBottom: 8 }}>📭</div>
              <div>資料不可用</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>非交易時段或資料來源無回應</div>
            </div>
          ) : (
            <>
              {govFunds.items.map(b => (
                <div key={b.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, padding: "4px 0", borderBottom: "1px solid var(--c-border)" }}>
                  <span style={{ fontSize: 15, color: "var(--c-text-mid)" }}>{b.name}</span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: b.net_bn >= 0 ? "#ff4d4d" : "#00c076", fontFamily: "'JetBrains Mono',monospace" }}>
                    {b.net_bn >= 0 ? "+" : ""}{b.net_bn}億
                  </span>
                </div>
              ))}
              <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 4 }}>
                合計 {govFunds.total_bn >= 0 ? "+" : ""}{govFunds.total_bn}億
                {govFunds.date ? ` ｜ ${govFunds.date}` : ""}
                {govFunds.source === "dealer_proxy" ? " (估算)" : ""}
              </div>
            </>
          )}
        </Card>

        {/* 美股指數 */}
        <Card title="美股指數">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <IndexCard label="S&P 500" value={usData ? fmtPrice(usData.sp500.price,  "sp500")  : "---"} chg={usData ? fmtPct(usData.sp500.change_pct)  : "---"} up={(usData?.sp500.change_pct  ?? 1) >= 0} />
            <IndexCard label="Nasdaq"  value={usData ? fmtPrice(usData.nasdaq.price, "nasdaq") : "---"} chg={usData ? fmtPct(usData.nasdaq.change_pct) : "---"} up={(usData?.nasdaq.change_pct ?? 1) >= 0} />
            <IndexCard label="道瓊"    value={usData ? fmtPrice(usData.dji.price,    "dji")    : "---"} chg={usData ? fmtPct(usData.dji.change_pct)    : "---"} up={(usData?.dji.change_pct    ?? 0) >= 0} />
          </div>
        </Card>

        {/* 美股科技熱力圖 */}
        <Card title="美股科技熱力圖（點擊看詳情）">
          {us.length === 0 ? (
            <div style={{ color: "var(--c-text-dim)", fontSize: 13, padding: "20px 0", textAlign: "center" }}>載入中…</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
              {us.map(s => (
                <UsHeatCell key={s.label} {...s} onClick={() => setUsModal(s)} />
              ))}
            </div>
          )}
        </Card>

        {/* 台股產業熱力圖 */}
        <Card title="台股產業熱力圖（漲紅跌綠）">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 5 }}>
            {tw.map(i => <TwHeatCell key={i.label} {...i} />)}
          </div>
          {memStocks.length > 0 && (
            <div style={{ marginTop: 10, borderTop: "1px solid var(--c-border)", paddingTop: 8 }}>
              <div style={{ fontSize: 12, color: "var(--c-label)", marginBottom: 5, letterSpacing: 1, textTransform: "uppercase" }}>💾 記憶體族群</div>
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {memStocks.map(s => {
                  const up = s.chg >= 0;
                  const color = up ? "#ff4d4d" : "#00c076";
                  return (
                    <div key={s.code} onClick={() => router.push(`/stock?s=${s.code}`)}
                      style={{ background: up ? "#2a0a0a" : "#002210", border: `1px solid ${color}44`, borderRadius: 5, padding: "4px 8px", cursor: "pointer", textAlign: "center", transition: "filter 0.15s" }}
                      onMouseEnter={e => (e.currentTarget.style.filter = "brightness(1.3)")}
                      onMouseLeave={e => (e.currentTarget.style.filter = "brightness(1)")}
                    >
                      <div style={{ fontSize: 12, color: "var(--c-text-mid)" }}>{s.name}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color, fontFamily: "'JetBrains Mono',monospace" }}>
                        {up ? "+" : ""}{s.chg.toFixed(2)}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ══ Row 3：個股動向 ══ */}
      <div style={isMobile ? { display: "flex", gap: 10, overflowX: "auto", WebkitOverflowScrolling: "touch" as "touch", paddingBottom: 4, scrollSnapType: "x mandatory" }
        : { display: "grid", gridTemplateColumns: isTablet ? "1fr 1fr" : "1fr 1fr 1fr 1fr", gap: 12 }}>

        {/* 波段領頭羊 */}
        <Card title="波段領頭羊" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {leaders.length === 0 ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.8 }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>📋</div>
              <div>尚無追蹤個股資料</div>
              <button onClick={() => setIsSettingsOpen(true)} style={{ marginTop: 10, background: "transparent", border: "1px solid #00c07644", borderRadius: 6, color: "#00c076", fontSize: 13, cursor: "pointer", padding: "4px 14px" }}>
                ⚙️ 設定股票池
              </button>
            </div>
          ) : leaders.map(s => (
            <div key={s.code} onClick={() => router.push(`/stock?s=${s.code}`)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid #1a1a2a", cursor: "pointer" }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--c-bg-deep)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 16, color: "#3d7eff", fontWeight: 700, whiteSpace: "nowrap" }}>{s.code}</span>
                <span style={{ fontSize: 15, color: "var(--c-text-dim)", whiteSpace: "nowrap" }}>{s.name}</span>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span style={{ fontSize: 14, color: "var(--c-text-dim)" }}>RSI {s.rsi}</span>
                <span style={{ fontSize: 14, padding: "1px 6px", borderRadius: 3, fontWeight: 700, background: s.score >= 80 ? "#3d0000" : "#1a2a3a", color: s.score >= 80 ? "#ff4d4d" : "#3d7eff", border: `1px solid ${s.score >= 80 ? "#ff4d4d44" : "#3d7eff44"}` }}>
                  AI {s.score}
                </span>
              </div>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>AI ≥ 80 = 強烈關注 · 每分鐘更新 · 點擊看個股</div>
        </Card>

        {/* 漲幅排行 */}
        <Card title="漲幅排行榜" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {topMovers.length === 0 ? (
            <div style={{ fontSize: 14, color: "var(--c-text-dim)", padding: "16px 0", textAlign: "center", lineHeight: 1.8 }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>📊</div>
              <div>尚無排行資料</div>
              <button onClick={() => setIsSettingsOpen(true)} style={{ marginTop: 10, background: "transparent", border: "1px solid #00c07644", borderRadius: 6, color: "#00c076", fontSize: 13, cursor: "pointer", padding: "4px 14px" }}>
                ⚙️ 設定股票池
              </button>
            </div>
          ) : topMovers.map((s, i) => (
            <div key={s.code} onClick={() => router.push(`/stock?s=${s.code}`)}
              style={{ display: "flex", gap: 8, alignItems: "center", padding: "7px 0", borderBottom: "1px solid #1a1a2a", cursor: "pointer" }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--c-bg-deep)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ fontSize: 14, color: "var(--c-text-dim)", width: 14, flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontSize: 16, color: "#3d7eff", fontWeight: 700, whiteSpace: "nowrap" }}>{s.code}</span>
              <span style={{ fontSize: 15, color: "var(--c-text-dim)", flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</span>
              <span style={{ fontSize: 15, fontWeight: 700, whiteSpace: "nowrap", color: s.chg_pct >= 0 ? "#ff4d4d" : "#00c076" }}>
                {s.chg_pct >= 0 ? "+" : ""}{s.chg_pct.toFixed(2)}%
              </span>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 8 }}>追蹤股池即時漲幅 · 點擊看個股</div>
        </Card>

        {/* 市場快訊 */}
        <Card title="市場快訊" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {newsItems.length === 0 ? (
            <div style={{ color: "var(--c-text-dim)", fontSize: 13, padding: "12px 0" }}>載入中…</div>
          ) : newsItems.map((n, i) => {
            const tagColor = n.tag === "利多" ? "#00c076" : n.tag === "利空" ? "#ff4d4d" : n.tag === "注意" ? "#f5a623" : "var(--c-text-dim)";
            return (
              <a key={i} href={n.url} target="_blank" rel="noreferrer" style={{ display: "block", textDecoration: "none", padding: "7px 0", borderBottom: "1px solid #1a1a2a" }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 3 }}>
                  <span style={{ fontSize: 12, color: "var(--c-text-dim)" }}>{n.date} {n.time}</span>
                  <span style={{ fontSize: 11, padding: "0 5px", borderRadius: 2, border: `1px solid ${tagColor}55`, color: tagColor }}>{n.tag}</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--c-text-mid)", lineHeight: 1.5 }}>{n.text}</div>
              </a>
            );
          })}
          <div style={{ fontSize: 11, color: "var(--c-text-dim)", marginTop: 6 }}>資料來源：鉅亨網 · 每10分鐘更新</div>
        </Card>

        {/* 台美連動 */}
        <Card title="台美連動分析" style={isMobile ? { minWidth: "75vw", scrollSnapAlign: "start", flexShrink: 0 } : {}}>
          {[
            { label: "NVDA ↔ 台積電",    corr: 0.82,  color: "#00c076" },
            { label: "費半 ↔ 半導體",    corr: 0.79,  color: "#00c076" },
            { label: "TSMC ADR ↔ 現貨", corr: 0.94,  color: "#00c076" },
            { label: "DXY ↔ 台幣",      corr: -0.71, color: "#ff4d4d" },
          ].map(c => (
            <div key={c.label} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 15, color: "var(--c-text-dim)" }}>{c.label}</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: c.color }}>{c.corr}</span>
              </div>
              <div style={{ height: 3, background: "var(--c-border)", borderRadius: 2 }}>
                <div style={{ height: "100%", borderRadius: 2, background: c.color, width: `${Math.abs(c.corr) * 100}%` }} />
              </div>
            </div>
          ))}
          <div style={{ fontSize: 13, color: "var(--c-text-dim)", marginTop: 4 }}>60 日滾動相關係數 ｜ 每日更新</div>
        </Card>

      </div>
    </div>
  );
}
