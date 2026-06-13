"""Gemini StreamGenerate protocol implementation with httpx streaming."""
import json
import time
import uuid
import re
import urllib.request
import urllib.parse
import ssl
import os
import hashlib
import threading
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .config import CONFIG
from .cookies import normalize_cookie_input

_ssl_ctx = None
_cookie_cache = {"str": "", "sapisid": None, "mtime": 0}
_account_cookie_cache = {}
_account_lock = threading.Lock()
_account_index = 0
_httpx_client = None
_bl_cache = {"bl": None, "ts": 0}
_xsrf_cache = {"token": None, "ts": 0, "cookie_sig": ""}
_request_context = threading.local()
NON_RETRYABLE_BARD_ERROR_CODES = {"1003", "1152", "1155"}
# Any BardErrorInfo code not explicitly listed as retryable will also skip retry
# after the first failed attempt (avoids wasting 30+ s on upstream rejections).
_RETRYABLE_BARD_ERROR_CODES = set()  # empty = all unknown bard codes are non-retryable


def is_proxy_enabled() -> bool:
    return bool(CONFIG.get("proxy_enabled", True))


def reset_http_client():
    global _httpx_client
    client = _httpx_client
    _httpx_client = None
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def _extract_bard_error(raw: str):
    return re.search(r'BardErrorInfo\s*\[(\d+)\]', raw) or re.search(
        r'BardErrorInfo"[\s,\]]*\[(\d+)\]', raw
    )


def _bard_error_code_from_exception(exc: Exception) -> str:
    match = _extract_bard_error(str(exc))
    return match.group(1) if match else ""


def _is_non_retryable_bard_error(exc: Exception) -> bool:
    code = _bard_error_code_from_exception(exc)
    if not code:
        return False  # not a bard error at all → let normal retry happen
    if code in NON_RETRYABLE_BARD_ERROR_CODES:
        return True
    # Unknown bard code: treat as non-retryable unless explicitly retryable
    if code not in _RETRYABLE_BARD_ERROR_CODES:
        log(f"BardErrorInfo [{code}] not in retryable set; skipping retry")
        return True
    return False


def log(msg: str):
    if CONFIG["log_requests"]:
        import sys
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        sys.stderr.flush()


def _get_ssl_ctx():
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


def _get_httpx_client(process_id: int = 0):
    global _httpx_client
    if _httpx_client is None and HAS_HTTPX:
        # 优先使用代理池
        proxy = None
        if is_proxy_enabled() and CONFIG.get("proxy_pool_enabled"):
            from .proxy_builtin import get_proxy_url
            proxy = get_proxy_url(process_id)

        # 回退到配置中的代理
        if is_proxy_enabled() and not proxy:
            proxy = CONFIG.get("proxy")

        transport = httpx.HTTPTransport(proxy=proxy) if proxy else None
        _httpx_client = httpx.Client(transport=transport, timeout=CONFIG["request_timeout_sec"], verify=True)
    return _httpx_client


