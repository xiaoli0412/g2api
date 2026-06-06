"""Cookie extraction and auto-refresh scheduler.

Supports: Chrome, Edge, and any Chromium browser.
Methods: Direct DB read, CDP, browser_cookie3, Playwright, Extension push.
"""
import json
import os
import sys
import time
import sqlite3
import threading
from .config import CONFIG
from .stats import add_log

_cookie_refresh_timer = None
_cookie_status = {
    "last_refresh": None,
    "last_refresh_str": "Never",
    "next_refresh": None,
    "next_refresh_str": "N/A",
    "refresh_interval_hours": 12,
    "auto_refresh_enabled": False,
    "source_browser": "auto",
    "status": "idle",
    "error": None,
    "cookie_valid": False,
}

_BROWSER_PATHS = {
    "edge": {
        "db": [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 1\Network\Cookies"),
        ],
        "state": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Local State"),
    },
    "chrome": {
        "db": [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Profile 1\Network\Cookies"),
        ],
        "state": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State"),
    },
}

_REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"]


def _decrypt_value(data: bytes, browser: str = "edge") -> str:
    if not data:
        return ""
    if sys.platform != "win32":
        return data.decode("utf-8", errors="replace")
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1].decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        state_path = _BROWSER_PATHS.get(browser, _BROWSER_PATHS["edge"])["state"]
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            key_b64 = state.get("os_crypt", {}).get("encrypted_key", "")
            if key_b64:
                import win32crypt
                raw_key = base64.b64decode(key_b64)[5:]
                key = win32crypt.CryptUnprotectData(raw_key, None, None, None, 0)[1]
                if data[:3] in (b"v10", b"v20"):
                    return AESGCM(key).decrypt(data[3:15], data[15:], None).decode("utf-8", errors="replace")
    except Exception:
        pass
    return data.decode("utf-8", errors="replace")


def _read_cookies(conn: sqlite3.Connection, domain: str, browser: str = "edge") -> tuple:
    cur = conn.cursor()
    try:
        cur.execute("SELECT name, encrypted_value, host_key FROM cookies WHERE host_key LIKE ? OR host_key LIKE ?",
                    (f"%{domain}%", "%.google.com%"))
    except sqlite3.OperationalError:
        cur.execute("SELECT name, value, host_key FROM cookies WHERE host_key LIKE ? OR host_key LIKE ?",
                    (f"%{domain}%", "%.google.com%"))

    cookies = {}
    for name, value, host in cur.fetchall():
        if isinstance(value, bytes) and value:
            v = _decrypt_value(value, browser)
        else:
            v = str(value) if value else ""
        if v:
            cookies[name] = v

    found = [k for k in _REQUIRED_COOKIES if k in cookies]
    if len(found) < 3:
        return None, None

    cookie_str = "; ".join(f"{k}={cookies[k]}" for k in _REQUIRED_COOKIES if k in cookies)
    extra = "; ".join(f"{k}={v}" for k, v in cookies.items() if k.startswith("__Secure-") and k not in _REQUIRED_COOKIES)
    if extra:
        cookie_str += "; " + extra
    return cookie_str, cookies.get("SAPISID", "")


def _extract_from_db(browser: str, domain: str = "gemini.google.com") -> tuple:
    paths = _BROWSER_PATHS.get(browser, {}).get("db", [])
    for p in paths:
        if os.path.exists(p):
            try:
                conn = sqlite3.connect(p)
                result = _read_cookies(conn, domain, browser)
                conn.close()
                if result[0]:
                    add_log(f"[{browser}] Extracted cookies from database", "info")
                return result
            except Exception as e:
                add_log(f"[{browser}] DB locked ({browser.title()} running?): {e}", "warning")
                return None, None
    return None, None


def _extract_via_cdp(domain: str, port: int = 9222) -> tuple:
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3)
        version = json.loads(resp.read())
        ws_url = version.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return None, None
    except Exception:
        return None, None

    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        result = json.loads(ws.recv())
        ws.close()

        cookies = {}
        for c in result.get("result", {}).get("cookies", []):
            if domain in c.get("domain", "") or "google.com" in c.get("domain", ""):
                cookies[c["name"]] = c["value"]

        found = [k for k in _REQUIRED_COOKIES if k in cookies]
        if len(found) < 3:
            return None, None

        cookie_str = "; ".join(f"{k}={cookies[k]}" for k in _REQUIRED_COOKIES if k in cookies)
        add_log(f"[cdp] Extracted {len(cookies)} cookies via CDP", "info")
        return cookie_str, cookies.get("SAPISID", "")
    except ImportError:
        add_log("[cdp] websocket-client not installed", "warning")
        return None, None
    except Exception as e:
        add_log(f"[cdp] Failed: {e}", "error")
        return None, None


