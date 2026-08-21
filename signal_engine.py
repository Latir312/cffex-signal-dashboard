from datetime import datetime
import json

import requests

CONTRACTS = {
    "IF": {"name": "沪深300", "multiplier": 300, "market_code": "IFM"},
    "IC": {"name": "中证500", "multiplier": 200, "market_code": "ICM"},
    "IH": {"name": "上证50", "multiplier": 300, "market_code": "IHM"},
    "IM": {"name": "中证1000", "multiplier": 200, "market_code": "IMM"},
}

QUOTE_URL = "https://futsseapi.eastmoney.com/list/main/CFFEX"


def _load_quotes():
    """Load public CFFEX continuous-contract quotes without accessing an account."""
    response = requests.get(
        QUOTE_URL,
        params={
            "callbackName": "snapshot",
            "orderBy": "zdf",
            "sort": "desc",
            "pageSize": 100,
            "pageIndex": 0,
            "token": "1101ffec61617c99be287c1bec3085ff",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
        timeout=8,
    )
    response.raise_for_status()
    text = response.text.strip()
    if "(" in text:
        text = text[text.index("(") + 1:text.rfind(")")]
    payload = json.loads(text)
    return {item["dm"]: item for item in payload.get("list", [])}


def build_snapshot():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        quotes = _load_quotes()
        quote_error = None
    except (requests.RequestException, ValueError, KeyError) as error:
        quotes = {}
        quote_error = str(error)

    rows = []
    for code, info in CONTRACTS.items():
        quote = quotes.get(info["market_code"])
        rows.append({
            "code": code,
            "name": info["name"],
            "status": "行情已接入，等待 5 分钟K线" if quote else "行情连接暂不可用",
            "direction": "观望",
            "suggested_lots": 0,
            "last_price": quote.get("p") if quote else None,
            "open": quote.get("o") if quote else None,
            "high": quote.get("h") if quote else None,
            "low": quote.get("l") if quote else None,
            "change_pct": quote.get("zdf") if quote else None,
            "turnover": quote.get("cje") if quote else None,
            "updated_at": now,
        })
    return {
        "updated_at": now,
        "mode": "signal-only / public quote",
        "account": {"futures_equity": 1000000, "margin_cap": 0.75, "risk_per_trade": 0.02},
        "rules": {"last_entry": "14:45", "flat_time": "14:55", "t_plus_0": True},
        "contracts": rows,
        "notice": "报价来自公开行情源，仅作辅助核对。尚未接入可靠的 5 分钟K线，不生成开仓、止损或手数信号。" if not quote_error else "公开行情源暂不可用；请以东方财富期货 APP 行情为准。",
    }
