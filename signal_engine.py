from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
import csv
import json
import threading

import requests

CONTRACTS = {
    "IF": {"name": "沪深300", "multiplier": 300, "margin_rate": 0.12, "market_code": "IFM"},
    "IC": {"name": "中证500", "multiplier": 200, "margin_rate": 0.14, "market_code": "ICM"},
    "IH": {"name": "上证50", "multiplier": 300, "margin_rate": 0.12, "market_code": "IHM"},
    "IM": {"name": "中证1000", "multiplier": 200, "margin_rate": 0.14, "market_code": "IMM"},
}

QUOTE_URL = "https://futsseapi.eastmoney.com/list/main/CFFEX"
DATA_DIR = Path("data") / "quote_log"
ACCOUNT_EQUITY = 1_000_000
MAX_MARGIN_PER_SIGNAL = 0.375
RISK_PER_TRADE = 0.02
STOP_LOSS_PCT = 0.01
REFRESH_SECONDS = 25

_lock = threading.Lock()
_quotes: dict[str, dict] = {}
_last_refresh: datetime | None = None
_last_error: str | None = None


def _is_market_time(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    current = now.time()
    return time(9, 30) <= current <= time(11, 30) or time(13, 0) <= current <= time(15, 0)


def _fetch_quotes() -> dict[str, dict]:
    response = requests.get(
        QUOTE_URL,
        params={
            "callbackName": "snapshot", "orderBy": "zdf", "sort": "desc",
            "pageSize": 100, "pageIndex": 0, "token": "1101ffec61617c99be287c1bec3085ff",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
        timeout=8,
    )
    response.raise_for_status()
    text = response.text.strip()
    payload = json.loads(text[text.index("(") + 1:text.rfind(")")] if "(" in text else text)
    by_market_code = {item["dm"]: item for item in payload.get("list", [])}
    return {code: by_market_code[info["market_code"]] for code, info in CONTRACTS.items() if info["market_code"] in by_market_code}


def _log_snapshot(now: datetime, quotes: dict[str, dict]) -> None:
    if not _is_market_time(now):
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{now:%Y-%m-%d}.csv"
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["timestamp", "code", "price", "turnover"])
        if new_file:
            writer.writeheader()
        for code, quote in quotes.items():
            price = quote.get("p")
            turnover = quote.get("cje")
            if price is not None and turnover is not None:
                writer.writerow({"timestamp": now.isoformat(timespec="seconds"), "code": code, "price": price, "turnover": turnover})


def refresh_market_data(force: bool = False) -> None:
    global _last_error, _last_refresh, _quotes
    now = datetime.now()
    with _lock:
        if not force and _last_refresh and (now - _last_refresh).total_seconds() < REFRESH_SECONDS:
            return
    try:
        quotes = _fetch_quotes()
        _log_snapshot(now, quotes)
        with _lock:
            _quotes = quotes
            _last_refresh = now
            _last_error = None
    except (requests.RequestException, ValueError, KeyError) as error:
        with _lock:
            _last_error = str(error)
            _last_refresh = now


def _read_day(day: str, code: str) -> list[dict]:
    path = DATA_DIR / f"{day}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [row for row in csv.DictReader(file) if row["code"] == code]


def _opening_stats(rows: list[dict]) -> tuple[float, float, float] | None:
    buckets: dict[datetime, dict] = {}
    for row in rows:
        stamp = datetime.fromisoformat(row["timestamp"])
        if time(9, 30) <= stamp.time() < time(10, 0):
            bucket = stamp.replace(minute=(stamp.minute // 5) * 5, second=0, microsecond=0)
            item = buckets.setdefault(bucket, {"high": float(row["price"]), "low": float(row["price"]), "first": float(row["turnover"]), "last": float(row["turnover"])})
            price = float(row["price"])
            item["high"] = max(item["high"], price)
            item["low"] = min(item["low"], price)
            item["last"] = float(row["turnover"])
    if len(buckets) < 6:
        return None
    bars = [buckets[key] for key in sorted(buckets)]
    turnover = bars[-1]["last"] - bars[0]["first"]
    return max(bar["high"] for bar in bars), min(bar["low"] for bar in bars), max(turnover, 0.0)


def _historical_open_turnovers(code: str, today: str) -> list[float]:
    if not DATA_DIR.exists():
        return []
    values = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        if path.stem >= today:
            continue
        stats = _opening_stats(_read_day(path.stem, code))
        if stats:
            values.append(stats[2])
    return values[-20:]


def _suggest_lots(info: dict, entry: float, stop: float) -> int:
    loss_per_lot = abs(entry - stop) * info["multiplier"]
    margin_per_lot = entry * info["multiplier"] * info["margin_rate"]
    if loss_per_lot <= 0 or margin_per_lot <= 0:
        return 0
    risk_limit = int(ACCOUNT_EQUITY * RISK_PER_TRADE / loss_per_lot)
    margin_limit = int(ACCOUNT_EQUITY * MAX_MARGIN_PER_SIGNAL / margin_per_lot)
    return max(0, min(risk_limit, margin_limit))


def _signal_for(code: str, info: dict, quote: dict | None, now: datetime) -> dict:
    row = {
        "code": code, "name": info["name"], "direction": "观望", "suggested_lots": 0,
        "entry": None, "stop": None, "status": "行情连接暂不可用",
        "last_price": quote.get("p") if quote else None,
        "open": quote.get("o") if quote else None,
        "high": quote.get("h") if quote else None,
        "low": quote.get("l") if quote else None,
        "change_pct": quote.get("zdf") if quote else None,
    }
    if not quote:
        return row
    if not _is_market_time(now):
        row["status"] = "非交易时段，信号关闭"
        return row
    if now.time() < time(10, 0):
        row["status"] = "正在采集开盘 30 分钟区间"
        return row
    if now.time() >= time(14, 45):
        row["status"] = "仅平仓时段，不开新仓"
        return row
    stats = _opening_stats(_read_day(now.strftime("%Y-%m-%d"), code))
    if not stats:
        row["status"] = "缺少完整开盘采样，请于 9:25 前启动"
        return row
    range_high, range_low, opening_turnover = stats
    historical = _historical_open_turnovers(code, now.strftime("%Y-%m-%d"))
    if len(historical) < 5:
        row["status"] = f"已形成开盘区间，建立成交额基线中（{len(historical)}/5）"
        return row
    active = opening_turnover >= sum(historical) / len(historical) * 1.1 and range_high / range_low - 1 >= 0.002
    if not active:
        row["status"] = "开盘不活跃，观望"
        return row
    price = float(quote["p"])
    if price > range_high:
        stop = range_high * (1 - STOP_LOSS_PCT)
        row.update(direction="做多", entry=price, stop=stop, suggested_lots=_suggest_lots(info, price, stop), status="开盘活跃向上突破，需人工确认")
    elif price < range_low:
        stop = range_low * (1 + STOP_LOSS_PCT)
        row.update(direction="做空", entry=price, stop=stop, suggested_lots=_suggest_lots(info, price, stop), status="开盘活跃向下突破，需人工确认")
    else:
        row["status"] = "开盘活跃，等待突破"
    return row


def build_snapshot() -> dict:
    refresh_market_data()
    now = datetime.now()
    with _lock:
        quotes = _quotes.copy()
        quote_error = _last_error
    return {
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "signal-only / local sampling",
        "account": {"futures_equity": ACCOUNT_EQUITY, "margin_cap": 0.75, "risk_per_trade": RISK_PER_TRADE},
        "rules": {"last_entry": "14:45", "flat_time": "14:55", "t_plus_0": True},
        "contracts": [_signal_for(code, info, quotes.get(code), now) for code, info in CONTRACTS.items()],
        "notice": "本地每 25 秒采样公开报价并聚合为 5 分钟K线。请在比赛日 9:25 前启动，且以东方财富期货 APP 的实际合约、价格和保证金为最终依据。" if not quote_error else "公开行情源暂不可用；请以东方财富期货 APP 行情为准。",
    }
