"""
Sprint 1-6 回測基準線報告
執行：cd backend && python baseline_backtest.py
"""
import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from backtest.engine import fetch_backtest_data, run_backtest

STOCKS = [
    ("2330", "台積電"),
    ("2317", "鴻海"),
    ("2454", "聯發科"),
    ("0050", "台灣50 ETF"),
    ("2412", "中華電"),
]

STRATEGIES = ["wave", "momentum", "ma_cross", "rsi"]
START = "2023-01-01"
END   = "2025-12-31"


async def run_all():
    results = []
    for symbol, name in STOCKS:
        print(f"  抓取 {symbol} {name} 資料...", flush=True)
        try:
            df = await fetch_backtest_data(symbol, START, END)
            print(f"    {len(df)} 筆交易日", flush=True)
        except Exception as e:
            print(f"    [FAIL] 資料取得失敗：{e}", flush=True)
            continue

        for strategy in STRATEGIES:
            try:
                res = run_backtest(df, strategy, params={})
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "strategy": strategy,
                    "trades": res["total_trades"],
                    "win_rate": res["win_rate"],
                    "total_return": res["total_return"],
                    "sharpe": res["sharpe_ratio"],
                    "max_dd": res["max_drawdown"],
                })
                print(f"    [OK] {strategy:12s} | 交易:{res['total_trades']:3d} | 勝率:{res['win_rate']:5.1f}% | 報酬:{res['total_return']:+6.2f}% | Sharpe:{str(res['sharpe_ratio']):>6}", flush=True)
            except Exception as e:
                print(f"    [FAIL] {strategy} 失敗：{e}", flush=True)

    return results


def print_summary(results):
    if not results:
        print("\n[FAIL] 無結果可顯示")
        return

    print("\n" + "=" * 75)
    print("  BASELINE 回測報告")
    print(f"  期間：{START} ~ {END}  |  生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 75)
    print(f"  {'股票':<10} {'策略':<14} {'交易數':>6} {'勝率':>7} {'總報酬':>8} {'Sharpe':>7} {'最大DD':>8}")
    print("-" * 75)

    # 依策略分組算平均勝率
    from collections import defaultdict
    by_strategy = defaultdict(list)

    for r in results:
        label = f"{r['symbol']} {r['name']}"
        print(f"  {label:<10} {r['strategy']:<14} {r['trades']:>6} {r['win_rate']:>6.1f}% {r['total_return']:>+7.2f}% {str(r['sharpe'] or 'N/A'):>7} {r['max_dd']:>7.1f}%")
        by_strategy[r['strategy']].append(r)

    print("=" * 75)
    print("  策略平均（所有股票）")
    print("-" * 75)
    for strat, rows in sorted(by_strategy.items()):
        n = len(rows)
        avg_wr  = sum(r["win_rate"] for r in rows) / n
        avg_ret = sum(r["total_return"] for r in rows) / n
        avg_dd  = sum(r["max_dd"] for r in rows) / n
        valid_sharpe = [r["sharpe"] for r in rows if r["sharpe"] is not None]
        avg_sharpe = sum(valid_sharpe) / len(valid_sharpe) if valid_sharpe else None
        print(f"  {strat:<24} 平均勝率:{avg_wr:5.1f}% | 平均報酬:{avg_ret:+6.2f}% | 平均Sharpe:{str(round(avg_sharpe,3) if avg_sharpe else 'N/A'):>6} | 平均MaxDD:{avg_dd:5.1f}%")

    print("=" * 75)

    # 目標達成判斷
    all_win_rates = [r["win_rate"] for r in results if r["trades"] >= 5]
    overall_avg_wr = sum(all_win_rates) / len(all_win_rates) if all_win_rates else 0
    print(f"\n  整體平均勝率：{overall_avg_wr:.1f}%  (目標：55–62%)")
    if overall_avg_wr >= 55:
        print("  [OK] 達標 — 現有策略已達勝率目標")
    elif overall_avg_wr >= 45:
        print("  [WARN]  接近但未達標 — Change A Factor Engine 有提升空間")
    else:
        print("  [FAIL] 未達標 — 需要 Change A 提升訊號品質")

    # 寫入報告檔案
    report_path = os.path.join(os.path.dirname(__file__), "..", "docs", "baseline_backtest_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Sprint 1-6 回測基準線報告\n\n")
        f.write(f"> 期間：{START} ~ {END}  \n> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**整體平均勝率：{overall_avg_wr:.1f}%**（目標：55–62%）\n\n")
        f.write("| 股票 | 策略 | 交易數 | 勝率 | 總報酬 | Sharpe | 最大DD |\n")
        f.write("|------|------|--------|------|--------|--------|--------|\n")
        for r in results:
            f.write(f"| {r['symbol']} {r['name']} | {r['strategy']} | {r['trades']} | {r['win_rate']:.1f}% | {r['total_return']:+.2f}% | {r['sharpe'] or 'N/A'} | {r['max_dd']:.1f}% |\n")
        f.write("\n## 策略平均\n\n")
        for strat, rows in sorted(by_strategy.items()):
            n = len(rows)
            avg_wr  = sum(r["win_rate"] for r in rows) / n
            avg_ret = sum(r["total_return"] for r in rows) / n
            f.write(f"- **{strat}**：平均勝率 {avg_wr:.1f}%，平均報酬 {avg_ret:+.2f}%\n")
    print("\n  [REPORT] 報告已寫入：docs/baseline_backtest_report.md")


if __name__ == "__main__":
    print(f"[START] 基準線回測：{START} ~ {END}")
    print(f"   股票：{[s[0] for s in STOCKS]}")
    print(f"   策略：{STRATEGIES}\n")
    results = asyncio.run(run_all())
    print_summary(results)