def load_cookie() -> tuple:
    """Load cookie from file with mtime-based caching."""
    cookie_file = CONFIG.get("cookie_file")
    if not cookie_file or not os.path.exists(cookie_file):
        return "", None
    try:
        mtime = os.path.getmtime(cookie_file)
        if mtime == _cookie_cache["mtime"] and _cookie_cache["str"]:
            return _cookie_cache["str"], _cookie_cache["sapisid"]
        with open(cookie_file, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()
        cookie_str, sapisid = normalize_cookie_input(content)
        _cookie_cache.update({"str": cookie_str, "sapisid": sapisid or None, "mtime": mtime})
        return cookie_str, sapisid if sapisid else None
    except Exception as e:
        log(f"Cookie load error: {e}")
        return _cookie_cache["str"], _cookie_cache["sapisid"]


def _reset_request_account():
    _request_context.account_id = ""
    _request_context.auth_user = None
    _request_context.bound_proxy = ""
    _request_context.cookie_str = ""
    _request_context.sapisid = None


def _remember_request_cookie(cookie_str: str, sapisid):
    _request_context.cookie_str = cookie_str or ""
    _request_context.sapisid = sapisid
    return cookie_str, sapisid


def _auth_user_from_account(account: dict):
    auth_user = account.get("auth_user")
    if auth_user is not None and auth_user != "":
        return auth_user
    account_id = str(account.get("id") or "")
    if account_id.startswith("u/"):
        return account_id.split("/", 1)[1]
    if account_id.isdigit():
        return account_id
    return None


def _load_cookie_from_path(path: str) -> tuple:
    if not path or not os.path.exists(path):
        return "", None
    try:
        mtime = os.path.getmtime(path)
        cached = _account_cookie_cache.get(path)
        if cached and cached.get("mtime") == mtime and cached.get("str"):
            return cached["str"], cached.get("sapisid")
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()
        cookie_str, sapisid = normalize_cookie_input(content)
        _account_cookie_cache[path] = {"str": cookie_str, "sapisid": sapisid or None, "mtime": mtime}
        return cookie_str, sapisid if sapisid else None
    except Exception as e:
        log(f"Account cookie load error: {e}")
        cached = _account_cookie_cache.get(path) or {}
        return cached.get("str", ""), cached.get("sapisid")


def _select_configured_account():
    global _account_index
    accounts = [
        account for account in (CONFIG.get("accounts") or [])
        if account.get("enabled", True) and account.get("cookie_file")
    ]
    if not accounts:
        return None
    with _account_lock:
        start = _account_index % len(accounts)
        _account_index += 1
    for offset in range(len(accounts)):
        account = accounts[(start + offset) % len(accounts)]
        cookie_str, sapisid = _load_cookie_from_path(account.get("cookie_file"))
        if not cookie_str:
            continue
        _request_context.account_id = account.get("id") or ""
        _request_context.auth_user = _auth_user_from_account(account)
        _request_context.bound_proxy = account.get("primary_proxy") or account.get("proxy") or ""
        return cookie_str, sapisid
    return None


def get_request_cookie() -> tuple:
    """Return the cookie that should be used for the next upstream request.

    Order of preference:
    1. Admin cookie pool, if populated by /admin/cookie or init_admin().
    2. Configured cookie rotation from cookie_manager.
    3. Plain CONFIG["cookie_file"] via load_cookie().

    Imports are intentionally lazy to avoid module import cycles.
    """
    _reset_request_account()

    selected = _select_configured_account()
    if selected:
        return _remember_request_cookie(*selected)

    try:
        from .admin import get_next_cookie
        cookie_str, sapisid = get_next_cookie()
        if cookie_str:
            return _remember_request_cookie(cookie_str, sapisid)
    except Exception as e:
        log(f"Admin cookie selection failed: {e}")

    try:
        from .cookie_manager import get_current_cookie
        cookie_str, sapisid = get_current_cookie()
        if cookie_str:
            return _remember_request_cookie(cookie_str, sapisid)
    except Exception as e:
        log(f"Rotating cookie selection failed: {e}")

    return _remember_request_cookie(*load_cookie())


def get_current_request_cookie() -> tuple:
    """Return the cookie already bound to this request, or select one."""
    cookie_str = getattr(_request_context, "cookie_str", "") or ""
    if cookie_str:
        return cookie_str, getattr(_request_context, "sapisid", None)
    return get_request_cookie()


def make_sapisidhash(sapisid: str) -> str:
    ts = int(time.time())
    h = hashlib.sha1(f"{ts} {sapisid} https://gemini.google.com".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"


def _account_prefix() -> str:
    """Return the Gemini account path prefix for non-default Google accounts."""
    auth_user = getattr(_request_context, "auth_user", None)
    if auth_user is None or auth_user == "":
        auth_user = CONFIG.get("auth_user")
    if auth_user is None or auth_user == "":
        return ""
    return f"/u/{auth_user}"


def _build_headers_for_cookie(cookie_str: str = "", sapisid=None) -> dict:
    account_prefix = _account_prefix()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": f"https://gemini.google.com{account_prefix}/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if account_prefix:
        auth_user = getattr(_request_context, "auth_user", None)
        if auth_user is None or auth_user == "":
            auth_user = CONFIG["auth_user"]
        headers["X-Goog-AuthUser"] = str(auth_user)
    if cookie_str:
        headers["Cookie"] = cookie_str
    if sapisid:
        headers["Authorization"] = make_sapisidhash(sapisid)
    return headers


def _build_headers() -> dict:
    cookie_str, sapisid = get_request_cookie()
    return _build_headers_for_cookie(cookie_str, sapisid)


def _extract_xsrf_token_from_html(html: str) -> str:
    match = re.search(r'"SNlM0e"\s*:\s*"([^"]+)"', html or "")
    return match.group(1) if match else ""


def _discover_xsrf_token(cookie_str: str = None, sapisid: str = None) -> str:
    """Discover the authenticated Gemini page XSRF token without logging it."""
    cookie_str = cookie_str or ""
    if not cookie_str:
        return ""
    cookie_sig = hashlib.sha1(cookie_str.encode("utf-8", errors="ignore")).hexdigest()[:16]
    now = time.time()
    if (
        _xsrf_cache["token"]
        and _xsrf_cache["cookie_sig"] == cookie_sig
        and now - _xsrf_cache["ts"] < 1800
    ):
        return _xsrf_cache["token"]
    try:
        account_prefix = _account_prefix()
        url = f"https://gemini.google.com{account_prefix}/app"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://gemini.google.com",
            "Referer": f"https://gemini.google.com{account_prefix}/app",
            "X-Same-Domain": "1",
            "Cookie": cookie_str,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if account_prefix:
            auth_user = getattr(_request_context, "auth_user", None)
            if auth_user is None or auth_user == "":
                auth_user = CONFIG["auth_user"]
            headers["X-Goog-AuthUser"] = str(auth_user)
        if sapisid:
            headers["Authorization"] = make_sapisidhash(sapisid)
        req = urllib.request.Request(url, headers=headers, method="GET")
        proxy = (getattr(_request_context, "last_proxy", "") or CONFIG.get("proxy")) if is_proxy_enabled() else ""
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=_get_ssl_ctx()),
            )
            resp = opener.open(req, timeout=15)
        else:
            resp = urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=15)
        token = _extract_xsrf_token_from_html(resp.read().decode("utf-8", errors="replace"))
        if token:
            _xsrf_cache.update({"token": token, "ts": now, "cookie_sig": cookie_sig})
            log("Discovered authenticated Gemini XSRF token")
        return token
    except Exception as e:
        log(f"XSRF discovery failed: {e}")
        return ""


def _resolve_xsrf_token() -> str:
    """Resolve XSRF token.  Original behaviour: only send if explicitly configured.
    Auto-discovery makes an extra page request that can trigger rate-limiting and
    may return an invalid token, both causing BardErrorInfo upstream rejections."""
    configured = CONFIG.get("xsrf_token")
    if configured:
        return configured
    # Auto-discovery is OFF by default to match original behaviour.
    # Set CONFIG["xsrf_auto_discover"] = True to enable it.
    if CONFIG.get("xsrf_auto_discover"):
        cookie_str = getattr(_request_context, "cookie_str", "")
        sapisid = getattr(_request_context, "sapisid", None)
        if not cookie_str:
            cookie_str, sapisid = get_request_cookie()
        return _discover_xsrf_token(cookie_str, sapisid)
    return ""


def _build_payload(prompt: str, model_id: int, think_mode: int, file_refs: list = None, extra_fields: dict = None) -> str:
    inner = [None] * 102
    if file_refs:
        refs = [[None, None, ref] for ref in file_refs]
        inner[0] = [prompt, 0, None, refs, None, None, 0]
    else:
        inner[0] = [prompt, 0, None, None, None, None, 0]
    inner[1] = ["en"]
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    inner[6] = [0]
    inner[7] = 1
    inner[10] = 1
    inner[11] = 0
    inner[17] = [[think_mode]]
    inner[18] = 0
    inner[27] = 1
    inner[30] = [4]
    inner[41] = [2]
    inner[53] = 0
    inner[59] = str(uuid.uuid4())
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id

    # Handle extra fields (including search)
    if extra_fields:
        fields = dict(extra_fields)
        search_mode = fields.pop("search", False)
        if search_mode:
            # Enable web search - field 30 controls search
            inner[30] = [5]  # 5 enables search
        for k, v in fields.items():
            if isinstance(k, int):
                inner[k] = v

    outer = [None, json.dumps(inner)]
    params = {"f.req": json.dumps(outer)}
    xsrf_token = _resolve_xsrf_token()
    if xsrf_token:
        params["at"] = xsrf_token
    return urllib.parse.urlencode(params)


