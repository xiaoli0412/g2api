"""Cookie and proxy rotation management."""
import os
import time
import json
import threading
from .config import CONFIG
from .gemini import load_cookie, log
from .cookies import diagnose_cookie_header, normalize_cookie_input

_lock = threading.Lock()
_cookie_index = 0
_proxy_index = 0
_request_count = 0
_last_rotation = 0
_auto_refresh_enabled = False
_auto_refresh_interval = 12
_auto_refresh_thread = None
_cookie_file = "cookie.txt"
_last_push_time = 0
_last_push_status = "idle"
_last_refresh_source = ""
_last_refresh_diagnostics = None
_source_states = {
    "manual_import": {"status": "idle"},
    "edge_extension": {"status": "idle"},
    "internal_browser": {"status": "idle"},
}


def _cookie_score(cookie_str: str) -> int:
    diag = diagnose_cookie_header(cookie_str or "")
    score = diag.get("cookie_count", 0)
    if diag.get("api_streamgenerate_ready"):
        score += 100
    if diag.get("web_ui_likely_complete"):
        score += 1000
    return score


def _extract_installed_browser_cookies() -> tuple:
    """Extract Gemini/Google cookies from installed browsers only.

    Returns (cookie_str, sapisid, source). Cookie values are never logged.
    """
    try:
        import browser_cookie3
    except Exception as e:
        log(f"browser-cookie3 unavailable: {e}")
        return "", None, ""

    browsers = [
        ("Edge", getattr(browser_cookie3, "edge", None)),
        ("Chrome", getattr(browser_cookie3, "chrome", None)),
        ("Firefox", getattr(browser_cookie3, "firefox", None)),
    ]
    for browser_name, loader in browsers:
        if loader is None:
            continue
        try:
            jar = loader(domain_name=".google.com")
            pairs = []
            sapisid_value = None
            for cookie in jar:
                domain = (cookie.domain or "").lower()
                if not (domain == ".google.com" or domain.endswith(".google.com") or domain == "gemini.google.com"):
                    continue
                pairs.append(f"{cookie.name}={cookie.value}")
                if cookie.name == "SAPISID":
                    sapisid_value = cookie.value
            if pairs:
                cookie_str, parsed_sapisid = normalize_cookie_input("; ".join(pairs))
                log(
                    "Extracted Gemini/Google cookies from "
                    f"{browser_name} ({len(cookie_str.split('; ')) if cookie_str else 0} cookies)"
                )
                return cookie_str, sapisid_value or parsed_sapisid, browser_name
        except Exception as e:
            log(f"{browser_name} cookie extraction failed: {e}")

    return "", None, ""


def _refresh_from_local_sources(require_web_ui: bool = False) -> tuple:
    """Try local browser sources and return the best cookie candidate.

    Returns (cookie_str, sapisid, source), or ("", None, "") if no useful candidate exists.
    """
    candidates = []
    cookie_str, sapisid, source = _extract_installed_browser_cookies()
    if cookie_str:
        candidates.append((cookie_str, sapisid, f"installed-browser:{source}"))

    try:
        from .playwright_cookie import refresh_cookie_via_playwright
        cookie_str, sapisid = refresh_cookie_via_playwright()
        if cookie_str:
            candidates.append((cookie_str, sapisid, "internal-browser-profile"))
    except Exception as e:
        log(f"Playwright cookie refresh unavailable: {e}")

    if not candidates:
        return "", None, ""

    candidates.sort(key=lambda item: _cookie_score(item[0]), reverse=True)
    best_cookie, best_sapisid, best_source = candidates[0]
    best_diag = diagnose_cookie_header(best_cookie)
    if not best_diag.get("api_streamgenerate_ready"):
        return "", None, ""
    if require_web_ui and not best_diag.get("web_ui_likely_complete"):
        return "", None, ""
    return best_cookie, best_sapisid, best_source


def _save_cookie_candidate(cookie_str: str, sapisid: str = "", source: str = "refresh") -> bool:
    target = CONFIG.get("cookie_file") or _cookie_file
    ok = write_cookie_file(cookie_str, sapisid, target)
    if ok:
        try:
            from .admin import add_cookie
            add_cookie(cookie_str, sapisid, source=source)
        except Exception:
            pass
    return ok


