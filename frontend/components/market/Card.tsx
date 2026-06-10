"use client";
import React from "react";

export function Card({
  title,
  children,
  style,
}: {
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        background: "var(--c-bg-card)",
        border: "1px solid var(--c-border)",
        borderRadius: 8,
        padding: 12,
        ...style,
      }}
    >
      <div
        style={{
          fontSize: 17,
          color: "var(--c-label)",
          marginBottom: 10,
          fontWeight: 700,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

export function IndexCard({
  label,
  value,
  chg,
  up,
}: {
  label: string;
  value: string;
  chg: string;
  up: boolean;
}) {
  return (
    <div
      style={{
        background: "var(--c-bg-deep)",
        border: "1px solid var(--c-border)",
        borderRadius: 8,
        padding: "10px 14px",
        flex: 1,
      }}
    >
      <div style={{ fontSize: 13, color: "var(--c-label)", marginBottom: 4, letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--c-text)", fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
      <div
        style={{
          fontSize: 15,
          color: up ? "#00c076" : "#ff4d4d",
          marginTop: 2,
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 600,
        }}
      >
        {chg}
      </div>
    </div>
  );
}
