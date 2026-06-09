"use client";
import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

// 各產業的代表股清單（可擴充）
const INDUSTRY_STOCKS: Record<string, {
  code: string; name: string; price: number; change_pct: number;
  volume_bn: number; rsi: number; ma_align: boolean; foreign_buy: boolean;
}[]> = {
  "半導體": [
    { code:"2330", name:"台積電",  price:1082, change_pct: 2.15, volume_bn:182.4, rsi:62.4, ma_align:true,  foreign_buy:true  },
    { code:"2454", name:"聯發科",  price: 940, change_pct: 1.38, volume_bn: 28.7, rsi:58.3, ma_align:true,  foreign_buy:true  },
    { code:"3711", name:"日月光",  price: 158, change_pct: 1.29, volume_bn: 12.1, rsi:57.3, ma_align:true,  foreign_buy:true  },
    { code:"2303", name:"聯電",    price:  52, change_pct: 0.97, volume_bn: 15.4, rsi:52.8, ma_align:false, foreign_buy:true  },
    { code:"3034", name:"聯詠",    price: 465, change_pct: 4.72, volume_bn: 38.6, rsi:74.8, ma_align:true,  foreign_buy:true  },
    { code:"6770", name:"力積電",  price:  39, change_pct: 9.97, volume_bn: 56.3, rsi:82.1, ma_align:true,  foreign_buy:false },
    { code:"4968", name:"立積",    price: 185, change_pct: 1.64, volume_bn:  7.4, rsi:53.9, ma_align:true,  foreign_buy:false },
    { code:"6531", name:"愛普",    price: 895, change_pct:10.00, volume_bn: 12.8, rsi:88.4, ma_align:true,  foreign_buy:false },
    { code:"2379", name:"瑞昱",    price: 688, change_pct:-1.72, volume_bn:  9.1, rsi:38.4, ma_align:false, foreign_buy:false },
  ],
  "電子製造": [
    { code:"2317", name:"鴻海",    price: 218, change_pct: 0.92, volume_bn: 34.1, rsi:55.1, ma_align:true,  foreign_buy:true  },
    { code:"2382", name:"廣達",    price: 322, change_pct: 1.86, volume_bn: 22.8, rsi:64.5, ma_align:true,  foreign_buy:true  },
    { code:"2308", name:"台達電",  price: 392, change_pct: 3.20, volume_bn: 12.3, rsi:71.2, ma_align:true,  foreign_buy:false },
    { code:"2376", name:"技嘉",    price: 312, change_pct: 5.41, volume_bn: 19.7, rsi:72.1, ma_align:true,  foreign_buy:false },
  ],
  "電子零組件": [
    { code:"2308", name:"台達電",  price: 392, change_pct: 3.20, volume_bn: 12.3, rsi:71.2, ma_align:true,  foreign_buy:false },
    { code:"3037", name:"欣興",    price: 168, change_pct: 3.85, volume_bn: 22.4, rsi:65.2, ma_align:true,  foreign_buy:true  },
  ],
  "航運": [
    { code:"2603", name:"長榮",    price: 218, change_pct: 2.83, volume_bn: 41.2, rsi:68.9, ma_align:true,  foreign_buy:true  },
    { code:"2615", name:"萬海",    price:  98, change_pct:-9.91, volume_bn: 28.4, rsi:21.3, ma_align:false, foreign_buy:false },
    { code:"2609", name:"陽明",    price:  72, change_pct:-9.86, volume_bn: 31.2, rsi:19.7, ma_align:false, foreign_buy:false },
  ],
  "金融": [
    { code:"2881", name:"富邦金",  price: 102, change_pct: 0.49, volume_bn:  8.2, rsi:48.7, ma_align:false, foreign_buy:false },
    { code:"2886", name:"兆豐金",  price:  44, change_pct:-0.22, volume_bn:  5.4, rsi:42.1, ma_align:false, foreign_buy:false },
    { code:"2892", name:"第一金",  price:  31, change_pct: 0.32, volume_bn:  4.1, rsi:46.8, ma_align:false, foreign_buy:false },
    { code:"2880", name:"華南金",  price:  25, change_pct: 0.40, volume_bn:  3.8, rsi:49.3, ma_align:false, foreign_buy:false },
  ],
  "光電": [
    { code:"3481", name:"群創",    price:  18, change_pct: 9.89, volume_bn: 42.1, rsi:79.4, ma_align:true,  foreign_buy:false },
    { code:"3008", name:"大立光",  price:2280, change_pct:-0.87, volume_bn:  4.1, rsi:39.6, ma_align:false, foreign_buy:false },
  ],
  "通訊": [
    { code:"2412", name:"中華電",  price: 128, change_pct: 0.08, volume_bn:  3.1, rsi:44.3, ma_align:false, foreign_buy:false },
  ],
  "零組件": [
    { code:"2308", name:"台達電",  price: 392, change_pct: 3.20, volume_bn: 12.3, rsi:71.2, ma_align:true,  foreign_buy:false },
    { code:"3037", name:"欣興",    price: 168, change_pct: 3.85, volume_bn: 22.4, rsi:65.2, ma_align:true,  foreign_buy:true  },
  ],
  "電通路": [
    { code:"2395", name:"研華",    price: 388, change_pct: 0.52, volume_bn:  4.3, rsi:49.8, ma_align:false, foreign_buy:false },
  ],
  "其他電子": [
    { code:"6669", name:"緯穎",    price:3450, change_pct: 2.08, volume_bn: 14.3, rsi:61.8, ma_align:true,  foreign_buy:true  },
    { code:"2379", name:"瑞昱",    price: 688, change_pct:-1.72, volume_bn:  9.1, rsi:38.4, ma_align:false, foreign_buy:false },
  ],
  "電子": [
    { code:"2330", name:"台積電",  price:1082, change_pct: 2.15, volume_bn:182.4, rsi:62.4, ma_align:true,  foreign_buy:true  },
    { code:"2454", name:"聯發科",  price: 940, change_pct: 1.38, volume_bn: 28.7, rsi:58.3, ma_align:true,  foreign_buy:true  },
    { code:"2317", name:"鴻海",    price: 218, change_pct: 0.92, volume_bn: 34.1, rsi:55.1, ma_align:true,  foreign_buy:true  },
    { code:"2382", name:"廣達",    price: 322, change_pct: 1.86, volume_bn: 22.8, rsi:64.5, ma_align:true,  foreign_buy:true  },
  ],
  "建材": [
    { code:"2002", name:"中鋼",    price:  24, change_pct:-0.41, volume_bn:  6.8, rsi:35.2, ma_align:false, foreign_buy:false },
  ],
  "鋼鐵": [
    { code:"2002", name:"中鋼",    price:  24, change_pct:-0.41, volume_bn:  6.8, rsi:35.2, ma_align:false, foreign_buy:false },
  ],
  "生技": [
    { code:"4743", name:"合一",    price: 168, change_pct: 3.21, volume_bn:  5.2, rsi:62.1, ma_align:true,  foreign_buy:false },
    { code:"6547", name:"安派",    price:  88, change_pct: 1.15, volume_bn:  2.1, rsi:55.4, ma_align:false, foreign_buy:false },
  ],
  "化生醫": [
    { code:"4743", name:"合一",    price: 168, change_pct: 3.21, volume_bn:  5.2, rsi:62.1, ma_align:true,  foreign_buy:false },
  ],
};

