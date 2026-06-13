"""Configuration management."""
import json
import os

DEFAULT_CONFIG = {
    "port": 8081,
    "host": "0.0.0.0",
    "retry_attempts": 3,
    "retry_delay_sec": 2,
    "request_timeout_sec": 180,
    "gemini_bl": "boq_assistant-bard-web-server_20260525.09_p0",
    "auth_user": None,
    "xsrf_token": None,
    "default_model": "gemini-3.5-flash",
    "log_requests": True,
    "capture_request_bodies": True,
    "capture_response_bodies": True,
    "log_body_limit_chars": 65536,
    "log_upstream_raw": False,
    "dashboard_local_bypass": True,
    "expose_experimental_models": False,
    "expose_web_feature_models": True,
    "stream_mode": "auto",  # auto, true, fake
    "fake_stream_delay_ms": 10,
    "stream_chunk_chars": 1,
    "upload_retry_attempts": 3,
    "cookie_file": None,
    "proxy_enabled": True,
    "proxy": None,
    "api_keys": [],
    # Cookie rotation settings
    "cookie_files": [],  # List of cookie files for rotation
    "cookie_rotation": False,  # Enable cookie rotation
    "cookie_rotation_interval": 10,  # Requests before rotation
    # Proxy rotation settings
    "proxies": [],  # List of proxies for rotation
    "proxy_rotation": False,  # Enable proxy rotation
    "proxy_rotation_interval": 10,  # Requests before rotation
    # Rate limiting
    "rate_limit_per_minute": 30,  # Max requests per minute per cookie
    "rate_limit_delay": 2,  # Delay between requests in seconds

    # ─── Proxy Pool Settings ─────────────────────────────────────
    "proxy_pool_enabled": False,  # Enable proxy pool
    "proxy_subscriptions": [],  # Subscription URLs (Clash/V2Ray format)
    "proxy_pool_strategy": "round_robin",  # round_robin, random, fastest, least_used
    "proxy_pool_health_check": True,  # Enable health check
    "proxy_pool_health_check_interval": 300,  # Health check interval in seconds
    "proxy_pool_max_failures": 3,  # Max failures before marking unhealthy
    "proxy_pool_port_range_start": 10000,  # Local proxy port range start
    "proxy_pool_port_range_end": 20000,  # Local proxy port range end
    "proxy_pool_auto_update": True,  # Auto update subscriptions
    "proxy_pool_update_interval": 3600,  # Subscription update interval in seconds
    # Multi-process IP isolation
    "proxy_pool_isolate_by_process": True,  # Each process uses different IP

    # Proxy workbench: stable, lightweight routing and import policy
    "proxy_workbench_enabled": True,
    "proxy_import_sources": {
        "subscriptions": [],
        "direct_links": [],
    },
    "proxy_health_policy": {
        "require_healthy": True,
        "check_on_import": True,
        "background_check_enabled": True,
        "check_interval_seconds": 300,
        "status_ttl_seconds": 600,
        "probe_concurrency": 8,
        "probe_timeout_seconds": 8,
        "max_failures": 2,
        "cooldown_seconds": 120,
        "lightweight_mode": True,
    },
    "proxy_ui_preferences": {
        "view": "compact_list",
        "density": "compact",
        "sort": "health_then_delay",
    },
    "proxy_groups": [
        {
            "name": "GLOBAL",
            "type": "url-test",
            "providers": ["*"],
            "proxies": ["*"],
            "tolerance_ms": 150,
            "test_url": "http://httpbin.org/ip",
        },
        {
            "name": "Healthy",
            "type": "fallback",
            "providers": ["*"],
            "proxies": ["*"],
        },
    ],
    "proxy_group_selections": {},
    "proxy_account_bindings": [],
    "accounts": [],
    "anonymous_route_policy": {
        "enabled": True,
        "group": "GLOBAL",
        "strategy": "url-test",
        "max_concurrent_requests": 20,
        "max_concurrent_per_proxy": 2,
        "requests_per_minute_per_proxy": 30,
        "queue_max_size": 200,
        "cooldown_seconds": 120,
    },
    "account_route_policy": {
        "strategy": "sticky_account",
        "max_concurrent_per_account": 1,
        "fallback": "queue_then_fail",
    },
}

CONFIG = dict(DEFAULT_CONFIG)


def load_config(path: str = None):
    """Load config from JSON file."""
    if path and os.path.exists(path):
        with open(path) as f:
            CONFIG.update(json.load(f))
    return CONFIG


def find_config():
    """Search for config file in standard locations."""
    for p in ["./config.json", os.path.expanduser("~/.config/gemini-web2api/config.json")]:
        if os.path.exists(p):
            return p
    return None
