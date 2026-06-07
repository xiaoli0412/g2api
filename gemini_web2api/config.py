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
    "cookie_file": None,
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
