"""End-to-end HTTP checks for proxy workbench routes."""

import json
import socket
import threading
import urllib.request

from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _json_request(url, payload=None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_proxy_import_health_status_and_account_binding_http_routes(monkeypatch, tmp_path):
    from gemini_web2api import proxy_builtin

    port = _free_port()
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))

    old_pool = proxy_builtin._global_pool
    old_config = {
        key: CONFIG.get(key)
        for key in (
            "api_keys",
            "host",
            "port",
            "proxy_pool_enabled",
            "proxies",
            "proxy_subscriptions",
            "proxy_import_sources",
            "accounts",
            "proxy_account_bindings",
        )
    }
    proxy_builtin._global_pool = proxy_builtin.ProxyPool()
    CONFIG["api_keys"] = []
    CONFIG["host"] = "127.0.0.1"
    CONFIG["port"] = port
    CONFIG["proxy_pool_enabled"] = False
    CONFIG["proxies"] = []
    CONFIG["proxy_subscriptions"] = []
    CONFIG["proxy_import_sources"] = {}
    CONFIG["accounts"] = []
    CONFIG["proxy_account_bindings"] = []

    monkeypatch.setattr(
        "gemini_web2api.proxy_builtin.check_pool_health",
        lambda **kwargs: {"checked": len(proxy_builtin.get_pool().nodes), "only_stale": kwargs.get("only_stale")},
    )

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, imported = _json_request(
            f"http://127.0.0.1:{port}/admin/proxy/import",
            {
                "provider": "vendor-a",
                "direct_links": [
                    "http://127.0.0.1:9001",
                    "http://127.0.0.1:9001",
                    "socks5://127.0.0.1:9002",
                ],
            },
        )
        assert status == 200
        assert imported["success"] is True
        assert imported["result"]["added"] == 2
        assert imported["result"]["duplicates"] == 1

        status, proxy_status = _json_request(f"http://127.0.0.1:{port}/api/proxy/status")
        assert status == 200
        assert proxy_status["enabled"] is True
        assert proxy_status["runtime"]["total_nodes"] == 2

        status, health = _json_request(
            f"http://127.0.0.1:{port}/admin/proxy/test-all",
            {"only_stale": True},
        )
        assert status == 200
        assert health["success"] is True
        assert health["result"]["checked"] == 2
        assert health["result"]["only_stale"] is True

        status, account = _json_request(
            f"http://127.0.0.1:{port}/admin/accounts/u%2F1/bind-proxy",
            {"primary_proxy": "http://127.0.0.1:9001", "cookie_file": "cookies/u1.txt"},
        )
        assert status == 200
        assert account["success"] is True
        assert account["account"]["id"] == "u/1"
        assert account["account"]["primary_proxy"] == "http://127.0.0.1:9001"
        assert CONFIG["proxy_account_bindings"][0]["account_id"] == "u/1"

        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["proxy_pool_enabled"] is True
        assert persisted["proxy_import_sources"]["providers"]["http://127.0.0.1:9001"] == "vendor-a"
        assert persisted["accounts"][0]["cookie_file"] == "cookies/u1.txt"
    finally:
        server.shutdown()
        server.server_close()
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_config)