def _discover_bl() -> str:
    """Discover BL token from Gemini page source, with caching."""
    now = time.time()
    if _bl_cache["bl"] and now - _bl_cache["ts"] < 3600:
        return _bl_cache["bl"]
    try:
        cookie_str = getattr(_request_context, "cookie_str", "")
        sapisid = getattr(_request_context, "sapisid", None)
        headers = _build_headers_for_cookie(cookie_str, sapisid) if cookie_str else _build_headers()
        account_prefix = _account_prefix()
        url = f"https://gemini.google.com{account_prefix}/app"
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ctx = _get_ssl_ctx()
        proxy = (getattr(_request_context, "last_proxy", "") or CONFIG.get("proxy")) if is_proxy_enabled() else ""
        req = urllib.request.Request(url, headers=headers, method="GET")
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=ctx)
            )
            resp = opener.open(req, timeout=15)
        else:
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        page = resp.read().decode("utf-8", errors="replace")
        import re as _re
        m = _re.search(r'boq_assistant-bard-web-server_[\w.]+', page)
        if m:
            _bl_cache["bl"] = m.group(0)
            _bl_cache["ts"] = now
            log(f"Discovered BL: {_bl_cache['bl']}")
            return _bl_cache["bl"]
    except Exception as e:
        log(f"BL discovery failed: {e}")
    return CONFIG.get("gemini_bl", "")


def _resolve_bl() -> str:
    """Resolve BL token: config first (matches original behaviour), cache second,
    discovery last.  Discovery makes an extra HTTP request and may return a token
    that doesn't match the StreamGenerate RPC version, causing BardErrorInfo."""
    # 1. Cached value (already validated by a successful request or prior discovery)
    if _bl_cache["bl"]:
        return _bl_cache["bl"]
    # 2. Config value (static, known-good — original behaviour)
    config_bl = CONFIG.get("gemini_bl", "")
    if config_bl:
        _bl_cache["bl"] = config_bl
        _bl_cache["ts"] = time.time()
        return config_bl
    # 3. Dynamic discovery (last resort — may cause BardErrorInfo on version mismatch)
    discovered = _discover_bl()
    if discovered:
        return discovered
    return ""


def _get_url() -> str:
    reqid = int(time.time()) % 1000000
    account_prefix = _account_prefix()
    bl = _resolve_bl()
    return (
        f"https://gemini.google.com{account_prefix}/_/BardChatUi/data/"
        "assistant.lamda.BardFrontendService/StreamGenerate"
        f"?bl={bl}&hl=en&_reqid={reqid}&rt=c"
    )


def _get_batchexecute_url(rpcids: str, source_path: str = "/app") -> str:
    reqid = int(time.time()) % 1000000
    account_prefix = _account_prefix()
    bl = _resolve_bl()
    query = urllib.parse.urlencode({
        "rpcids": rpcids,
        "source-path": source_path,
        "bl": bl,
        "hl": "en",
        "_reqid": reqid,
        "rt": "c",
    })
    return f"https://gemini.google.com{account_prefix}/_/BardChatUi/data/batchexecute?{query}"


def _current_request_headers() -> dict:
    cookie_str, sapisid = get_current_request_cookie()
    return _build_headers_for_cookie(cookie_str, sapisid)


def _batch_execute_rpc(rpcid: str, payload: str, source_path: str = "/app") -> str:
    """Execute a Gemini Web batchexecute RPC using the active request cookie."""
    headers = _current_request_headers()
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "x-goog-ext-525001261-jspb": "[1,null,null,null,null,null,null,null,[4]]",
        "x-goog-ext-73010989-jspb": "[0]",
    })
    data = {
        "f.req": json.dumps([[[rpcid, payload, None, "generic"]]], separators=(",", ":")),
    }
    at = _resolve_xsrf_token()
    if at:
        data["at"] = at
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        _get_batchexecute_url(rpcid, source_path),
        data=body,
        headers=headers,
        method="POST",
    )
    proxy, leased_proxy = get_current_request_proxy(lease_if_missing=True)
    try:
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=_get_ssl_ctx()),
            )
            resp = opener.open(req, timeout=CONFIG["request_timeout_sec"])
        else:
            resp = urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=CONFIG["request_timeout_sec"])
        return resp.read().decode("utf-8", errors="replace")
    finally:
        if leased_proxy:
            release_current_request_proxy()


def _extract_batchexecute_frames(raw: str, rpcid: str = "") -> list:
    frames = []

    def walk(node):
        if isinstance(node, list):
            if len(node) >= 3 and node[0] == "wrb.fr" and (not rpcid or node[1] == rpcid):
                frames.append(node)
            for item in node:
                walk(item)

    text = (raw or "").lstrip()
    if text.startswith(")]}'"):
        text = text[4:].lstrip()
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
    return frames


def get_full_size_image_url(cid: str, rid: str, rcid: str, image_id: str) -> str:
    if not all([cid, rid, rcid, image_id]):
        return ""
    payload = [
        [
            [None, None, None, [None, None, None, None, None, ""]],
            [image_id, 0],
            None,
            [19, ""],
            None,
            None,
            None,
            None,
            None,
            "",
        ],
        [rid, rcid, cid, None, ""],
        1,
        0,
        1,
    ]
    try:
        raw = _batch_execute_rpc("c8o8Fe", json.dumps(payload, separators=(",", ":")))
        for frame in _extract_batchexecute_frames(raw, "c8o8Fe"):
            body = frame[2]
            if not isinstance(body, str) or not body:
                continue
            data = json.loads(body)
            url = _get_nested(data, [0], "")
            if isinstance(url, str) and url.startswith("http"):
                return url
    except Exception as exc:
        log(f"Full-size image RPC failed: {exc}")
    return ""


def _fetch_text_url(url: str) -> str:
    headers = _current_request_headers()
    headers.update({
        "Accept": "text/plain,text/html,*/*",
        "Origin": "https://gemini.google.com",
        "Referer": f"https://gemini.google.com{_account_prefix()}/app",
    })
    req = urllib.request.Request(url, headers=headers, method="GET")
    proxy, leased_proxy = get_current_request_proxy(lease_if_missing=True)
    try:
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=_get_ssl_ctx()),
            )
            resp = opener.open(req, timeout=90)
        else:
            resp = urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=90)
        return resp.read().decode("utf-8", errors="replace").strip()
    finally:
        if leased_proxy:
            release_current_request_proxy()


