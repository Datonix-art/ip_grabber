import os
import sqlite3
import threading
from datetime import datetime, timezone
from functools import wraps

import requests
from flask import Flask, request, render_template, Response, g
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
DB_PATH = "visits.db"

# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")


# ---------- Database ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                user_agent TEXT,
                path TEXT,
                timestamp TEXT
            )
        """)


# ---------- Discord ----------
def _send_to_discord(payload):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except requests.RequestException:
        pass  # a Discord outage shouldn't break the site

def get_client_ip():
    # Render sits behind Cloudflare, which sets these headers
    for header in ("CF-Connecting-IP", "True-Client-IP"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    # Fallback: the first address in X-Forwarded-For is the original client
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr

def notify_discord(ip, user_agent, path):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {
        "embeds": [{
            "title": "New visit",
            "color": 5814783,
            "fields": [
                {"name": "IP", "value": ip or "unknown", "inline": True},
                {"name": "Path", "value": path, "inline": True},
                {"name": "User-Agent", "value": (user_agent or "unknown")[:1000]},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }
    threading.Thread(target=_send_to_discord, args=(payload,), daemon=True).start()


# ---------- Auth ----------
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return Response("Login required", 401,
                            {"WWW-Authenticate": 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return wrapper


# ---------- Routes ----------
@app.route("/")
def index():
    ip = get_client_ip()
    ua = request.headers.get("User-Agent", "")[:300]
    db = get_db()
    db.execute(
        "INSERT INTO visits (ip, user_agent, path, timestamp) VALUES (?, ?, ?, ?)",
        (ip, ua, request.path, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    notify_discord(ip, ua, request.path)
    return render_template("index.html")


@app.route("/admin/logs")
@require_auth
def logs():
    rows = get_db().execute(
        "SELECT * FROM visits ORDER BY id DESC LIMIT 200"
    ).fetchall()
    return render_template("logs.html", rows=rows)

@app.route("/admin/headers")
@require_auth
def headers_debug():
    return "<pre>" + "\n".join(f"{k}: {v}" for k, v in request.headers) + "</pre>"

init_db()  # runs at import time so it also works under gunicorn

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)