def _source_key(source: str) -> str:
    source = (source or "").strip().lower().replace(" ", "-")
    if "edge" in source or "extension" in source:
        return "edge_extension"
    if "internal" in source or "browser-login" in source or "browser" in source:
        return "internal_browser"
    return "manual_import"


def _status_for_diagnostics(diagnostics: dict, ok: bool) -> str:
    if not ok:
        return "error"
    if diagnostics.get("web_ui_likely_complete"):
        return "ok_full_web"
    if diagnostics.get("api_streamgenerate_ready"):
        return "ok_api"
    return "partial_cookie"


def _record_source_state(source: str, *, ok: bool, message: str, cookie_length: int = 0,
                         diagnostics: dict = None, target: str = ""):
    key = _source_key(source)
    now = time.time()
    _source_states[key] = {
        "status": _status_for_diagnostics(diagnostics or {}, ok),
        "success": bool(ok),
        "source": source or key,
        "cookie_length": cookie_length,
        "cookie_file": target or "",
        "last_time": now,
        "last_sync_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "message": message,
        "diagnostics": diagnostics or {},
    }


def accept_cookie_source(raw: str, sapisid: str = "", source: str = "manual-import",
                         target: str = None, add_to_pool: bool = True) -> dict:
    """Normalize, persist, add to pool, and record status for one cookie source."""
    global _last_push_time, _last_push_status, _last_refresh_source, _last_refresh_diagnostics
    try:
        cookie_str, parsed_sapisid = normalize_cookie_input(raw)
    except Exception as exc:
        message = f"invalid cookie input: {exc}"
        _record_source_state(source, ok=False, message=message)
        return {"success": False, "message": message, "source": source, "diagnostics": {}}

    if not cookie_str:
        message = "no Gemini/Google cookies found"
        _record_source_state(source, ok=False, message=message)
        return {"success": False, "message": message, "source": source, "diagnostics": {}}

    final_sapisid = sapisid or parsed_sapisid
    diagnostics = diagnose_cookie_header(cookie_str)
    target = target or CONFIG.get("cookie_file") or _cookie_file
    ok = write_cookie_file(cookie_str, final_sapisid, target)
    message = "cookies saved" if ok else "failed to save cookies"
    if ok and add_to_pool:
        try:
            from .admin import add_cookie
            add_cookie(cookie_str, final_sapisid, source=source)
        except Exception as exc:
            log(f"Cookie pool update skipped for {source}: {exc}")
    _last_push_time = time.time()
    _last_push_status = _status_for_diagnostics(diagnostics, ok)
    _last_refresh_source = source
    _last_refresh_diagnostics = diagnostics
    _record_source_state(
        source,
        ok=ok,
        message=message,
        cookie_length=len(cookie_str),
        diagnostics=diagnostics,
        target=target,
    )
    return {
        "success": ok,
        "message": message,
        "source": source,
        "method": _source_key(source),
        "cookie_length": len(cookie_str),
        "cookie_file": target,
        "diagnostics": diagnostics,
        "needs_browser_login": not diagnostics.get("web_ui_likely_complete"),
    }


def get_current_cookie() -> tuple:
    """Get current cookie, with rotation if enabled."""
    global _cookie_index, _request_count, _last_rotation

    with _lock:
        # Check if rotation is enabled
        if not CONFIG.get("cookie_rotation") or not CONFIG.get("cookie_files"):
            return load_cookie()

        # Check if we need to rotate
        _request_count += 1
        interval = CONFIG.get("cookie_rotation_interval", 10)

        if _request_count >= interval:
            _cookie_index = (_cookie_index + 1) % len(CONFIG["cookie_files"])
            _request_count = 0
            _last_rotation = time.time()
            log(f"Rotated to cookie index {_cookie_index}")

        # Load current cookie file
        cookie_file = CONFIG["cookie_files"][_cookie_index]
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, encoding="utf-8-sig", errors="replace") as f:
                    content = f.read().strip()
                cookie, sapisid = normalize_cookie_input(content)
                return cookie, sapisid if sapisid else None
            except Exception as e:
                log(f"Cookie load error from {cookie_file}: {e}")

        return load_cookie()