def resolve_generated_image_download_url(item: dict) -> str:
    """Resolve Gemini generated-image metadata to a downloadable URL when possible."""
    if not isinstance(item, dict):
        return ""
    original = get_full_size_image_url(
        item.get("cid", ""),
        item.get("rid", ""),
        item.get("rcid", ""),
        item.get("image_id", ""),
    )
    if original:
        try:
            first = _fetch_text_url(f"{original}=d-I?alr=yes")
            if first.startswith("http"):
                second = _fetch_text_url(first)
                if second.startswith("http"):
                    return second
                return first
        except Exception as exc:
            log(f"Generated image redirect resolution failed: {exc}")
        return original
    url = item.get("url", "")
    if url and "googleusercontent.com" in url and "=s2048-rj" not in url:
        return f"{url}=s2048-rj"
    return ""


def is_internal_control_only(text: str) -> bool:
    """Return True when Gemini only returned an internal routing/control block."""
    value = (text or "").strip()
    if not value:
        return False
    value = re.sub(r"```(?:json|text)?\s*", "", value, flags=re.I).replace("```", "").strip()
    lowered = value.lower()
    if "<websearch" in lowered and "</websearch>" in lowered:
        remainder = re.sub(r"<websearch\b[^>]*>.*?</websearch>", "", value, flags=re.I | re.S).strip()
        return not remainder
    try:
        parsed = json.loads(value)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        keys = set(parsed)
        if keys and keys.issubset({"stream", "text", "images", "media", "artifacts", "files"}):
            inner = str(parsed.get("text") or "").strip().lower()
            return "<websearch" in inner and "</websearch>" in inner
    return False


def clean_text(text: str, strip: bool = True) -> str:
    """Clean response text, removing internal artifacts while preserving content."""
    text = text or ""
    # Remove internal Gemini/WebSearch routing decisions. These can appear when
    # a search-enabled request decides no search is needed; clients expect the
    # final answer, not the routing annotation.
    text = re.sub(r"<websearch\b[^>]*>.*?</websearch>", "", text, flags=re.I | re.S)
    # Remove code reference artifacts
    text = re.sub(
        r'```(?:python|javascript|text)\?code_(?:reference|stdout)&code_event_index=\d+\n.*?```\n?',
        '', text, flags=re.DOTALL
    )
    # Remove card content URLs (internal Gemini UI artifacts)
    text = re.sub(r'http://googleusercontent\.com/card_content/\d+\n?', '', text)
    return text.strip() if strip else text


def _normalize_embedded_json_text(text: str) -> str:
    """Normalize common JSON escapes before URL/media regex extraction."""
    return (
        (text or "")
        .replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\u003D", "=")
        .replace("\\u003f", "?")
        .replace("\\u003F", "?")
    )


def _clean_media_url(url: str) -> str:
    """Trim JSON/string punctuation that often trails embedded media URLs."""
    value = _normalize_embedded_json_text(url).strip()
    if not value:
        return ""
    value = value.lstrip('\\\'"`(<[{')
    for marker in ('\\"', "\\'", '"', "'", "`", "<", ">", ")", "]", "}", ",null", "],[", "\\n", "\n", "\r", "\t", " "):
        idx = value.find(marker)
        if idx > 0:
            value = value[:idx]
    return value.rstrip('\\\'"`,]}>)')


def _is_probable_media_artifact_url(url: str) -> bool:
    """Filter Gemini Web UI chrome assets out of generated media candidates."""
    if not url:
        return False
    if url.startswith("data:image/") or url.startswith("data:video/") or url.startswith("data:audio/"):
        return True
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    full = url.lower()
    if host in {"fonts.gstatic.com", "www.gstatic.com", "ssl.gstatic.com"}:
        return False
    if host.endswith(".gstatic.com") and "googleusercontent" not in host:
        return False
    ui_markers = (
        "/short-term/release/googlesymbols/",
        "/lamda/images/",
        "gemini_sparkle",
        "/_/mss/",
        "/og/_/js/",
    )
    if any(marker in path for marker in ui_markers):
        return False
    if host.endswith("googleusercontent.com") and (
        path.startswith(("/a/", "/ogw/", "/rd-ogw/"))
        or "=s64" in full
        or "=w72" in full
        or "=s96" in full
    ):
        return False
    return True


def _classify_media_url(url: str, context: str = "") -> str:
    """Return image/video/audio when a URL is likely a generated media artifact."""
    url = _clean_media_url(url)
    if url.startswith("data:image/"):
        return "image"
    if url.startswith("data:video/"):
        return "video"
    if url.startswith("data:audio/"):
        return "audio"
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = urllib.parse.unquote(parsed.query.lower())
    context_lower = (context or "").lower()
    if re.search(r'\.(png|jpg|jpeg|gif|webp|bmp|svg)(?:$|[?#])', path):
        return "image"
    if re.search(r'\.(mp4|webm|mov|m4v)(?:$|[?#])', path):
        return "video"
    if re.search(r'\.(mp3|wav|ogg|m4a|aac|flac)(?:$|[?#])', path):
        return "audio"
    if "video/" in query:
        return "video"
    if "audio/" in query:
        return "audio"
    if "image/" in query:
        return "image"
    if host.endswith("googlevideo.com") or "videoplayback" in path:
        return "video"
    if host == "storage.googleapis.com" and "audio" in path:
        return "audio"
    if re.search(r'\b(video_url|videourl|video_uri|video stream|type["\']?\s*:\s*["\']?video)\b', context_lower):
        return "video"
    if re.search(r'\b(audio_url|audiourl|audio_uri|music_url|type["\']?\s*:\s*["\']?audio)\b', context_lower):
        return "audio"
    if re.search(r'\b(image_url|imageurl|image_uri|cover_url|thumbnail_url|type["\']?\s*:\s*["\']?image)\b', context_lower):
        return "image"
    if "video/" in context_lower:
        return "video"
    if "audio/" in context_lower:
        return "audio"
    if "image/" in context_lower:
        return "image"
    if host.endswith("googleusercontent.com"):
        if "video" in context_lower:
            return "video"
        if "audio" in context_lower or "music" in context_lower:
            return "audio"
        return "image"
    return ""


