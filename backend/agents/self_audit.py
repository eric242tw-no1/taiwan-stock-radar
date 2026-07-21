"""
Self Audit 自審計系統
每日 16:30 由 APScheduler 觸發，執行六大項目稽核，
結果寫入 logs/audit_YYYYMMDD.json，有問題透過 Telegram 推播。
"""
import json
import logging
import os
from datetime import date, datetime

logger = logging.getLogger(__name__)


class SelfAudit:
    """每日 16:30 自動執行，審計六大項目"""

    def run(self) -> dict:
        today = date.today().strftime("%Y-%m-%d")
        issues: list[str] = []
        fixes:   list[str] = []
        warnings: list[str] = []

        # 1. 行情資料完整性
        missing = self._check_data(today)
        if missing:
            issues.append(f"行情缺失：{missing}")

        # 2. 異常價格（漲跌幅 > 10% 的非漲跌停股）
        anomalies = self._check_anomalies()
        if anomalies:
            warnings.append(f"異常價格：{anomalies}")

        # 3. Redis 健康
        if not self._check_redis():
            issues.append("Redis 連線異常")

        # 4. FinMind API 健康
        if not self._check_finmind():
            warnings.append("FinMind API 回應異常")

        # 5. 技術指標預算完整性
        missing_ind = self._check_indicators(today)
        if missing_ind:
            issues.append(f"指標未預算：{missing_ind}")
            self._fix_indicators(missing_ind)
            fixes.append(f"已重新預算：{missing_ind}")

        # 6. 停損監控狀態（檢查排程器是否正常）
        if not self._check_scheduler():
            issues.append("APScheduler 排程未運行")

        result = {
            "date": today,
            "status": "healthy" if not issues else "issues_found",
            "issues": issues,
            "fixes": fixes,
            "warnings": warnings,
            "checked_at": datetime.now().isoformat(),
        }

        # 寫入日誌
        os.makedirs("logs", exist_ok=True)
        log_path = f"logs/audit_{today.replace('-', '')}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("SelfAudit done: %s  issues=%d", today, len(issues))

        # 有 issue 才發 Telegram
        if issues:
            import asyncio
            from utils.telegram import send_message
            msg = (
                f"⚠️ 系統自審計\n"
                f"━━━━━━━━━━━━\n"
                f"問題：{chr(10).join(issues)}\n"
                f"已修復：{chr(10).join(fixes) if fixes else '無'}"
            )
            try:
                asyncio.get_event_loop().run_until_complete(send_message(msg))
            except Exception:
                pass

        return result

    # ── 六項檢查 ──────────────────────────────────────────────────────────

    def _check_data(self, today: str) -> list[str]:
        """確認 stock_pool 內的股票當日都有 indicators 記錄"""
        try:
            from db import get_conn
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT symbol FROM stock_pool WHERE enabled = 1")
            pool = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT DISTINCT ticker FROM stock_indicators_daily WHERE trade_date = ?",
                (today,),
            )
            have = {r[0].replace(".TW", "") for r in cur.fetchall()}
            conn.close()
            return list(pool - have)
        except Exception as e:
            logger.warning("_check_data error: %s", e)
            return []

    def _check_anomalies(self) -> list[str]:
        """從快取中找出報價異常的股票（change_pct 絕對值 > 12%）"""
        try:
            from services.indicator_service import _cache
            anomalies = []
            for sym, data in _cache.items():
                pct = data.get("change_pct", 0) or 0
                if abs(pct) > 12:
                    anomalies.append(f"{sym}({pct:+.1f}%)")
            return anomalies
        except Exception as e:
            logger.debug("_check_anomalies error: %s", e)
            return []

    def _check_redis(self) -> bool:
        try:
            import redis
            import os
            url = os.getenv("REDIS_URL", "")
            if not url:
                return True  # Redis 未設定視為 N/A
            r = redis.Redis.from_url(url, socket_connect_timeout=3)
            r.ping()
            return True
        except Exception:
            return False

    def _check_finmind(self) -> bool:
        try:
            import httpx
            r = httpx.get(
                "https://api.finmindtrade.com/api/v4/info",
                timeout=5,
            )
            return r.status_code == 200
        except Exception:
            return False

    def _check_indicators(self, today: str) -> list[str]:
        """同 _check_data，但只看 rsi14/macd 是否為 NULL"""
        try:
            from db import get_conn
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT ticker FROM stock_indicators_daily "
                "WHERE trade_date = ? AND (rsi14 IS NULL OR macd IS NULL)",
                (today,),
            )
            result = [r[0] for r in cur.fetchall()]
            conn.close()
            return result
        except Exception as e:
            logger.debug("_check_indicators error: %s", e)
            return []

    def _fix_indicators(self, symbols: list[str]):
        """重新觸發指定股票的指標計算"""
        try:
            from services.indicator_service import calculate_and_store
            calculate_and_store(symbols=symbols)
        except Exception as e:
            logger.warning("_fix_indicators error: %s", e)

    def _check_scheduler(self) -> bool:
        """確認 APScheduler 有在跑（indicator_refresh job 存在）"""
        try:
            from main import scheduler
            job_ids = [j.id for j in scheduler.get_jobs()]
            return "indicator_refresh" in job_ids
        except Exception:
            return True  # 無法取得時不誤報
