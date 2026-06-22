"""
ReEntry 重複信號評估
evaluate(symbol, ai_confidence, positions) → "add" | "ignore" | "warn"

決策矩陣：
  無持倉               → add（全倉）
  有持倉 + 信心 >= 0.75 → add（半倉加碼）
  有持倉 + 信心 >= 0.55 → warn（推播警告，不下單）
  有持倉 + 信心 < 0.55  → ignore（僅記錄）
"""
from __future__ import annotations

_ADD_THRESHOLD  = 0.75
_WARN_THRESHOLD = 0.55


def evaluate(
    symbol: str,
    ai_confidence: float,
    positions: list[dict],
) -> str:
    current_qty = next(
        (int(p.get("quantity", 0)) for p in positions if p.get("symbol") == symbol),
        0,
    )

    if current_qty == 0:
        return "add"

    if ai_confidence >= _ADD_THRESHOLD:
        return "add"

    if ai_confidence >= _WARN_THRESHOLD:
        return "warn"

    return "ignore"
