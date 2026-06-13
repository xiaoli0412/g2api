"""Tests for admin cookie/proxy pool behavior."""
import json

from gemini_web2api.admin import add_cookie, get_next_cookie, remove_cookie


def test_admin_cookie_pool_extracts_sapisid():
    cookie = "SID=test_sid; SAPISID=test_sapisid; HSID=test_hsid"
    try:
        result = add_cookie(cookie, source="test")
        assert result["success"] is True
        selected_cookie, sapisid = get_next_cookie()
        assert selected_cookie == cookie
        assert sapisid == "test_sapisid"
    finally:
        remove_cookie(cookie_str=cookie)


def test_admin_proxy_import_and_health(monkeypatch, tmp_path):
    from gemini_web2api import proxy_builtin
    from gemini_web2api.admin import handle_admin_request
    from gemini_web2api.config import CONFIG

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
        "proxies": list(CONFIG.get("proxies") or []),
        "proxy_subscriptions": list(CONFIG.get("proxy_subscriptions") or []),
        "proxy_import_sources": CONFIG.get("proxy_import_sources"),
    }
    proxy_builtin._global_pool = proxy_builtin.ProxyPool()
    try:
        payload, status = handle_admin_request(
            "/admin/proxy/import",
            "POST",
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
        assert payload["success"] is True
        assert payload["result"]["added"] == 2
        assert payload["result"]["duplicates"] == 1
        assert proxy_builtin.get_proxy_url() is None
        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["proxy_pool_enabled"] is True
        assert persisted["proxy_import_sources"]["providers"]["http://127.0.0.1:9001"] == "vendor-a"

        health, status = handle_admin_request("/admin/proxy/health", "GET")
        assert status == 200
        assert health["health"]["total_nodes"] == 2
        assert health["health"]["available_nodes"] == 0
        assert health["health"]["statuses"]["checking"] == 2
    finally:
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)


def test_admin_accounts_can_bind_proxy(monkeypatch, tmp_path):
    from gemini_web2api.admin import handle_admin_request
    from gemini_web2api.config import CONFIG

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))

    old_accounts = list(CONFIG.get("accounts") or [])
    old_bindings = list(CONFIG.get("proxy_account_bindings") or [])
    CONFIG["accounts"] = []
    CONFIG["proxy_account_bindings"] = []
    try:
        payload, status = handle_admin_request(
            "/admin/accounts/u%2F1/bind-proxy",
            "POST",
            {"label": "work", "proxy": "node-1", "cookie_file": "cookies/work.txt"},
        )

        assert status == 200
        assert payload["success"] is True
        assert CONFIG["accounts"][0]["id"] == "u/1"
        assert CONFIG["accounts"][0]["primary_proxy"] == "node-1"
        assert CONFIG["proxy_account_bindings"][0]["account_id"] == "u/1"
        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["accounts"][0]["primary_proxy"] == "node-1"
        assert persisted["proxy_account_bindings"][0]["primary_proxy"] == "node-1"
    finally:
        CONFIG["accounts"] = old_accounts
        CONFIG["proxy_account_bindings"] = old_bindings


def test_admin_account_binding_preserves_existing_account_fields(monkeypatch, tmp_path):
    from gemini_web2api.admin import handle_admin_request
    from gemini_web2api.config import CONFIG

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))

    old_accounts = list(CONFIG.get("accounts") or [])
    old_bindings = list(CONFIG.get("proxy_account_bindings") or [])
    CONFIG["accounts"] = [{
        "id": "u/1",
        "label": "existing",
        "cookie_file": "cookies/existing.txt",
        "fallback_group": "Pinned",
        "enabled": False,
    }]
    CONFIG["proxy_account_bindings"] = []
    try:
        payload, status = handle_admin_request(
            "/admin/accounts/u%2F1/bind-proxy",
            "POST",
            {"proxy": "node-2"},
        )

        assert status == 200
        assert payload["account"]["label"] == "existing"
        assert payload["account"]["cookie_file"] == "cookies/existing.txt"
        assert payload["account"]["fallback_group"] == "Pinned"
        assert payload["account"]["enabled"] is False
        assert payload["account"]["primary_proxy"] == "node-2"
    finally:
        CONFIG["accounts"] = old_accounts
        CONFIG["proxy_account_bindings"] = old_bindings


def test_admin_proxy_group_selection_is_persisted(monkeypatch, tmp_path):
    from gemini_web2api import proxy_builtin
    from gemini_web2api.admin import handle_admin_request
    from gemini_web2api.config import CONFIG
    from gemini_web2api.proxy_builtin import ProxyNode, ProxyType

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_group_selections": CONFIG.get("proxy_group_selections"),
    }
    pool = proxy_builtin.ProxyPool()
    pool.add(ProxyNode("a", ProxyType.HTTP, "a.example.test", 8001))
    pool.configure_service_routing(groups=[{"name": "GLOBAL", "type": "select", "proxies": ["*"]}])
    proxy_builtin._global_pool = pool
    CONFIG["proxy_group_selections"] = {}
    try:
        payload, status = handle_admin_request(
            "/admin/proxy/groups/GLOBAL/select",
            "POST",
            {"proxy": "a"},
        )

        assert status == 200
        assert payload["success"] is True
        assert CONFIG["proxy_group_selections"]["GLOBAL"] == "a"
        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["proxy_group_selections"]["GLOBAL"] == "a"
    finally:
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)
