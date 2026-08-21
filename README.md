# 中金所杯本地信号看板

手机端优先的本地网页。程序只生成交易信号，不自动下单；用户在东方财富期货 APP 中人工确认。

## Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

浏览器打开 `http://127.0.0.1:8501`。Cloud Studio 中使用同样的安装和启动命令，并将 8501 端口设为预览端口。

当前页面是信号框架，行情接入后才会生成实际开仓、止损和手数。不要把占位的“观望”当作交易建议。