def _response_text_candidates(raw: str, include_raw: bool = False) -> list:
    """Return text snippets from either raw wrb.fr payloads or plain text."""
    texts = []
    for line in raw.split("\n"):
        for t in _extract_texts_from_line(line):
            texts.append(t)
    if include_raw and raw:
        normalized = _normalize_embedded_json_text(raw)
        if normalized not in texts:
            texts.append(normalized)
    return texts or [raw]


def _get_nested(value, path, default=None):
    cur = value
    for key in path:
        try:
            if isinstance(cur, dict):
                cur = cur[key]
            elif isinstance(cur, list) and isinstance(key, int):
                cur = cur[key]
            else:
                return default
        except (KeyError, IndexError, TypeError):
            return default
    return cur


def _iter_streamgenerate_inner(raw: str):
    for line in (raw or "").split("\n"):
        if '"wrb.fr"' not in line or len(line) < 80:
            continue
        try:
            frame = json.loads(line)
            inner_str = _get_nested(frame, [0, 2])
            if not isinstance(inner_str, str) or len(inner_str) < 20:
                continue
            inner = json.loads(inner_str)
            if isinstance(inner, list):
                yield inner
        except (json.JSONDecodeError, TypeError):
            continue


def extract_conversation_metadata(raw: str) -> dict:
    """Extract Gemini conversation ids needed by media download RPCs."""
    metadata = {"cid": "", "rid": "", "rcid": ""}
    for inner in _iter_streamgenerate_inner(raw):
        m_data = _get_nested(inner, [1])
        if isinstance(m_data, list):
            if _get_nested(m_data, [0]):
                metadata["cid"] = _get_nested(m_data, [0])
            if _get_nested(m_data, [1]):
                metadata["rid"] = _get_nested(m_data, [1])
        for candidate in _get_nested(inner, [4], []) or []:
            rcid = _get_nested(candidate, [0])
            if rcid:
                metadata["rcid"] = rcid
    return metadata


def extract_generated_image_items(raw: str) -> list:
    """Extract structured generated-image records from StreamGenerate payloads."""
    items = []
    seen = set()
    metadata = {"cid": "", "rid": "", "rcid": ""}

    for inner in _iter_streamgenerate_inner(raw):
        m_data = _get_nested(inner, [1])
        if isinstance(m_data, list):
            metadata = {
                "cid": _get_nested(m_data, [0]) or metadata.get("cid", ""),
                "rid": _get_nested(m_data, [1]) or metadata.get("rid", ""),
                "rcid": metadata.get("rcid", ""),
            }
        for candidate in _get_nested(inner, [4], []) or []:
            rcid = _get_nested(candidate, [0]) or metadata.get("rcid", "")
            candidate_meta = {
                "cid": metadata.get("cid", ""),
                "rid": metadata.get("rid", ""),
                "rcid": rcid,
            }
            blocks = []

            def add_blocks(value):
                if not isinstance(value, list):
                    return
                if _get_nested(value, [0, 3, 3]):
                    blocks.append(value)
                else:
                    blocks.extend(value)

            plain = _get_nested(candidate, [12, 7, 0], [])
            add_blocks(plain)
            image_to_image = _get_nested(candidate, [12, 0, "8", 0], [])
            add_blocks(image_to_image)

            for idx, block in enumerate(blocks):
                url = _clean_media_url(_get_nested(block, [0, 3, 3], "") or "")
                if not url or not _is_probable_media_artifact_url(url):
                    continue
                image_id = _get_nested(block, [1, 0]) or f"http://googleusercontent.com/image_generation_content/{idx}"
                name = _get_nested(block, [0, 3, 2], "") or f"generated-image-{idx}"
                mime_type = _get_nested(block, [0, 3, 10], "") or ""
                size = _get_nested(block, [0, 3, 14], None)
                key = (url, image_id, candidate_meta.get("cid"), candidate_meta.get("rid"), candidate_meta.get("rcid"))
                if key in seen:
                    continue
                seen.add(key)
                item = {
                    "kind": "image",
                    "url": url,
                    "source_url": url,
                    "alt": "",
                    "type": "gemini_generated_image",
                    "name": name,
                    "mime_type": mime_type,
                    "image_id": image_id,
                    **candidate_meta,
                }
                if isinstance(size, list) and len(size) >= 3:
                    item["width"] = size[0]
                    item["height"] = size[1]
                    item["source_bytes"] = size[2]
                items.append(item)
    return items


def extract_images_from_response(raw: str) -> list:
    """Extract image URLs from Gemini response.

    Gemini returns images in several formats:
    1. Markdown: ![alt](url)
    2. Direct URLs: https://...
    3. Inline data: data:image/...;base64,...

    Supports both raw text and wrb.fr formatted responses.
    Returns list of {"url": str, "alt": str, "type": str} dicts.
    """
    images = []
    seen_urls = set()

    for item in extract_generated_image_items(raw):
        url = item.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            images.append({
                "url": url,
                "alt": item.get("alt", ""),
                "type": item.get("type", "gemini_generated_image"),
                "source_url": item.get("source_url", url),
                "name": item.get("name", ""),
                "mime_type": item.get("mime_type", ""),
                "image_id": item.get("image_id", ""),
                "cid": item.get("cid", ""),
                "rid": item.get("rid", ""),
                "rcid": item.get("rcid", ""),
            })

    for t in _response_text_candidates(raw, include_raw=True):
        # Extract markdown images: ![alt](url)
        for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', t):
            alt, url = m.group(1), _clean_media_url(m.group(2))
            if url not in seen_urls and not url.startswith("data:") and _is_probable_media_artifact_url(url):
                seen_urls.add(url)
                images.append({"url": url, "alt": alt, "type": "markdown"})

        # Extract direct image URLs (googleusercontent, etc.)
        for m in re.finditer(r'(https?://(?:lh\d+\.googleusercontent\.com|[^)\s]+\.(?:png|jpg|jpeg|gif|webp))[^\s)]*)', t):
            url = _clean_media_url(m.group(1))
            if url not in seen_urls and _is_probable_media_artifact_url(url):
                seen_urls.add(url)
                images.append({"url": url, "alt": "", "type": "url"})

        for m in re.finditer(r'https?://[^\s"\'<>()\\]+', t):
            url = _clean_media_url(m.group(0))
            context = t[max(0, m.start() - 160):m.end() + 160]
            if (
                url not in seen_urls
                and _is_probable_media_artifact_url(url)
                and _classify_media_url(url, context) == "image"
            ):
                seen_urls.add(url)
                images.append({"url": url, "alt": "", "type": "url"})

        # Extract inline base64 images
        for m in re.finditer(r'(data:image/([^;]+);base64,([A-Za-z0-9+/=]+))', t):
            full_data, fmt = m.group(1), m.group(2)
            if full_data not in seen_urls:
                seen_urls.add(full_data)
                images.append({"url": full_data, "alt": f"Generated image ({fmt})", "type": "base64"})

    return images


