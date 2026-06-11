"use client"

import { useEffect, useState } from "react"

export interface MarketStreamData {
  taiex?: { price: number; change: number; change_pct: number }
  otc?: { price: number; change: number; change_pct: number }
  futures?: { price: number; change: number; change_pct: number }
  usd_twd?: number
  error?: string
}

export function useMarketStream() {
  const [data, setData] = useState<MarketStreamData | null>(null)

  useEffect(() => {
    const es = new EventSource("/api/stream/market")
    es.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data))
      } catch {
        // ignore parse errors
      }
    }
    return () => es.close()
  }, [])

  return data
}