def _extract_via_browser_cookie3(domain: str) -> tuple:
    try:
        import browser_cookie3
    except ImportError:
        return None, None

    for func_name in ["edge", "chrome"]:
        try:
            func = getattr(browser_cookie3, func_name)
            cj = func(domain_name=domain)
            cookies = {}
            for c in cj:
                if domain in c.domain or "google.com" in c.domain:
                    cookies[c.name] = c.value
            found = [k for k in _REQUIRED_COOKIES if k in cookies]
            if len(found) >= 3:
                cookie_str = "; ".join(f"{k}={cookies[k]}" for k in _REQUIRED_COOKIES if k in cookies)
                add_log(f"[browser_cookie3:{func_name}] Extracted {len(cookies)} cookies", "info")
                return cookie_str, cookies.get("SAPISID", "")
        except Exception:
            continue
    return None, None


def extract_cookies(domain: str = "gemini.google.com") -> tuple:
    """Extract cookies from any available browser. Returns (cookie_str, sapisid) or (None, None)."""
    source = CONFIG.get("cookie_source", "auto")

    if source == "playwright":
        from . import playwright_cookie
        add_log("Using Playwright for cookie extraction...", "info")
        result = playwright_cookie.refresh_cookie_via_playwright()
        if result[0]:
            return result
        return None, None

    for browser in ["edge", "chrome"]:
        result = _extract_from_db(browser, domain)
        if result[0]:
            return result

    add_log("Trying CDP fallback...", "info")
    result = _extract_via_cdp(domain)
    if result[0]:
        return result

    add_log("Trying browser_cookie3 fallback...", "info")
    result = _extract_via_browser_cookie3(domain)
    if result[0]:
        return result

    from . import playwright_cookie
    if playwright_cookie.is_playwright_available():
        add_log("Trying Playwright fallback...", "info")
        result = playwright_cookie.refresh_cookie_via_playwright()
        if result[0]:
            return result

    return None, None


extract_edge_cookies = extract_cookies


def write_cookie_file(cookie_str: str, sapisid: str, path: str = None):
    if path is None:
        path = CONFIG.get("cookie_file")
    if not path:
        path = "cookie.txt"
    content = json.dumps({"cookie": cookie_str, "sapisid": sapisid}, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    add_log(f"Cookie file updated: {path}", "info")


def refresh_cookie() -> bool:
    _cookie_status["status"] = "refreshing"
    _cookie_status["error"] = None
    try:
        cookie_str, sapisid = extract_cookies()
        if not cookie_str:
            _cookie_status["status"] = "error"
            _cookie_status["error"] = "Failed to extract cookies from any browser"
            return False

        write_cookie_file(cookie_str, sapisid)
        from . import gemini
        gemini._cookie_cache.update({"str": "", "sapisid": None, "mtime": 0})

        now = time.time()
        _cookie_status["last_refresh"] = now
        _cookie_status["last_refresh_str"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        _cookie_status["cookie_valid"] = True
        _cookie_status["status"] = "ok"
        _cookie_status["error"] = None
        add_log("Cookie auto-refresh completed successfully", "info")
        return True
    except Exception as e:
        _cookie_status["status"] = "error"
        _cookie_status["error"] = str(e)
        add_log(f"Cookie auto-refresh failed: {e}", "error")
        return False


def _refresh_loop():
    interval = _cookie_status["refresh_interval_hours"] * 3600
    while _cookie_status["auto_refresh_enabled"]:
        next_time = time.time() + interval
        _cookie_status["next_refresh"] = next_time
        _cookie_status["next_refresh_str"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))
        time.sleep(interval)
        if not _cookie_status["auto_refresh_enabled"]:
            break
        refresh_cookie()


def start_auto_refresh(interval_hours: int = 12):
    global _cookie_refresh_timer
    _cookie_status["auto_refresh_enabled"] = True
    _cookie_status["refresh_interval_hours"] = interval_hours
    refresh_cookie()
    _cookie_refresh_timer = threading.Thread(target=_refresh_loop, daemon=True)
    _cookie_refresh_timer.start()
    add_log(f"Cookie auto-refresh started (every {interval_hours}h)", "info")


def stop_auto_refresh():
    _cookie_status["auto_refresh_enabled"] = False
    add_log("Cookie auto-refresh stopped", "info")


def get_cookie_status() -> dict:
    return dict(_cookie_status)


def manual_refresh() -> dict:
    success = refresh_cookie()
    return {
        "success": success,
        "status": _cookie_status["status"],
        "error": _cookie_status.get("error"),
        "last_refresh": _cookie_status["last_refresh_str"],
    }
