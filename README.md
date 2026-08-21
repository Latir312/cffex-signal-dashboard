# 中金所杯本地信号看板

手机端优先的本地网页。程序只生成交易信号，不自动下单；用户在东方财富期货 APP 中人工确认。

## Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

浏览器打开 `http://127.0.0.1:8501`。Cloud Studio 中使用同样的安装和启动命令，并将 8501 端口设为预览端口。

程序每 25 秒记录一次公开主连报价，并在本地聚合为 5 分钟采样K线，使用开盘前 30 分钟的区间与成交额基线生成“做多/做空/观望”提醒。请在比赛日 9:25 前启动，让本地日志完整；历史基线至少需要 5 个交易日。页面只提醒，不自动下单，最终以东方财富期货 APP 的实际合约、价格、保证金和比赛规则为准。