function rsiColor(r: number) {
  if (r >= 70) return "#ff4d4d";
  if (r <= 30) return "#3d7eff";
  return "#f5a623";
}

function IndustryContent() {
  const params = useSearchParams();
  const router = useRouter();
  const sector = params.get("s") ?? "";

  const stocks = INDUSTRY_STOCKS[sector] ?? [];

  // 統計
  const up   = stocks.filter(s => s.change_pct > 0).length;
  const down = stocks.filter(s => s.change_pct < 0).length;
  const avgChg = stocks.length
    ? (stocks.reduce((a, s) => a + s.change_pct, 0) / stocks.length).toFixed(2)
    : "0.00";
  const avgChgNum = parseFloat(avgChg);

  return (
    <div style={{ maxWidth:960, margin:"0 auto", padding:"16px 20px" }}>
      {/* 頁頭 */}
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:16 }}>
        <button onClick={() => router.back()} style={{
          background:"#1a1a24", border:"1px solid #2a2a3a", borderRadius:7,
          color:"#8888aa", fontSize:13, padding:"5px 12px", cursor:"pointer",
        }}>← 返回</button>
        <h2 style={{ fontSize:20, fontWeight:700, color:"#e8e8f0", margin:0 }}>
          {sector} 產業個股
        </h2>
      </div>

      {/* 產業概況 */}
      <div style={{
        display:"flex", gap:12, marginBottom:20, flexWrap:"wrap",
      }}>
        {[
          { label:"本日均漲跌", value:`${avgChgNum >= 0 ? "+" : ""}${avgChg}%`, color: avgChgNum >= 0 ? "#ff4d4d" : "#00c076" },
          { label:"上漲家數",   value:`${up} 家`,   color:"#ff4d4d" },
          { label:"下跌家數",   value:`${down} 家`, color:"#00c076" },
          { label:"追蹤股數",   value:`${stocks.length} 檔`, color:"#8888aa" },
        ].map(item => (
          <div key={item.label} style={{
            background:"#111118", border:"1px solid #2a2a3a", borderRadius:9,
            padding:"10px 16px", flex:"1", minWidth:120,
          }}>
            <div style={{ fontSize:11, color:"#555570", marginBottom:4 }}>{item.label}</div>
            <div style={{ fontSize:18, fontWeight:700, color:item.color }}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* 股票列表 */}
      {stocks.length === 0 ? (
        <div style={{ textAlign:"center", color:"#555570", padding:"60px 0", fontSize:15 }}>
          此產業暫無資料（即將接入真實 API）
        </div>
      ) : (
        <div style={{ display:"flex", flexDirection:"column", gap:1 }}>
          {/* 表頭 */}
          <div style={{
            display:"grid", gridTemplateColumns:"1fr 80px 90px 80px 80px 80px 60px",
            padding:"6px 14px", fontSize:11, color:"#555570",
          }}>
            <span>股票</span>
            <span style={{ textAlign:"right" }}>現價</span>
            <span style={{ textAlign:"right" }}>漲跌幅</span>
            <span style={{ textAlign:"right" }}>成交額</span>
            <span style={{ textAlign:"center" }}>RSI</span>
            <span style={{ textAlign:"center" }}>均線</span>
            <span style={{ textAlign:"center" }}>外資</span>
          </div>
          {stocks
            .sort((a, b) => b.change_pct - a.change_pct)
            .map(s => {
              const up = s.change_pct >= 0;
              return (
                <div
                  key={s.code}
                  onClick={() => router.push(`/stock?s=${s.code}`)}
                  style={{
                    display:"grid", gridTemplateColumns:"1fr 80px 90px 80px 80px 80px 60px",
                    padding:"11px 14px", cursor:"pointer",
                    borderRadius:8, background:"#111118",
                    marginBottom:2,
                    border:"1px solid #1a1a2a",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background="#1a1a2e")}
                  onMouseLeave={e => (e.currentTarget.style.background="#111118")}
                >
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <span style={{ fontSize:14, fontWeight:700, color:"#e8e8f0" }}>{s.name}</span>
                    <span style={{ fontSize:12, color:"#555570" }}>{s.code}</span>
                  </div>
                  <span style={{ textAlign:"right", fontSize:14, fontWeight:600, color:"#e8e8f0" }}>{s.price.toLocaleString()}</span>
                  <span style={{ textAlign:"right", fontSize:14, fontWeight:600, color: up ? "#ff4d4d" : "#00c076" }}>
                    {up ? "▲" : "▼"}{Math.abs(s.change_pct).toFixed(2)}%
                  </span>
                  <span style={{ textAlign:"right", fontSize:13, color:"#8888aa" }}>{s.volume_bn.toFixed(1)}億</span>
                  <span style={{ textAlign:"center", fontSize:13, color:rsiColor(s.rsi) }}>{s.rsi.toFixed(1)}</span>
                  <span style={{ textAlign:"center", fontSize:12, color: s.ma_align ? "#00c076" : "#ff4d4d" }}>
                    {s.ma_align ? "多排" : "空排"}
                  </span>
                  <span style={{ textAlign:"center", fontSize:12, color: s.foreign_buy ? "#00c076" : "#ff4d4d" }}>
                    {s.foreign_buy ? "買" : "賣"}
                  </span>
                </div>
              );
            })}
        </div>
      )}

      <div style={{
        marginTop:20, padding:"10px 14px", borderRadius:8,
        background:"#0d0d15", border:"1px solid #2a2a3a", fontSize:12, color:"#8888aa",
      }}>
        <span style={{ color:"#f5a623", fontWeight:600 }}>⚠️ 目前為 Demo 資料</span>
        　Data Agent 上線後將顯示該產業全部掛牌股票即時報價。
      </div>
    </div>
  );
}

export default function IndustryPage() {
  return (
    <Suspense fallback={<div style={{ color:"#8888aa", padding:40 }}>載入中…</div>}>
      <IndustryContent />
    </Suspense>
  );
}