def extract_media_from_response(raw: str) -> list:
    """Extract image/video/audio URLs or data URLs from Gemini text responses."""
    media = []
    seen_urls = set()
    direct_patterns = [
        ("image", r'https?://(?:lh\d+\.googleusercontent\.com|[^)\s]+\.(?:png|jpg|jpeg|gif|webp|bmp|svg))[^\s)]*'),
        ("video", r'https?://[^)\s]+\.(?:mp4|webm|mov|m4v)(?:\?[^)\s]*)?'),
        ("audio", r'https?://[^)\s]+\.(?:mp3|wav|ogg|m4a|aac|flac)(?:\?[^)\s]*)?'),
    ]

    for item in extract_generated_image_items(raw):
        url = item.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            media.append(item)

    for t in _response_text_candidates(raw, include_raw=True):
        for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', t):
            alt, url = m.group(1), _clean_media_url(m.group(2))
            if url not in seen_urls and not url.startswith("data:") and _is_probable_media_artifact_url(url):
                seen_urls.add(url)
                media.append({"kind": "image", "url": url, "alt": alt, "type": "markdown"})

        for kind, pattern in direct_patterns:
            for m in re.finditer(pattern, t, re.I):
                url = _clean_media_url(m.group(0))
                if url not in seen_urls and _is_probable_media_artifact_url(url):
                    seen_urls.add(url)
                    media.append({"kind": kind, "url": url, "alt": "", "type": "url"})

        for m in re.finditer(r'https?://[^\s"\'<>()\\]+', t):
            url = _clean_media_url(m.group(0))
            context = t[max(0, m.start() - 160):m.end() + 160]
            kind = _classify_media_url(url, context)
            if kind and url not in seen_urls and _is_probable_media_artifact_url(url):
                seen_urls.add(url)
                media.append({"kind": kind, "url": url, "alt": "", "type": "url"})

        for m in re.finditer(r'(data:(image|video|audio)/([^;]+);base64,([A-Za-z0-9+/=]+))', t, re.I):
            full_data, kind, fmt = m.group(1), m.group(2).lower(), m.group(3)
            if full_data not in seen_urls:
                seen_urls.add(full_data)
                media.append({"kind": kind, "url": full_data, "alt": f"Generated {kind} ({fmt})", "type": "base64"})

    return media


