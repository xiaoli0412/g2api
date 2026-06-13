"""Multimodal: Scotty resumable upload for Gemini file input (images, video, audio, documents)."""
import urllib.request
import urllib.parse
import time
import re
import os

from .config import CONFIG
from .gemini import get_request_cookie, make_sapisidhash, _account_prefix, _get_ssl_ctx, log

MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
    ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".csv": "text/csv", ".json": "application/json",
    ".xml": "application/xml", ".md": "text/markdown",
    ".py": "text/x-python", ".js": "text/javascript", ".html": "text/html",
}


def _get_page_tokens() -> dict:
    """Fetch WIZ_global_data tokens from Gemini page (Push-ID, X-Client-Pctx)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://gemini.google.com{_account_prefix()}/app",
    }
    cookie_str, sapisid = get_request_cookie()
    if cookie_str:
        headers["Cookie"] = cookie_str
    if sapisid:
        headers["Authorization"] = make_sapisidhash(sapisid)
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy") if CONFIG.get("proxy_enabled", True) else None
    try:
        req = urllib.request.Request(f"https://gemini.google.com{_account_prefix()}/app", headers=headers)
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=ctx)
            )
            resp = opener.open(req, timeout=30)
        else:
            resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        html = resp.read().decode()
        tokens = {}
        for key, pattern in [
            ("push_id", r'"qKIAYe":"([^"]+)"'),
            ("pctx", r'"Ylro7b":"([^"]+)"'),
            ("at", r'"thykhd":"([^"]+)"'),
        ]:
            m = re.search(pattern, html)
            if m:
                tokens[key] = m.group(1)
        return tokens
    except Exception as e:
        log(f"Page token fetch failed: {e}")
        return {}


_page_tokens_cache = {"tokens": {}, "ts": 0}


def _cached_page_tokens(force: bool = False) -> dict:
    now = time.time()
    if force or now - _page_tokens_cache["ts"] > 600:
        _page_tokens_cache["tokens"] = _get_page_tokens()
        _page_tokens_cache["ts"] = now
    return _page_tokens_cache["tokens"]


def upload_file(file_bytes: bytes, filename: str = "file", mime_type: str = None) -> str:
    """Upload file via Scotty resumable upload. Returns file reference path.
    
    Supports: images, video, audio, documents.
    """
    if not mime_type:
        ext = os.path.splitext(filename)[1].lower()
        mime_type = MIME_MAP.get(ext, "application/octet-stream")

    last_error = None
    attempts = max(1, int(CONFIG.get("upload_retry_attempts") or CONFIG.get("retry_attempts") or 3))
    for attempt in range(attempts):
        try:
            return _upload_file_once(file_bytes, filename, mime_type, force_tokens=attempt > 0)
        except Exception as exc:
            last_error = exc
            log(f"File upload attempt {attempt + 1}/{attempts} failed: {exc}")
            if attempt < attempts - 1:
                time.sleep(min(2 + attempt, 5))
    raise last_error


def _upload_file_once(file_bytes: bytes, filename: str, mime_type: str, force_tokens: bool = False) -> str:
    tokens = _cached_page_tokens(force=force_tokens)
    push_id = tokens.get("push_id", "feeds/mcudyrk2a4khkz")
    pctx = tokens.get("pctx", "CgcSBWjK7pYx")

    cookie_str, sapisid = get_request_cookie()
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy") if CONFIG.get("proxy_enabled", True) else None
    timeout = max(60, int(CONFIG.get("request_timeout_sec") or 180))

    # Step 1: Initiate resumable upload
    start_headers = {
        "Push-ID": push_id,
        "X-Tenant-Id": "bard-storage",
        "X-Client-Pctx": pctx,
        "X-Goog-Upload-Header-Content-Length": str(len(file_bytes)),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if cookie_str:
        start_headers["Cookie"] = cookie_str
    if sapisid:
        start_headers["Authorization"] = make_sapisidhash(sapisid)

    start_url = "https://content-push.googleapis.com/upload/"
    req = urllib.request.Request(start_url, data=b"", headers=start_headers, method="POST")

    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=ctx)
        )
        resp = opener.open(req, timeout=min(timeout, 120))
    else:
        resp = urllib.request.urlopen(req, context=ctx, timeout=min(timeout, 120))

    upload_url = resp.headers.get("X-Goog-Upload-URL") or resp.headers.get("x-goog-upload-url")
    if not upload_url:
        raise RuntimeError(f"No upload URL in response headers: {dict(resp.headers)}")

    log(f"Upload session started: {upload_url[:80]}...")

    # Step 2: Upload file data + finalize
    upload_headers = {
        "X-Goog-Upload-Command": "upload, finalize",
        "X-Goog-Upload-Offset": "0",
        "Content-Type": "application/octet-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    req2 = urllib.request.Request(upload_url, data=file_bytes, headers=upload_headers, method="POST")
    if proxy:
        resp2 = opener.open(req2, timeout=timeout)
    else:
        resp2 = urllib.request.urlopen(req2, context=ctx, timeout=timeout)

    file_ref = resp2.read().decode().strip()
    if not file_ref or not file_ref.startswith("/"):
        raise RuntimeError(f"Invalid file reference: {file_ref[:100]}")

    log(f"File uploaded: {filename} ({mime_type}, {len(file_bytes)} bytes) -> {file_ref[:50]}...")
    return file_ref


# Legacy aliases
upload_image = upload_file


def fetch_file_bytes(url: str) -> bytes:
    """Fetch file from URL, using configured proxy if available."""
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy") if CONFIG.get("proxy_enabled", True) else None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=ctx)
            )
            resp = opener.open(req, timeout=30)
        else:
            resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        return resp.read()
    except Exception as e:
        log(f"File fetch failed: {e}")
        return b""


# Legacy alias
fetch_image_bytes = fetch_file_bytes
