"""Statistics tracking: logs, usage records, token counts, request details."""
import json
import time
import uuid
import threading
from collections import defaultdict, deque

_lock = threading.Lock()
_logs = deque(maxlen=2000)
_requests = deque(maxlen=10000)
_model_stats = defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "errors": 0})
_model_category_stats = defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "errors": 0})
_protocol_stats = defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "errors": 0})
_hourly_stats = defaultdict(lambda: {"requests": 0, "tokens": 0})
_daily_stats = defaultdict(lambda: {"requests": 0, "tokens": 0})
_start_time = time.time()
_BODY_LIMIT = 65536
_SECRET_KEYS = {
    "authorization", "cookie", "cookies", "set-cookie", "sapisid", "xsrf_token",
    "api_key", "api_keys", "x-api-key", "password", "token", "access_token",
    "refresh_token", "proxy-authorization",
}


def _config_value(key: str, default):
    try:
        from .config import CONFIG
        return CONFIG.get(key, default)
    except Exception:
        return default


def _is_secret_key(key: str) -> bool:
    lower = str(key or "").lower()
    return lower in _SECRET_KEYS or lower.endswith("_cookie") or lower.endswith("_token")


def _truncate_text(value: str) -> dict | str:
    limit = int(_config_value("log_body_limit_chars", _BODY_LIMIT) or _BODY_LIMIT)
    if len(value) <= limit:
        return value
    return {
        "truncated": True,
        "limit": limit,
        "chars": len(value),
        "value": value[:limit],
    }


def _sanitize_payload(value, depth: int = 0):
    if depth > 8:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        try:
            return _truncate_text(value.decode("utf-8", errors="replace"))
        except Exception:
            return {"bytes": len(value), "value": "<binary>"}
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if _is_secret_key(key):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_payload(item, depth + 1)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_payload(item, depth + 1) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _mask_proxy_url(value: str) -> str:
    text = str(value or "")
    if not text or "@" not in text:
        return text
    scheme, rest = text.split("://", 1) if "://" in text else ("", text)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}" if scheme else f"***@{host}"