def extract_artifacts_from_response(raw: str) -> list:
    """Extract code/HTML artifacts from response for Canvas-like functionality.

    Supports both raw text and wrb.fr formatted responses.
    Returns list of {"type": str, "language": str, "content": str} dicts.
    """
    artifacts = []
    seen_files = set()

    for t in _response_text_candidates(raw, include_raw=True):
        for m in re.finditer(r'\[file-tag:\s*([^\]\r\n]+)\]', t, re.I):
            name = m.group(1).strip()
            if name and name not in seen_files:
                seen_files.add(name)
                artifacts.append({
                    "type": "file",
                    "language": "",
                    "name": name,
                    "content": "",
                })

        for m in re.finditer(
            r'\b(code-generated-file-[\w.-]+\.(?:pdf|docx?|xlsx?|pptx?|png|jpe?g|webp|mp4|webm|mp3|wav|zip|csv|txt|html))\b',
            t,
            re.I,
        ):
            name = m.group(1).strip()
            if name and name not in seen_files:
                seen_files.add(name)
                artifacts.append({
                    "type": "file",
                    "language": "",
                    "name": name,
                    "content": "",
                })

        for m in re.finditer(r'https?://[^\s"\'<>()\\]+', t):
            url = _clean_media_url(m.group(0))
            path = urllib.parse.urlparse(url).path.lower()
            if not re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|zip|csv|txt|html)(?:$|[?#])', path):
                continue
            if url in seen_files or not _is_probable_media_artifact_url(url):
                continue
            seen_files.add(url)
            artifacts.append({
                "type": "file",
                "language": "",
                "name": os.path.basename(urllib.parse.urlparse(url).path) or "generated-file",
                "url": url,
                "content": "",
            })

        # Extract code blocks: ```language\ncode\n```
        for m in re.finditer(r'```(\w+)?\n(.*?)```', t, re.DOTALL):
            lang = m.group(1) or "text"
            code = m.group(2).strip()
            if code:
                artifacts.append({
                    "type": "code",
                    "language": lang,
                    "content": code,
                })

        # Extract HTML blocks: ```html\nhtml\n```
        for m in re.finditer(r'```html\n(.*?)```', t, re.DOTALL):
            html = m.group(1).strip()
            if html:
                artifacts.append({
                    "type": "html",
                    "language": "html",
                    "content": html,
                })

    return artifacts


def _extract_texts_from_line(line: str) -> list:
    """Parse a single wrb.fr line and return list of text strings found."""
    if '"wrb.fr"' not in line or len(line) < 200:
        return []
    try:
        arr = json.loads(line)
        inner_str = arr[0][2]
        if not inner_str or len(inner_str) < 50:
            return []
        inner = json.loads(inner_str)
        if not (isinstance(inner, list) and len(inner) > 4 and inner[4]):
            return []
        texts = []
        for part in inner[4]:
            if isinstance(part, list) and len(part) > 1 and part[1] and isinstance(part[1], list):
                for t in part[1]:
                    if isinstance(t, str) and t:
                        texts.append(t)
        return texts
    except (json.JSONDecodeError, IndexError, TypeError):
        return []


def _extract_last_response_text(raw: str) -> str:
    """Parse full response to get the last visible text candidate."""
    last_text = ""
    for line in raw.split("\n"):
        for t in _extract_texts_from_line(line):
            if len(t) > len(last_text):
                last_text = t
    return last_text


def response_is_internal_control_only(raw: str) -> bool:
    """Return True when the upstream response only contains routing metadata."""
    return is_internal_control_only(_extract_last_response_text(raw))


def extract_response_text(raw: str) -> str:
    """Parse full response to get final text."""
    bard_err = _extract_bard_error(raw)
    if bard_err:
        raise RuntimeError(f"Gemini upstream rejected request: BardErrorInfo [{bard_err.group(1)}]")
    return clean_text(_extract_last_response_text(raw))


def _bound_proxy_for_account() -> str:
    account_id = getattr(_request_context, "account_id", "") or ""
    if not account_id:
        return ""
    for account in CONFIG.get("accounts") or []:
        if account.get("id") == account_id and account.get("enabled", True):
            return account.get("primary_proxy") or account.get("proxy") or ""
    for binding in CONFIG.get("proxy_account_bindings") or []:
        if binding.get("account_id") == account_id and binding.get("enabled", True):
            return binding.get("primary_proxy") or binding.get("proxy") or ""
    return ""


class UpstreamError(Exception):
    """上游请求错误"""
    def __init__(self, message: str, status_code: int = 502, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class CookieExpiredError(UpstreamError):
    """Cookie 过期错误"""
    def __init__(self, message: str = "Cookie expired"):
        super().__init__(message, status_code=401, retryable=True)


class RateLimitError(UpstreamError):
    """频率限制错误"""
    def __init__(self, message: str = "Rate limited"):
        super().__init__(message, status_code=429, retryable=True)


def _should_refresh_cookie(error: Exception) -> bool:
    """判断是否需要刷新 cookie"""
    error_str = str(error).lower()
    refresh_keywords = [
        "401", "403", "unauthorized", "forbidden",
        "cookie", "expired", "invalid", "login",
        "auth", "session"
    ]
    return any(keyword in error_str for keyword in refresh_keywords)


def _refresh_cookie_if_needed(error: Exception) -> bool:
    """如果需要，刷新 cookie"""
    if not _should_refresh_cookie(error):
        return False

    log(f"Detected auth error, attempting cookie refresh: {error}")

    # 清除缓存
    global _cookie_cache, _bl_cache, _xsrf_cache
    _cookie_cache = {"str": "", "sapisid": None, "mtime": 0}
    _bl_cache = {"bl": None, "ts": 0}
    _xsrf_cache = {"token": None, "ts": 0, "cookie_sig": ""}

    # 重新加载 cookie
    try:
        load_cookie()
        log("Cookie refreshed successfully")
        return True
    except Exception as e:
        log(f"Cookie refresh failed: {e}")
        return False


def _get_proxy_for_request() -> Optional[str]:
    """获取请求代理（优先代理池）"""
    _release_proxy_for_request()
    if not is_proxy_enabled():
        _request_context.last_proxy = ""
        return None
    proxy = None
    if CONFIG.get("proxy_pool_enabled"):
        bound_proxy = getattr(_request_context, "bound_proxy", "") or _bound_proxy_for_account()
        if bound_proxy:
            from .proxy_builtin import lease_proxy_route
            route = lease_proxy_route(identifier=bound_proxy)
            if route:
                _request_context.proxy_lease_id = route["id"]
                _request_context.proxy_route = route
                _request_context.last_proxy = route["url"]
                return route["url"]
            if (CONFIG.get("proxy_health_policy") or {}).get("require_healthy", True):
                _request_context.last_proxy = ""
                raise UpstreamError("Bound account proxy is not healthy; waiting for proxy health checks", status_code=503, retryable=True)

        from .proxy_builtin import lease_proxy_route
        anonymous_policy = CONFIG.get("anonymous_route_policy") or {}
        route = lease_proxy_route(
            group=anonymous_policy.get("group") or anonymous_policy.get("proxy_group") or "GLOBAL",
            strategy=anonymous_policy.get("strategy"),
        )
        if route:
            _request_context.proxy_lease_id = route["id"]
            _request_context.proxy_route = route
            _request_context.last_proxy = route["url"]
            return route["url"]
        try:
            from .proxy_builtin import get_pool
            pool = get_pool()
            if pool.total_count and (CONFIG.get("proxy_health_policy") or {}).get("require_healthy", True):
                _request_context.last_proxy = ""
                raise UpstreamError("No healthy proxy available; waiting for proxy health checks", status_code=503, retryable=True)
        except UpstreamError:
            raise
    proxy = CONFIG.get("proxy")
    _request_context.last_proxy = proxy or ""
    return proxy


def _release_proxy_for_request():
    node_id = getattr(_request_context, "proxy_lease_id", "")
    if not node_id:
        return
    try:
        from .proxy_builtin import release_proxy_route
        release_proxy_route(node_id)
    finally:
        _request_context.proxy_lease_id = ""
        _request_context.proxy_route = None


def get_last_proxy_url() -> str:
    """Return the proxy URL selected for the current worker thread."""
    return getattr(_request_context, "last_proxy", "") or ""


def get_current_request_proxy(lease_if_missing: bool = False) -> tuple[str, bool]:
    """Return the active request proxy, optionally leasing one for follow-up RPCs.

    Media materialization may happen after the primary StreamGenerate request has
    released pool capacity. Reusing ``last_proxy`` keeps Googleusercontent
    downloads on the same exit when one was selected for the upstream request.
    """
    if not is_proxy_enabled():
        _request_context.last_proxy = ""
        return "", False
    proxy = getattr(_request_context, "last_proxy", "") or ""
    if proxy:
        return proxy, False
    if not lease_if_missing:
        return "", False
    return _get_proxy_for_request() or "", True


def release_current_request_proxy():
    """Release a proxy route leased by get_current_request_proxy."""
    _release_proxy_for_request()


def generate_with_metadata(prompt: str, model_id: int, think_mode: int, file_refs: list = None, extra_fields: dict = None) -> dict:
    """Non-streaming generation with raw response metadata for artifact extraction.

    Features (inspired by HelloKimi):
    - Auto cookie refresh on auth errors
    - Auto BL token refresh on failure
    - Smart retry with exponential backoff
    - Built-in proxy pool support
    """
    ctx = _get_ssl_ctx()

    last_err = None
    cookie_refreshed = False

    for attempt in range(CONFIG["retry_attempts"]):
        proxy = None
        try:
            # 每次重试重新获取 URL 和 headers（可能 BL token 已更新）
            headers = _build_headers()
            proxy = _get_proxy_for_request()
            body = _build_payload(prompt, model_id, think_mode, file_refs, extra_fields).encode()
            url = _get_url()

            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            if proxy:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                    urllib.request.HTTPSHandler(context=ctx)
                )
                resp = opener.open(req, timeout=CONFIG["request_timeout_sec"])
            else:
                resp = urllib.request.urlopen(req, context=ctx, timeout=CONFIG["request_timeout_sec"])
            raw = resp.read().decode("utf-8", errors="replace")

            # 检查响应是否有效
            if len(raw) < 100:
                raise UpstreamError("Empty response from upstream")

            result = extract_response_text(raw)
            response_images = extract_images_from_response(raw)
            response_media = extract_media_from_response(raw)
            if not result and not (response_images or response_media):
                if response_is_internal_control_only(raw):
                    return {
                        "text": "",
                        "raw": raw,
                        "images": response_images,
                        "media": response_media,
                        "proxy": proxy or "",
                        "internal_control_only": True,
                    }
                raise UpstreamError("No valid text in response")

            # 标记代理成功
            if is_proxy_enabled() and CONFIG.get("proxy_pool_enabled"):
                from .proxy_builtin import get_pool
                pool = get_pool()
                for node in pool.nodes:
                    if node.url == proxy:
                        pool.mark_success(node)
                        break

            return {
                "text": result,
                "raw": raw,
                "images": response_images,
                "media": response_media,
                "proxy": proxy or "",
                "internal_control_only": False,
            }

        except Exception as e:
            last_err = e
            log(f"Attempt {attempt+1}/{CONFIG['retry_attempts']} failed: {e}")

            # 标记代理失败
            if is_proxy_enabled() and CONFIG.get("proxy_pool_enabled") and proxy:
                from .proxy_builtin import get_pool
                pool = get_pool()
                for node in pool.nodes:
                    if node.url == proxy:
                        pool.mark_failure(node)
                        break
            _release_proxy_for_request()

            # 尝试自动刷新 cookie（只刷新一次）
            if not cookie_refreshed and _refresh_cookie_if_needed(e):
                cookie_refreshed = True
                continue  # 立即重试，不等待

            if _is_non_retryable_bard_error(e):
                break

            # 指数退避重试
            if attempt < CONFIG["retry_attempts"] - 1:
                delay = CONFIG["retry_delay_sec"] * (2 ** attempt)  # 指数退避
                log(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
        finally:
            _release_proxy_for_request()

    raise last_err


def generate(prompt: str, model_id: int, think_mode: int, file_refs: list = None, extra_fields: dict = None) -> str:
    """Non-streaming generation, preserving the original public string API."""
    return generate_with_metadata(prompt, model_id, think_mode, file_refs, extra_fields)["text"]


def generate_stream(prompt: str, model_id: int, think_mode: int, file_refs: list = None, extra_fields: dict = None):
    """Streaming generation via httpx with retry on connection failure.

    Supports built-in proxy pool with automatic failover.
    """
    stream_mode = str(CONFIG.get("stream_mode") or "auto").lower()
    chunk_chars = max(1, int(CONFIG.get("stream_chunk_chars") or 1))
    fake_delay = max(0, int(CONFIG.get("fake_stream_delay_ms") or 0)) / 1000
    if stream_mode == "fake" or (stream_mode in {"auto", "true"} and not HAS_HTTPX):
        text = generate(prompt, model_id, think_mode, file_refs, extra_fields)
        for i in range(0, len(text or ""), chunk_chars):
            yield text[i:i + chunk_chars]
            if fake_delay:
                time.sleep(fake_delay)
        return

    last_err = None
    cookie_refreshed = False
    for attempt in range(CONFIG["retry_attempts"]):
        proxy = None
        try:
            headers = _build_headers()
            proxy = _get_proxy_for_request()
            body = _build_payload(prompt, model_id, think_mode, file_refs, extra_fields)
            url = _get_url()
            # Reuse shared client when no specific proxy is needed (matches original
            # behaviour and preserves HTTP connection pooling).
            prev_text = ""
            if proxy:
                transport = httpx.HTTPTransport(proxy=proxy)
                client = httpx.Client(transport=transport, timeout=CONFIG["request_timeout_sec"], verify=True)
                _own_client = True
            else:
                client = _get_httpx_client()
                _own_client = False
            try:
                with client.stream("POST", url, content=body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        raise UpstreamError(f"Upstream HTTP {resp.status_code}", status_code=resp.status_code)
                    buf = ""
                    for chunk in resp.iter_text():
                        buf += chunk
                        if "BardErrorInfo" in buf:
                            bard_err = _extract_bard_error(buf)
                            if bard_err:
                                raise RuntimeError(f"Gemini upstream rejected request: BardErrorInfo [{bard_err.group(1)}]")
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            for t in _extract_texts_from_line(line):
                                if len(t) > len(prev_text):
                                    delta = clean_text(t[len(prev_text):], strip=False)
                                    if delta:
                                        yield delta
                                    prev_text = t
            finally:
                if _own_client:
                    try:
                        client.close()
                    except Exception:
                        pass

            # 成功，标记代理
            if is_proxy_enabled() and CONFIG.get("proxy_pool_enabled") and proxy:
                from .proxy_builtin import get_pool
                pool = get_pool()
                for node in pool.nodes:
                    if node.url == proxy:
                        pool.mark_success(node)
                        break
            return

        except Exception as e:
            last_err = e
            log(f"Stream attempt {attempt+1}/{CONFIG['retry_attempts']} failed: {e}")

            # 标记代理失败
            if is_proxy_enabled() and CONFIG.get("proxy_pool_enabled") and proxy:
                from .proxy_builtin import get_pool
                pool = get_pool()
                for node in pool.nodes:
                    if node.url == proxy:
                        pool.mark_failure(node)
                        break
            _release_proxy_for_request()

            if not cookie_refreshed and _refresh_cookie_if_needed(e):
                cookie_refreshed = True
                continue

            if _is_non_retryable_bard_error(e):
                break

            if attempt == 0:
                _bl_cache["bl"] = None
                _bl_cache["ts"] = 0

            if attempt < CONFIG["retry_attempts"] - 1:
                time.sleep(CONFIG["retry_delay_sec"])
        finally:
            _release_proxy_for_request()

    raise last_err
