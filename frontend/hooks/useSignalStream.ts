"use client";
import { useState, useEffect, useRef } from "react";

export interface SignalEvent {
  signal_id: number;
  symbol: string;
  action: "buy" | "sell";
  quantity: number;
  ai_confidence: number;
  order_status: string;
  timestamp: string;
}

// Shioaji Tick 格式（SinopacBroker 推播）
export interface TickEvent {
  price: number;
  volume: number;
  timestamp: number;   // ms unix
  symbol?: string;
  error?: string;
}

// SSE 需直連後端：Next dev 代理會緩衝 EventSource 串流。EventSource 是 simple
// request 無 CORS preflight，後端 CORS 已允許 localhost:3002（見 main.py）。
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useSignalStream() {
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(`${API}/api/stream/signals`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onmessage = (e) => {
      try {
        const signal: SignalEvent = JSON.parse(e.data);
        setSignals(prev => [signal, ...prev].slice(0, 50));
      } catch {}
    };
    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, []);

  const clearSignals = () => setSignals([]);

  return { signals, connected, clearSignals };
}

export function useTickStream(symbol: string) {
  const [tick, setTick] = useState<TickEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!symbol) return;
    const es = new EventSource(`${API}/api/stream/quote/${symbol}`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.addEventListener("tick", (e: MessageEvent) => {
      try {
        const data: TickEvent = JSON.parse(e.data);
        if (!data.error) setTick(data);
      } catch {}
    });
    es.onerror = () => setConnected(false);

    return () => {
      es.close();
      setConnected(false);
    };
  }, [symbol]);

  return { tick, connected };
}
