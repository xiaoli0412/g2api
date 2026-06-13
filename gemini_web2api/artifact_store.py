"""Local materialization for generated media and file artifacts."""
import base64
import mimetypes
import os
import re
import time
import urllib.parse
import urllib.request
import uuid

from .config import CONFIG
from .gemini import (
    _get_ssl_ctx,
    get_current_request_cookie,
    get_current_request_proxy,
    make_sapisidhash,
    log,
    release_current_request_proxy,
    resolve_generated_image_download_url,
)


DEFAULT_MAX_BYTES = 250 * 1024 * 1024


def artifact_root() -> str:
    root = CONFIG.get("artifact_dir") or os.path.join(os.getcwd(), "output", "generated_artifacts")
    os.makedirs(root, exist_ok=True)
    return root


def _safe_filename(name: str, default_ext: str = "") -> str:
    name = os.path.basename((name or "").strip()) or f"artifact{default_ext}"
    name = re.sub(r"[^0-9A-Za-z._-]+", "_", name)
    if default_ext and not os.path.splitext(name)[1]:
        name += default_ext
    return name[:160] or f"artifact{default_ext}"


def _ext_from_mime(mime_type: str) -> str:
    if not mime_type:
        return ""
    mime_type = mime_type.split(";", 1)[0].strip().lower()
    return mimetypes.guess_extension(mime_type) or {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "video/mp4": ".mp4",
        "image/jpeg": ".jpg",
    }.get(mime_type, "")


def _ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url or "").path
    ext = os.path.splitext(path)[1].lower()
    if 1 < len(ext) <= 10:
        return ext
    return ""


def _write_artifact(data: bytes, filename: str, mime_type: str = "") -> dict:
    ext = _ext_from_mime(mime_type)
    filename = _safe_filename(filename, ext)
    unique = f"{int(time.time())}_{uuid.uuid4().hex[:10]}_{filename}"
    path = os.path.join(artifact_root(), unique)
    with open(path, "wb") as handle:
        handle.write(data)
    return {
        "status": "saved",
        "filename": filename,
        "local_path": os.path.abspath(path),
        "download_url": f"/artifacts/{urllib.parse.quote(unique)}",
        "bytes": len(data),
        "mime_type": mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
    }


def _read_limited(response, max_bytes: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = response.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError(f"artifact exceeds max size {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _download_url(url: str, max_bytes: int = None) -> tuple[bytes, str]:
    max_bytes = max_bytes or int(CONFIG.get("artifact_max_bytes") or DEFAULT_MAX_BYTES)
    auth_user = CONFIG.get("auth_user")
    referer_path = f"/u/{auth_user}/app" if auth_user not in (None, "") else "/app"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Origin": "https://gemini.google.com",
        "Referer": f"https://gemini.google.com{referer_path}",
    }
    if auth_user not in (None, ""):
        headers["X-Goog-AuthUser"] = str(auth_user)
    cookie_str, sapisid = get_current_request_cookie()
    attempts = []
    if cookie_str:
        auth_headers = dict(headers)
        auth_headers["Cookie"] = cookie_str
        if sapisid:
            auth_headers["Authorization"] = make_sapisidhash(sapisid)
        attempts.append(auth_headers)
    attempts.append(headers)
    last_error = None
    proxy, leased_proxy = get_current_request_proxy(lease_if_missing=True)
    try:
        for item_headers in attempts:
            try:
                req = urllib.request.Request(url, headers=item_headers)
                if proxy:
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                        urllib.request.HTTPSHandler(context=_get_ssl_ctx()),
                    )
                    response_ctx = opener.open(req, timeout=90)
                else:
                    response_ctx = urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=90)
                with response_ctx as response:
                    mime_type = response.headers.get("Content-Type", "").split(";", 1)[0]
                    return _read_limited(response, max_bytes), mime_type
            except Exception as exc:
                last_error = exc
    finally:
        if leased_proxy:
            release_current_request_proxy()
    raise RuntimeError(str(last_error))


def _is_placeholder_media_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url or "")
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return host == "googleusercontent.com" and path.startswith((
        "/image_generation_content/",
        "/video_generation_content/",
        "/audio_generation_content/",
        "/card_content/",
    ))


def _materialize_data_url(url: str, filename: str) -> dict:
    header, b64data = url.split(",", 1)
    mime_type = header[5:].split(";", 1)[0]
    data = base64.b64decode(b64data)
    return _write_artifact(data, filename, mime_type)


def materialize_media_item(item: dict) -> dict:
    result = dict(item or {})
    url = result.get("url", "")
    kind = result.get("kind") or "file"
    result.setdefault("source_url", url)
    if not url:
        result.setdefault("materialized", {"status": "unresolved", "reason": "missing_url"})
        return result
    if _is_placeholder_media_url(url):
        result["materialized"] = {
            "status": "unresolved",
            "reason": "placeholder_url_not_downloadable",
            "note": "Gemini Web returned a UI placeholder URL, not a fetchable media file.",
        }
        return result
    try:
        if url.startswith("data:"):
            saved = _materialize_data_url(url, f"generated-{kind}")
        else:
            if result.get("type") == "gemini_generated_image":
                resolved = resolve_generated_image_download_url(result)
                if resolved:
                    result["resolved_url"] = resolved
                    url = resolved
            data, mime_type = _download_url(url)
            filename = (
                result.get("name")
                or os.path.basename(urllib.parse.urlparse(url).path)
                or f"generated-{kind}{_ext_from_url(url)}"
            )
            saved = _write_artifact(data, filename, mime_type)
        result["materialized"] = saved
        result["download_url"] = saved["download_url"]
        result["local_path"] = saved["local_path"]
        result["url"] = saved["download_url"]
    except Exception as exc:
        log(f"Artifact materialization failed: {exc}")
        result["materialized"] = {"status": "failed", "reason": str(exc)[:240]}
    return result


def materialize_artifact_item(item: dict) -> dict:
    result = dict(item or {})
    artifact_type = result.get("type", "")
    if artifact_type == "file":
        url = result.get("url", "")
        if not url:
            result["materialized"] = {
                "status": "unresolved",
                "reason": "file tag did not include a downloadable URL",
            }
            return result
        return materialize_media_item({"kind": "file", "url": url, "alt": result.get("name", "")})

    content = result.get("content")
    if not content:
        result["materialized"] = {"status": "unresolved", "reason": "missing_content"}
        return result
    language = (result.get("language") or "txt").lower()
    ext = {
        "html": ".html",
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "json": ".json",
        "markdown": ".md",
        "md": ".md",
        "css": ".css",
    }.get(language, ".txt")
    saved = _write_artifact(content.encode("utf-8"), f"generated-{language}{ext}", "text/plain")
    result["materialized"] = saved
    result["download_url"] = saved["download_url"]
    result["local_path"] = saved["local_path"]
    return result


def materialize_response_files(media=None, artifacts=None) -> list:
    files = []
    seen = set()
    for item in media or []:
        key = ((item or {}).get("kind"), (item or {}).get("url"))
        if key in seen:
            continue
        seen.add(key)
        materialized = materialize_media_item(item)
        if materialized.get("materialized"):
            files.append(materialized)
    for item in artifacts or []:
        materialized = materialize_artifact_item(item)
        if materialized.get("materialized"):
            files.append(materialized)
    return files


def resolve_artifact_path(name: str) -> str:
    safe = os.path.basename(urllib.parse.unquote(name or ""))
    path = os.path.abspath(os.path.join(artifact_root(), safe))
    root = os.path.abspath(artifact_root())
    if not path.startswith(root + os.sep):
        return ""
    return path if os.path.exists(path) else ""
