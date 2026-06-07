"""Cookie and proxy rotation management."""
import os
import time
import threading
from .config import CONFIG
from .gemini import load_cookie, log

_lock = threading.Lock()
_cookie_index = 0
_proxy_index = 0
_request_count = 0
_last_rotation = 0


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
                with open(cookie_file) as f:
                    content = f.read().strip()
                if content.startswith("{"):
                    import json
                    data = json.loads(content)
                    return data.get("cookie", ""), data.get("sapisid", "")
                else:
                    pairs = dict(p.split("=", 1) for p in content.split("; ") if "=" in p)
                    sapisid = pairs.get("SAPISID", "")
                    return content, sapisid if sapisid else None
            except Exception as e:
                log(f"Cookie load error from {cookie_file}: {e}")
        
        return load_cookie()


def get_current_proxy() -> str:
    """Get current proxy, with rotation if enabled."""
    global _proxy_index
    
    with _lock:
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
