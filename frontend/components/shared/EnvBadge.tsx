"use client"

export function EnvBadge() {
  const isSimulation = process.env.NEXT_PUBLIC_SIMULATION === "true"
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-bold ${
      isSimulation
        ? "bg-yellow-500/20 text-yellow-400"
        : "bg-red-500/20 text-red-400"
    }`}>
      {isSimulation ? "模擬" : "正式"}
    </span>
  )
}