def get_current_proxy() -> str:
    """Get current proxy, with rotation if enabled."""
    global _proxy_index

    with _lock:
        if not CONFIG.get("proxy_enabled", True):
            return None
        if not CONFIG.get("proxy_rotation") or not CONFIG.get("proxies"):
            return CONFIG.get("proxy")

        # Rotate proxy
        interval = CONFIG.get("proxy_rotation_interval", 10)
        if _request_count % interval == 0:
            _proxy_index = (_proxy_index + 1) % len(CONFIG["proxies"])
            log(f"Rotated to proxy index {_proxy_index}")

        return CONFIG["proxies"][_proxy_index]


def get_rate_limit_delay() -> float:
    """Get delay between requests based on rate limit."""
    delay = CONFIG.get("rate_limit_delay", 2)
    return delay


def check_rate_limit() -> bool:
    """Check if we should delay due to rate limiting."""
    # Simple rate limiting based on config
    delay = get_rate_limit_delay()
    if delay > 0:
        time.sleep(delay)
    return True


def get_stats() -> dict:
    """Get rotation statistics."""
    return {
        "cookie_index": _cookie_index,
        "proxy_index": _proxy_index,
        "request_count": _request_count,
        "last_rotation": _last_rotation,
        "cookie_files_count": len(CONFIG.get("cookie_files", [])),
        "proxies_count": len(CONFIG.get("proxies", [])),
    }


def write_cookie_file(cookies: str, sapisid: str = "", path: str = None) -> bool:
    """Write cookies to file. Returns True on success."""
    global _cookie_file, _last_push_time, _last_push_status
    target = path or _cookie_file
    try:
        cookie_str, parsed_sapisid = normalize_cookie_input(cookies)
        data = {"cookie": cookie_str, "sapisid": sapisid or parsed_sapisid}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        CONFIG["cookie_file"] = target
        _cookie_file = target
        _last_push_time = time.time()
        _last_push_status = "ok"
        log(f"Cookies written to {target} ({len(cookie_str)} chars)")
        return True
    except Exception as e:
        _last_push_status = f"error: {e}"
        log(f"Failed to write cookies: {e}")
        return False


def extract_cookies(prefer_browser: bool = False, require_web_ui: bool = False) -> tuple:
    """Extract Gemini cookies from configured file or local browsers.

    Returns (cookie_str, sapisid). Cookie values are never logged.
    """
    cookie_str, sapisid = load_cookie()
    if cookie_str and not prefer_browser:
        diag = diagnose_cookie_header(cookie_str)
        if not require_web_ui or diag.get("web_ui_likely_complete"):
            return cookie_str, sapisid

    local_cookie, local_sapisid, _ = _refresh_from_local_sources(require_web_ui=require_web_ui)
    if local_cookie:
        return local_cookie, local_sapisid

    if cookie_str:
        return cookie_str, sapisid
    return "", None


def manual_refresh() -> dict:
    """Manually refresh cookies. Returns status dict."""
    global _last_push_time, _last_push_status, _last_refresh_source, _last_refresh_diagnostics
    try:
        cookie_str, sapisid = load_cookie()
        current_diag = diagnose_cookie_header(cookie_str) if cookie_str else None
        require_web_upgrade = bool(
            cookie_str
            and current_diag
            and current_diag.get("api_streamgenerate_ready")
            and not current_diag.get("web_ui_likely_complete")
        )
        upgraded_cookie, upgraded_sapisid, upgraded_source = _refresh_from_local_sources(
            require_web_ui=require_web_upgrade
        )
        if upgraded_cookie and (not cookie_str or _cookie_score(upgraded_cookie) > _cookie_score(cookie_str)):
            ok = _save_cookie_candidate(upgraded_cookie, upgraded_sapisid, upgraded_source)
            upgraded_diag = diagnose_cookie_header(upgraded_cookie)
            _last_refresh_source = upgraded_source
            _last_refresh_diagnostics = upgraded_diag
            _last_push_time = time.time()
            _last_push_status = (
                "ok_full_web" if upgraded_diag.get("web_ui_likely_complete") else "ok_api"
            ) if ok else "refresh_write_failed"
            return {
                "success": ok,
                "status": "Cookie refreshed" if ok else "Failed to save refreshed cookie",
                "cookie_length": len(upgraded_cookie),
                "source": upgraded_source,
                "diagnostics": upgraded_diag,
                "needs_browser_login": not upgraded_diag.get("web_ui_likely_complete"),
            }

        if cookie_str:
            _last_push_time = time.time()
            _last_refresh_source = "configured-file"
            _last_refresh_diagnostics = current_diag
            api_ready = bool(current_diag and current_diag.get("api_streamgenerate_ready"))
            web_ready = bool(current_diag and current_diag.get("web_ui_likely_complete"))
            if web_ready:
                _last_push_status = "ok_full_web"
                status = "Cookie is valid for API and full Web UI"
            elif api_ready:
                _last_push_status = "api_ok_web_incomplete"
                status = "Cookie is valid for text/API calls but incomplete for full Gemini Web UI tools"
            else:
                _last_push_status = "partial_cookie"
                status = "Cookie file exists but is missing required Gemini auth markers"
            return {
                "success": api_ready,
                "status": status,
                "cookie_length": len(cookie_str),
                "source": "configured-file",
                "diagnostics": current_diag,
                "needs_browser_login": not web_ready,
            }

        _last_push_status = "no_cookie"
        _last_refresh_source = ""
        _last_refresh_diagnostics = None
        return {
            "success": False,
            "status": "No cookie found. Use extension or browser login.",
            "needs_browser_login": True,
        }
    except Exception as e:
        _last_push_status = f"error: {e}"
        return {"success": False, "status": str(e)}


