"use client"

import { useState } from "react"

interface OrderInfo {
  symbol: string
  action: "buy" | "sell"
  quantity: number
  price: number
  stopLoss: number
  takeProfit: number
  aiScore: number
}

interface Props {
  order: OrderInfo
  onConfirm: () => void
  onCancel: () => void
}

export function OrderConfirmDialog({ order, onConfirm, onCancel }: Props) {
  const [step, setStep] = useState<"preview" | "confirm">("preview")
  const isSimulation = process.env.NEXT_PUBLIC_SIMULATION === "true"
  const actionLabel = order.action === "buy" ? "買進" : "賣出"

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#111118] border border-[#2a2a3a] rounded-xl p-6 w-80">

        {/* 環境徽章 */}
        <div className={`text-center text-xs font-bold py-1 rounded mb-4 ${
          isSimulation
            ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
            : "bg-red-500/20 text-red-400 border border-red-500/30"
        }`}>
          {isSimulation ? "🟡 模擬帳戶" : "🔴 真實帳戶"}
        </div>

        {step === "preview" && (
          <>
            <h3 className="text-white font-medium mb-4">{actionLabel} 確認</h3>
            <div className="space-y-2 text-sm mb-6">
              <Row label="股票" value={order.symbol} />
              <Row label="數量" value={`${order.quantity} 張`} />
              <Row label="市價" value={String(order.price)} />
              <Row label="停損" value={String(order.stopLoss)} valueClass="text-red-400" />
              <Row label="停利" value={String(order.takeProfit)} valueClass="text-green-400" />
              <Row label="AI 評分" value={`${order.aiScore} 分`} valueClass="text-blue-400" />
            </div>
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 py-2 border border-gray-600 rounded-lg text-gray-400"
              >
                取消
              </button>
              <button
                onClick={() => setStep("confirm")}
                className="flex-1 py-2 bg-purple-600 rounded-lg text-white font-medium"
              >
                預覽確認 →
              </button>
            </div>
          </>
        )}

        {step === "confirm" && (
          <>
            <h3 className="text-yellow-400 font-medium mb-4">⚠️ 最終確認</h3>
            <p className="text-gray-300 text-sm mb-6">
              確定以市價{actionLabel}{" "}
              <span className="text-white font-bold">{order.symbol}</span>{" "}
              <span className="text-white font-bold">{order.quantity} 張</span>？
              {!isSimulation && (
                <span className="text-red-400 block mt-2">
                  此為真實帳戶，操作不可撤銷。
                </span>
              )}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("preview")}
                className="flex-1 py-2 border border-gray-600 rounded-lg text-gray-400"
              >
                返回
              </button>
              <button
                onClick={onConfirm}
                className={`flex-1 py-2 rounded-lg text-white font-bold ${
                  isSimulation ? "bg-yellow-600" : "bg-red-600"
                }`}
              >
                {isSimulation ? "模擬下單" : "確認下單"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  valueClass = "text-white",
}: {
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  )
}
