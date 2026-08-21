from datetime import datetime

CONTRACTS = {
    "IF": {"name": "沪深300", "multiplier": 300},
    "IC": {"name": "中证500", "multiplier": 200},
    "IH": {"name": "上证50", "multiplier": 300},
    "IM": {"name": "中证1000", "multiplier": 200},
}


def build_snapshot():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for code, info in CONTRACTS.items():
        rows.append({
            "code": code,
            "name": info["name"],
            "status": "等待行情接入",
            "direction": "观望",
            "suggested_lots": 0,
            "entry": None,
            "stop": None,
            "updated_at": now,
        })
    return {
        "updated_at": now,
        "mode": "signal-only",
        "account": {"futures_equity": 1000000, "margin_cap": 0.75, "risk_per_trade": 0.02},
        "rules": {"last_entry": "14:45", "flat_time": "14:55", "t_plus_0": True},
        "contracts": rows,
        "notice": "当前为信号框架；接入实时行情后才会生成开仓、止损和手数提示。",
    }