def _auto_refresh_worker():
    """Background thread for auto cookie refresh."""
    global _last_push_time, _last_push_status
    while _auto_refresh_enabled:
        try:
            result = manual_refresh()
            if result.get("success"):
                log(f"Auto-refresh: {result.get('status', 'cookie refreshed')}")
            else:
                log(f"Auto-refresh: {result.get('status', 'no cookie found')}")
        except Exception as e:
            _last_push_status = f"auto_error: {e}"
            log(f"Auto-refresh error: {e}")

        sleep_seconds = _auto_refresh_interval * 3600
        for _ in range(int(sleep_seconds)):
            if not _auto_refresh_enabled:
                return
            time.sleep(1)


def start_auto_refresh(interval_hours: int = 12):
    """Start auto-refresh background thread."""
    global _auto_refresh_enabled, _auto_refresh_interval, _auto_refresh_thread
    _auto_refresh_interval = max(1, interval_hours)
    if _auto_refresh_enabled:
        return
    _auto_refresh_enabled = True
    _auto_refresh_thread = threading.Thread(target=_auto_refresh_worker, daemon=True)
    _auto_refresh_thread.start()
    log(f"Auto-refresh started (every {_auto_refresh_interval}h)")


def stop_auto_refresh():
    """Stop auto-refresh background thread."""
    global _auto_refresh_enabled
    _auto_refresh_enabled = False
    log("Auto-refresh stopped")


def get_cookie_status() -> dict:
    """Get cookie status for API/dashboard."""
    cookie_str, sapisid = load_cookie()
    diagnostics = diagnose_cookie_header(cookie_str) if cookie_str else None
    pool_size = 0
    healthy_pool = 0
    if not cookie_str:
        try:
            from .admin import list_cookies
            cookies = list_cookies()
            pool_size = len(cookies)
            healthy_pool = sum(1 for c in cookies if c.get("healthy", True))
        except Exception:
            pass
    return {
        "cookie_valid": bool(cookie_str) or healthy_pool > 0,
        "cookie_length": len(cookie_str) if cookie_str else 0,
        "has_sapisid": bool(sapisid),
        "diagnostics": diagnostics,
        "api_streamgenerate_ready": bool(diagnostics and diagnostics.get("api_streamgenerate_ready")),
        "web_ui_likely_complete": bool(diagnostics and diagnostics.get("web_ui_likely_complete")),
        "cookie_pool_size": pool_size,
        "healthy_cookie_pool_size": healthy_pool,
        "auto_refresh_enabled": _auto_refresh_enabled,
        "refresh_interval_hours": _auto_refresh_interval,
        "last_push_time": _last_push_time,
        "last_push_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(_last_push_time)) if _last_push_time else None,
        "status": _last_push_status,
        "last_refresh_source": _last_refresh_source,
        "last_refresh_diagnostics": _last_refresh_diagnostics,
        "sources": dict(_source_states),
        "source_browser": "Edge",
        "next_refresh_str": _get_next_refresh_str(),
    }


def _get_next_refresh_str() -> str:
    """Get next refresh time as string."""
    if not _auto_refresh_enabled or not _last_push_time:
        return "N/A"
    next_time = _last_push_time + (_auto_refresh_interval * 3600)
    if next_time < time.time():
        return "Soon"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))
