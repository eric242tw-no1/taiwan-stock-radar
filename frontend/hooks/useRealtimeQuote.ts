"use client"

import { useEffect, useState } from "react"

export interface QuoteData {
  symbol: string
  name?: string
  price: number
  change: number
  change_pct: number
  volume?: number
  high?: number
  low?: number
  open?: number
  prev_close?: number
  market_status?: string
  updated_at?: string
  error?: string
}

export function useRealtimeQuote(symbol: string | null) {
  const [quote, setQuote] = useState<QuoteData | null>(null)

  useEffect(() => {
    if (!symbol) return
    const es = new EventSource(`/api/stream/quote/${symbol}`)
    es.onmessage = (e) => {
      try {
        setQuote(JSON.parse(e.data))
      } catch {
        // ignore parse errors
      }
    }
    return () => es.close()
  }, [symbol])

  return quote
}
