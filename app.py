import threading
import time

from flask import Flask, jsonify, render_template

from signal_engine import build_snapshot, refresh_market_data, REFRESH_SECONDS

app = Flask(__name__)


def _collector() -> None:
    while True:
        refresh_market_data(force=True)
        time.sleep(REFRESH_SECONDS)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/snapshot")
def snapshot():
    return jsonify(build_snapshot())


if __name__ == "__main__":
    threading.Thread(target=_collector, daemon=True, name="quote-collector").start()
    app.run(host="0.0.0.0", port=8501, debug=False)
