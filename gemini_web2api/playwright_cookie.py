"""Playwright-based cookie extraction with embedded browser."""
import os
import json
import time
import threading

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

_PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".gemini-web2api", "browser-profile")
_REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"]
_browser_lock = threading.Lock()


def is_playwright_available() -> bool:
    return HAS_PLAYWRIGHT


def _extract_cookies_from_context(context, domain: str = "gemini.google.com") -> tuple:
    cookies = context.cookies(f"https://{domain}")
    cookie_map = {}
    for c in cookies:
        if domain in c.get("domain", "") or "google.com" in c.get("domain", ""):
            cookie_map[c["name"]] = c["value"]

    present = [k for k in _REQUIRED_COOKIES if k in cookie_map]
    if len(present) < 3:
        return None, None

    cookie_str = "; ".join(
        f"{k}={v}" for k, v in cookie_map.items()
        if k in _REQUIRED_COOKIES or k.startswith("__Secure-")
    )
    sapisid = cookie_map.get("SAPISID", "")
    return cookie_str, sapisid


def launch_browser_login(port: int = 8081) -> dict:
    if not HAS_PLAYWRIGHT:
        return {"success": False, "error": "playwright not installed. Run: pip install playwright && playwright install msedge"}

    os.makedirs(_PROFILE_DIR, exist_ok=True)

    with _browser_lock:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    channel="msedge",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                )
                page = context.new_page()
                page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")

                max_wait = 300
                start = time.time()
                while time.time() - start < max_wait:
                    cookies = context.cookies("https://gemini.google.com")
                    cookie_names = {c["name"] for c in cookies}
                    has_sid = "SID" in cookie_names or "__Secure-1PSID" in cookie_names
                    has_apisid = "APISID" in cookie_names or "SAPISID" in cookie_names
                    if has_sid and has_apisid:
                        break
                    time.sleep(2)

                cookie_str, sapisid = _extract_cookies_from_context(context)
                context.close()
                browser.close()

                if cookie_str:
                    return {"success": True, "cookies": cookie_str, "sapisid": sapisid}
                return {"success": False, "error": "Login timeout or no valid cookies found"}

        except Exception as e:
            return {"success": False, "error": str(e)}


def refresh_cookie_via_playwright() -> tuple:
    if not HAS_PLAYWRIGHT:
        return None, None

    os.makedirs(_PROFILE_DIR, exist_ok=True)

    with _browser_lock:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    channel="msedge",
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                )
                page = context.new_page()
                page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
                time.sleep(5)

                cookie_str, sapisid = _extract_cookies_from_context(context)
                context.close()
                browser.close()
                return cookie_str, sapisid

        except Exception:
            return None, None