def estimate_tokens_from_text(text: str) -> int:
    """Cheap local estimate used for dashboards when upstream token usage is absent."""
    return max(0, len(text or "") // 4)


def _model_category(model: str) -> str:
    lower = (model or "").lower()
    if any(token in lower for token in ("nano-banana", "imagen", "image")):
        return "image"
    if any(token in lower for token in ("veo", "omni", "video")):
        return "video"
    if any(token in lower for token in ("lyria", "music")):
        return "music"
    if any(token in lower for token in ("tts", "speech", "audio")):
        return "audio"
    if "research" in lower:
        return "research"
    if "canvas" in lower:
        return "canvas"
    if "pro" in lower or "advanced" in lower:
        return "pro"
    if "thinking" in lower:
        return "thinking"
    if "flash" in lower:
        return "flash"
    if "auto" in lower:
        return "auto"
    return "other"


def log_request(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    status: str = "ok",
    error: str = "",
    *,
    endpoint: str = "",
    method: str = "POST",
    request_body=None,
    response_body=None,
    duration_ms: float | None = None,
    proxy: str = "",
    request_id: str = "",
    protocol: str = "",
    stream: bool = False,
    trace=None,
):
    """Record a completed request."""
    now = time.time()
    hour_key = time.strftime("%Y-%m-%d %H:00", time.localtime(now))
    day_key = time.strftime("%Y-%m-%d", time.localtime(now))
    total = prompt_tokens + completion_tokens
    rid = request_id or f"req_{uuid.uuid4().hex[:16]}"
    category = _model_category(model)
    protocol_key = protocol or endpoint or "unknown"
    with _lock:
        _requests.append({
            "id": rid,
            "time": now,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "endpoint": endpoint,
            "method": method,
            "protocol": protocol,
            "model": model,
            "model_category": category,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
            "status": status,
            "error": error,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "proxy": _mask_proxy_url(proxy),
            "stream": bool(stream),
            "request_body": _sanitize_payload(request_body) if _config_value("capture_request_bodies", True) else "<disabled>",
            "response_body": _sanitize_payload(response_body) if _config_value("capture_response_bodies", True) else "<disabled>",
            "trace": _sanitize_payload(trace),
        })
        ms = _model_stats[model]
        ms["requests"] += 1
        ms["prompt_tokens"] += prompt_tokens
        ms["completion_tokens"] += completion_tokens
        ms["total_tokens"] += total
        if status != "ok":
            ms["errors"] += 1
        cat = _model_category_stats[category]
        cat["requests"] += 1
        cat["prompt_tokens"] += prompt_tokens
        cat["completion_tokens"] += completion_tokens
        cat["total_tokens"] += total
        proto = _protocol_stats[protocol_key]
        proto["requests"] += 1
        proto["prompt_tokens"] += prompt_tokens
        proto["completion_tokens"] += completion_tokens
        proto["total_tokens"] += total
        if status != "ok":
            cat["errors"] += 1
            proto["errors"] += 1
        _hourly_stats[hour_key]["requests"] += 1
        _hourly_stats[hour_key]["tokens"] += total
        _daily_stats[day_key]["requests"] += 1
        _daily_stats[day_key]["tokens"] += total
    return rid


def add_log(msg: str, level: str = "info"):
    """Add a log entry."""
    with _lock:
        _logs.append({
            "time": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": msg,
        })


def get_dashboard_data() -> dict:
    """Return all dashboard data."""
    with _lock:
        uptime = time.time() - _start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        total_requests = sum(ms["requests"] for ms in _model_stats.values())
        total_prompt_tokens = sum(ms["prompt_tokens"] for ms in _model_stats.values())
        total_completion_tokens = sum(ms["completion_tokens"] for ms in _model_stats.values())
        total_tokens = sum(ms["total_tokens"] for ms in _model_stats.values())
        total_errors = sum(ms["errors"] for ms in _model_stats.values())
        total_success = max(0, total_requests - total_errors)
        request_list = list(_requests)
        completed_latencies = [r["duration_ms"] for r in request_list if isinstance(r.get("duration_ms"), (int, float))]
        avg_latency_ms = round(sum(completed_latencies) / max(len(completed_latencies), 1), 1)
        one_minute_ago = time.time() - 60
        requests_per_minute = sum(1 for r in request_list if r.get("time", 0) >= one_minute_ago)
        last_request = request_list[-1] if request_list else None

        recent_logs = list(_logs)[-100:]
        recent_logs.reverse()

        recent_requests = request_list[-100:]
        recent_requests.reverse()

        hourly = sorted(_hourly_stats.items())[-24:]
        daily = sorted(_daily_stats.items())[-30:]

        return {
            "uptime": f"{hours}h {minutes}m {seconds}s",
            "uptime_seconds": uptime,
            "summary": {
                "total_requests": total_requests,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "total_errors": total_errors,
                "total_success": total_success,
                "success_rate": round((total_success / max(total_requests, 1)) * 100, 1),
                "avg_tokens_per_request": round(total_tokens / max(total_requests, 1), 1),
                "avg_latency_ms": avg_latency_ms,
                "requests_per_minute": requests_per_minute,
                "last_request_at": last_request.get("time_str") if last_request else "",
            },
            "model_stats": dict(_model_stats),
            "model_category_stats": dict(_model_category_stats),
            "protocol_stats": dict(_protocol_stats),
            "hourly_stats": [{"hour": h, **s} for h, s in hourly],
            "daily_stats": [{"day": d, **s} for d, s in daily],
            "recent_logs": recent_logs,
            "recent_requests": recent_requests,
        }


def get_api_data() -> dict:
    """Return dashboard data as JSON-serializable dict for API endpoint."""
    return get_dashboard_data()


def get_request_detail(request_id: str) -> dict | None:
    """Return one recorded request by ID."""
    with _lock:
        for request in reversed(_requests):
            if request.get("id") == request_id:
                return dict(request)
    return None
