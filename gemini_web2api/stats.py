"""Statistics tracking: logs, usage records, token counts, request counts."""
import time
import threading
import json
from collections import defaultdict, deque

_lock = threading.Lock()
_logs = deque(maxlen=2000)
_requests = deque(maxlen=10000)
_model_stats = defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "errors": 0})
_hourly_stats = defaultdict(lambda: {"requests": 0, "tokens": 0})
_daily_stats = defaultdict(lambda: {"requests": 0, "tokens": 0})
_start_time = time.time()


def log_request(model: str, prompt_tokens: int, completion_tokens: int, status: str = "ok", error: str = ""):
    """Record a completed request."""
    now = time.time()
    hour_key = time.strftime("%Y-%m-%d %H:00", time.localtime(now))
    day_key = time.strftime("%Y-%m-%d", time.localtime(now))
    total = prompt_tokens + completion_tokens
    with _lock:
        _requests.append({
            "time": now,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
            "status": status,
            "error": error,
        })
        ms = _model_stats[model]
        ms["requests"] += 1
        ms["prompt_tokens"] += prompt_tokens
        ms["completion_tokens"] += completion_tokens
        ms["total_tokens"] += total
        if status != "ok":
            ms["errors"] += 1
        _hourly_stats[hour_key]["requests"] += 1
        _hourly_stats[hour_key]["tokens"] += total
        _daily_stats[day_key]["requests"] += 1
        _daily_stats[day_key]["tokens"] += total


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

        recent_logs = list(_logs)[-100:]
        recent_logs.reverse()

        recent_requests = list(_requests)[-50:]
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
                "avg_tokens_per_request": round(total_tokens / max(total_requests, 1), 1),
            },
            "model_stats": dict(_model_stats),
            "hourly_stats": [{"hour": h, **s} for h, s in hourly],
            "daily_stats": [{"day": d, **s} for d, s in daily],
            "recent_logs": recent_logs,
            "recent_requests": recent_requests,
        }


def get_api_data() -> dict:
    """Return dashboard data as JSON-serializable dict for API endpoint."""
    return get_dashboard_data()
