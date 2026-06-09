"""
八大官股動向抓取
資料來源：FinMind TaiwanStockGovernmentBankBuySell
若 FinMind 無此資料集，fallback 以主要官股股票（2885/2886/2891/2801/2880/2882/2884/2892）
的自營商買賣超估算

八大官股定義（市場穩定基金相關機構）：
  台灣銀行 / 合庫金控 / 兆豐金控 / 第一金控
  華南金控 / 彰化銀行 / 土地銀行 / 郵政儲金
"""
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

_lock = threading.Lock()
_cache: dict[str, Any] = {"gov": None, "updated_at": None}

# 追蹤的官股代號（自營商數據為proxy）
GOV_STOCKS = {
    "2885": "元大金",
    "2886": "兆豐金",
    "2880": "華南金",
    "2884": "玉山金",
    "2882": "國泰金",
    "2892": "第一金",
    "2881": "富邦金",
    "2801": "彰化銀",
}


def _get_token() -> str:
    token = os.environ.get("FINMIND_TOKEN", "")
    if not token or token == "placeholder":
        raise ValueError("FINMIND_TOKEN not configured")
    return token


def _fetch_gov_bank_finmind(start_date: str, client: httpx.Client) -> list[dict] | None:
    """
    Try FinMind TaiwanStockGovernmentBankBuySell dataset.
    Returns None if dataset unavailable.
    """
    try:
        resp = client.get(
            FINMIND_URL,
            params={
                "dataset":    "TaiwanStockGovernmentBankBuySell",
                "start_date": start_date,
                "token":      _get_token(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 200:
            return None
        rows = data.get("data", [])
        return rows if rows else None
    except Exception:
        return None


def _fetch_via_institutional(start_date: str, client: httpx.Client) -> list[dict]:
    """
    Fallback：抓官股股票本身的三大法人數據（dealer 方向作 proxy）
    """
    rows = []
    for sid, name in GOV_STOCKS.items():
        try:
            resp = client.get(
                FINMIND_URL,
                params={
                    "dataset":    "TaiwanStockInstitutionalInvestorsBuySell",
                    "data_id":    sid,
                    "start_date": start_date,
                    "token":      _get_token(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == 200:
                for r in data.get("data", []):
                    r["_name"] = name
                    r["_sid"] = sid
                    rows.append(r)
        except Exception as e:
            logger.warning("gov fund fetch [%s]: %s", sid, e)
    return rows


def fetch_gov_funds() -> dict:
    """
    Returns:
      items: [{name, net_bn (億), direction, net_raw}]
      total_bn: float
      consecutive_buy: int  (連續買超天數，估算)
      date: str
    """
    try:
        _get_token()
    except ValueError:
        return _empty_gov()

    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    with httpx.Client() as client:
        # 先嘗試直接 dataset
        gov_rows = _fetch_gov_bank_finmind(start_date, client)

        if gov_rows:
            # TaiwanStockGovernmentBankBuySell 欄位: date, bank_name, buy, sell, net
            latest_date = max(r["date"] for r in gov_rows)
            items = []
            total = 0
            for r in gov_rows:
                if r["date"] != latest_date:
                    continue
                net = int(r.get("net", 0)) if "net" in r else (int(r.get("buy", 0)) - int(r.get("sell", 0)))
                net_bn = round(net / 1e8, 1)
                items.append({
                    "name":      r.get("bank_name", r.get("name", "?")),
                    "net_bn":    net_bn,
                    "direction": "買超" if net >= 0 else "賣超",
                    "net_raw":   net,
                })
                total += net
            items.sort(key=lambda x: -abs(x["net_raw"]))
            result = {
                "items":            items[:8],
                "total_bn":         round(total / 1e8, 1),
                "date":             latest_date,
                "source":           "finmind_gov",
            }
        else:
            # Fallback：用官股個股自營商數據
            rows = _fetch_via_institutional(start_date, client)
            if not rows:
                return _empty_gov()

            latest_date = max(r["date"] for r in rows)
            # 每股彙總自營商 net
            per_stock: dict[str, dict] = {}
            for r in rows:
                if r["date"] != latest_date:
                    continue
                if r.get("name") not in ("Dealer_self", "Dealer_Hedging"):
                    continue
                sid  = r["_sid"]
                name = r["_name"]
                net  = int(r["buy"]) - int(r["sell"])
                if sid not in per_stock:
                    per_stock[sid] = {"name": name, "net": 0}
                per_stock[sid]["net"] += net

            items = []
            total = 0
            for sid, d in per_stock.items():
                net    = d["net"]
                net_bn = round(net / 1e4, 1)   # 自營商張數除以1萬估算億元
                items.append({
                    "name":      d["name"],
                    "net_bn":    net_bn,
                    "direction": "買超" if net >= 0 else "賣超",
                    "net_raw":   net,
                })
                total += net

            items.sort(key=lambda x: -abs(x["net_raw"]))
            result = {
                "items":    items[:8],
                "total_bn": round(total / 1e4, 1),
                "date":     latest_date,
                "source":   "dealer_proxy",
            }

    with _lock:
        _cache["gov"] = result
        _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    return result


def get_cached_gov_funds() -> dict:
    with _lock:
        data = _cache.get("gov")
    if data is not None:
        return data
    return fetch_gov_funds()


def _empty_gov() -> dict:
    return {"items": [], "total_bn": 0, "date": "", "source": "unavailable"}
