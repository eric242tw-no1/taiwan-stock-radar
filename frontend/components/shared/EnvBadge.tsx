"use client"

export function EnvBadge() {
  const env = process.env.NEXT_PUBLIC_TRADING_ENV ?? "simulation"
  const isSimulation = env !== "production"
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-bold ${
      isSimulation
        ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
        : "bg-red-500/20 text-red-400 border border-red-500/30"
    }`}>
      {isSimulation ? "🟡 模擬" : "🔴 正式"}
    </span>
  )
}
