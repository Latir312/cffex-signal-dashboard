from datetime import datetime
from flask import Flask, jsonify, render_template

from signal_engine import build_snapshot

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/snapshot")
def snapshot():
    return jsonify(build_snapshot())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False)
