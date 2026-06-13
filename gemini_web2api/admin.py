"""Admin API and Token Pool Management.

Inspired by HelloGML admin-panel.ts and index.ts patterns:
- API Key management (add/list/delete)
- Cookie pool with round-robin rotation
- Proxy pool management
- Token health checking
- Statistics dashboard API
"""
import json
import time
import os
import threading
import urllib.request
import urllib.parse
from .config import CONFIG
from .cookies import normalize_cookie_input, _extract_sapisid
from .stats import get_dashboard_data, get_request_detail, add_log

_lock = threading.Lock()
_config_write_lock = threading.Lock()
_api_keys = set()
_cookie_pool = []
_cookie_index = 0
_proxy_pool = []
_proxy_index = 0
_request_count = 0


def init_admin():
    global _api_keys, _cookie_pool
    keys = CONFIG.get("api_keys", [])
    _api_keys = set(keys) if keys else set()
    _cookie_pool = []
    cookie_paths = []
    cookie_file = CONFIG.get("cookie_file")
    if cookie_file:
        cookie_paths.append(cookie_file)
    cookie_paths.extend(CONFIG.get("cookie_files") or [])
    for path in cookie_paths:
        if path and os.path.exists(path):
            _load_cookies_from_file(path)


def _append_cookie(cookie_str, sapisid="", source="file", file_path=None):
    cookie_str, parsed_sapisid = normalize_cookie_input(cookie_str)
    if not cookie_str:
        return
    sapisid = sapisid or parsed_sapisid or _extract_sapisid(cookie_str)
    for c in _cookie_pool:
        if c.get("cookie") == cookie_str:
            return
    _cookie_pool.append({
        "cookie": cookie_str,
        "sapisid": sapisid,
        "file": file_path,
        "source": source,
        "healthy": True,
        "failures": 0,
        "added_at": time.time(),
    })


def _load_cookies_from_file(path):
    global _cookie_pool
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()
        _append_cookie(content, source="file", file_path=path)
    except Exception as e:
        add_log(f"Failed to load cookies from {path}: {e}", "error")


def verify_api_key(key):
    if not _api_keys:
        return True
    return key in _api_keys


def add_api_key(key):
    with _lock:
        _api_keys.add(key)
        _save_config_keys()
        add_log(f"API key added: {key[:8]}...")


def remove_api_key(key):
    with _lock:
        _api_keys.discard(key)
        _save_config_keys()
        add_log(f"API key removed: {key[:8]}...")


def list_api_keys():
    return [{"key": k, "preview": k[:8] + "****" if len(k) > 8 else k} for k in _api_keys]


def _save_config_fields(keys):
    try:
        from .config import find_config
        cfg_path = find_config() or "config.json"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        for key in keys:
            cfg[key] = CONFIG.get(key)
        directory = os.path.dirname(os.path.abspath(cfg_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = f"{cfg_path}.tmp"
        with _config_write_lock:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, cfg_path)
        return True
    except Exception as e:
        add_log(f"Failed to save config fields {list(keys)}: {e}", "error")
        return False


def _save_config_keys():
    try:
        CONFIG["api_keys"] = list(_api_keys)
        _save_config_fields(["api_keys"])
    except Exception as e:
        add_log(f"Failed to save config keys: {e}", "error")


def get_next_cookie():
    global _cookie_index, _request_count
    with _lock:
        if not _cookie_pool:
            return None, None
        _request_count += 1
        healthy = [c for c in _cookie_pool if c.get("healthy", True)]
        if not healthy:
            for c in _cookie_pool:
                c["healthy"] = True
                c["failures"] = 0
            healthy = _cookie_pool
        cookie = healthy[_cookie_index % len(healthy)]
        _cookie_index += 1
        return cookie.get("cookie", ""), cookie.get("sapisid", "")


def mark_cookie_failure(cookie_str):
    with _lock:
        for c in _cookie_pool:
            if c.get("cookie") == cookie_str:
                c["failures"] = c.get("failures", 0) + 1
                if c["failures"] >= 3:
                    c["healthy"] = False
                    add_log(f"Cookie marked unhealthy after {c['failures']} failures", "warning")
                break


def mark_cookie_success(cookie_str):
    with _lock:
        for c in _cookie_pool:
            if c.get("cookie") == cookie_str:
                c["failures"] = 0
                c["healthy"] = True
                break


def add_cookie(cookie_str, sapisid="", source="api"):
    with _lock:
        cookie_str, parsed_sapisid = normalize_cookie_input(cookie_str)
        for c in _cookie_pool:
            if c.get("cookie") == cookie_str:
                return {"success": False, "error": "Cookie already exists"}
        entry = {
            "cookie": cookie_str,
            "sapisid": sapisid or parsed_sapisid or _extract_sapisid(cookie_str),
            "source": source,
            "healthy": True,
            "failures": 0,
            "added_at": time.time(),
        }
        _cookie_pool.append(entry)
        add_log(f"Cookie added to pool (source: {source})")
        return {"success": True, "pool_size": len(_cookie_pool)}


def remove_cookie(index=None, cookie_str=None):
    with _lock:
        if cookie_str:
            _cookie_pool[:] = [c for c in _cookie_pool if c.get("cookie") != cookie_str]
        elif index is not None and 0 <= index < len(_cookie_pool):
            _cookie_pool.pop(index)
        add_log(f"Cookie removed from pool")
        return {"success": True, "pool_size": len(_cookie_pool)}


def list_cookies():
    result = []
    for i, c in enumerate(_cookie_pool):
        cookie = c.get("cookie", "")
        result.append({
            "index": i,
            "preview": cookie[:16] + "****" + cookie[-8:] if len(cookie) > 24 else cookie,
            "healthy": c.get("healthy", True),
            "failures": c.get("failures", 0),
            "source": c.get("source", "unknown"),
        })
    return result


def get_next_proxy():
    global _proxy_index
    with _lock:
        if not CONFIG.get("proxy_enabled", True):
            return None
        proxies = CONFIG.get("proxies", [])
        if not proxies:
            return CONFIG.get("proxy")
        _proxy_index += 1
        return proxies[_proxy_index % len(proxies)]


def get_admin_stats():
    dashboard = get_dashboard_data()
    return {
        "api_keys_count": len(_api_keys),
        "cookie_pool_size": len(_cookie_pool),
        "healthy_cookies": sum(1 for c in _cookie_pool if c.get("healthy", True)),
        "proxy_count": len(CONFIG.get("proxies", [])),
        "request_count": _request_count,
        "uptime": dashboard.get("uptime", "N/A"),
        "total_requests": dashboard.get("summary", {}).get("total_requests", 0),
        "total_tokens": dashboard.get("summary", {}).get("total_tokens", 0),
    }


def _mask_proxy_url(url: str) -> str:
    if not url:
        return ""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("", url)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}" if scheme else f"***@{host}"


def get_proxy_status():
    """Return configured proxy state plus built-in pool runtime health."""
    master_enabled = bool(CONFIG.get("proxy_enabled", True))
    pool_enabled = bool(CONFIG.get("proxy_pool_enabled"))
    pool = {
        "enabled": master_enabled and pool_enabled,
        "proxy_enabled": master_enabled,
        "pool_enabled": pool_enabled,
        "strategy": CONFIG.get("proxy_pool_strategy", "round_robin"),
        "rotation_enabled": bool(CONFIG.get("proxy_rotation")),
        "rotation_interval": CONFIG.get("proxy_rotation_interval", 10),
        "configured_proxy": _mask_proxy_url(CONFIG.get("proxy") or ""),
        "configured_nodes": len(CONFIG.get("proxies") or []),
        "subscriptions": len(CONFIG.get("proxy_subscriptions") or []),
        "runtime": {"total_nodes": 0, "healthy_nodes": 0, "nodes": []},
    }
    if master_enabled and pool_enabled:
        try:
            from .proxy_builtin import get_pool_status
            runtime = get_pool_status()
            runtime["nodes"] = [
                {**node, "url": _mask_proxy_url(
                    f"{node.get('type', 'http')}://{node.get('host', '')}:{node.get('port', '')}"
                )}
                for node in runtime.get("nodes", [])
            ]
            pool["runtime"] = runtime
        except Exception as e:
            pool["runtime_error"] = str(e)
    return pool


def _extend_config_list(key, values):
    values = [v for v in (values or []) if isinstance(v, str) and v.strip()]
    current = list(CONFIG.get(key) or [])
    seen = set(current)
    added = 0
    for value in values:
        value = value.strip()
        if value and value not in seen:
            current.append(value)
            seen.add(value)
            added += 1
    CONFIG[key] = current
    return added


def _merge_proxy_import_sources(subscriptions, direct_links, provider):
    sources = dict(CONFIG.get("proxy_import_sources") or {})
    providers = dict(sources.get("providers") or {})
    provider = (provider or "manual").strip() or "manual"

    def merge_list(name, values):
        current = [v for v in (sources.get(name) or []) if isinstance(v, str) and v.strip()]
        seen = set(current)
        for value in values or []:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if not value:
                continue
            if value not in seen:
                current.append(value)
                seen.add(value)
            providers[value] = provider
        sources[name] = current

    merge_list("subscriptions", subscriptions)
    merge_list("direct_links", direct_links)
    sources["providers"] = providers
    CONFIG["proxy_import_sources"] = sources


def _sync_proxy_account_bindings():
    bindings = []
    for account in CONFIG.get("accounts") or []:
        proxy = account.get("primary_proxy") or account.get("proxy")
        if not account.get("id") or not proxy:
            continue
        bindings.append({
            "account_id": account.get("id"),
            "primary_proxy": proxy,
            "fallback_group": account.get("fallback_group") or "Healthy",
            "enabled": bool(account.get("enabled", True)),
        })
    CONFIG["proxy_account_bindings"] = bindings


def _proxy_nodes_payload():
    from .proxy_builtin import get_pool
    return {"nodes": get_pool().node_payloads()}


def _find_proxy_node(identifier: str):
    from .proxy_builtin import get_pool
    if not identifier:
        return None
    for node in get_pool().nodes:
        if identifier in {node.node_id, node.name, node.url, node.raw_link}:
            return node
    return None


def _remove_proxy_node(identifier: str):
    from .proxy_builtin import get_pool
    pool = get_pool()
    with pool._lock:
        removed_urls = [
            node.raw_link or node.url
            for node in pool.nodes
            if identifier in {node.node_id, node.name, node.url, node.raw_link}
        ]
        before = len(pool.nodes)
        pool.nodes[:] = [node for node in pool.nodes if identifier not in {node.node_id, node.name, node.url, node.raw_link}]
        removed = before - len(pool.nodes)
    if removed:
        CONFIG["proxies"] = [
            value for value in (CONFIG.get("proxies") or [])
            if value not in removed_urls
        ]
        sources = dict(CONFIG.get("proxy_import_sources") or {})
        sources["direct_links"] = [
            value for value in (sources.get("direct_links") or [])
            if value not in removed_urls
        ]
        providers = dict(sources.get("providers") or {})
        for value in removed_urls:
            providers.pop(value, None)
        sources["providers"] = providers
        CONFIG["proxy_import_sources"] = sources
        _save_config_fields(["proxies", "proxy_import_sources"])
    return removed


def _handle_proxy_import(data):
    subscriptions = data.get("subscriptions") or data.get("proxy_subscriptions") or []
    direct_links = data.get("direct_links") or data.get("proxies") or data.get("links") or []
    raw = data.get("raw") or data.get("content") or ""
    if isinstance(subscriptions, str):
        subscriptions = [line.strip() for line in subscriptions.splitlines() if line.strip()]
    if isinstance(direct_links, str):
        direct_links = [line.strip() for line in direct_links.splitlines() if line.strip()]
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(("http://", "https://")) and "/sub" in line.lower():
                subscriptions.append(line)
            else:
                direct_links.append(line)
    provider = data.get("provider") or data.get("name") or ""

    from .proxy_builtin import import_proxy_sources
    result = import_proxy_sources(subscriptions=subscriptions, direct_links=direct_links, provider=provider)
    _extend_config_list("proxy_subscriptions", subscriptions)
    _extend_config_list("proxies", direct_links)
    _merge_proxy_import_sources(subscriptions, direct_links, provider)
    CONFIG["proxy_pool_enabled"] = True
    _save_config_fields(["proxy_subscriptions", "proxies", "proxy_import_sources", "proxy_pool_enabled"])
    return {
        "success": True,
        "message": "proxy sources imported",
        "result": result,
    }


def _handle_proxy_test(data):
    from .proxy_builtin import get_pool
    pool = get_pool()
    identifier = data.get("id") or data.get("name") or data.get("url") or ""
    node = _find_proxy_node(identifier)
    if not node:
        return {"error": "proxy node not found"}, 404
    timeout = float(data.get("timeout") or pool._probe_timeout)
    test_url = data.get("test_url") or "http://httpbin.org/ip"
    latency = pool.speed_test(node, test_url=test_url, timeout=timeout)
    if latency == float("inf"):
        pool.mark_failure(node, reason="speed test timeout")
        return {"success": False, "node": node.to_dict(), "latency_ms": None}, 200
    pool.mark_success(node, latency)
    return {"success": True, "node": node.to_dict(), "latency_ms": round(latency, 1)}, 200


def _handle_proxy_group_select(group_name, data):
    proxy_name = (data.get("proxy") or data.get("proxy_name") or data.get("node_id") or "").strip()
    from .proxy_builtin import set_group_selection, get_group_summaries
    if not set_group_selection(group_name, proxy_name):
        return {"error": "proxy group not found"}, 404
    selections = dict(CONFIG.get("proxy_group_selections") or {})
    if proxy_name:
        selections[group_name] = proxy_name
    else:
        selections.pop(group_name, None)
    CONFIG["proxy_group_selections"] = selections
    _save_config_fields(["proxy_group_selections"])
    return {"success": True, "groups": get_group_summaries()}, 200


def _account_id_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return urllib.parse.unquote(parts[2]) if len(parts) >= 3 else ""


def _list_accounts():
    return list(CONFIG.get("accounts") or [])


def _upsert_account(data):
    accounts = list(CONFIG.get("accounts") or [])
    account_id = (data.get("id") or data.get("account_id") or data.get("auth_user") or "").strip()
    if not account_id:
        return {"error": "missing account id"}, 400
    enabled_provided = "enabled" in data
    entry = {
        "id": account_id,
        "label": data.get("label") or account_id,
        "auth_user": data.get("auth_user"),
        "cookie_file": data.get("cookie_file"),
        "primary_proxy": data.get("primary_proxy") or data.get("proxy"),
        "fallback_group": data.get("fallback_group") or "Healthy",
        "enabled": bool(data.get("enabled", True)),
    }
    replaced = False
    saved_account = entry
    for idx, existing in enumerate(accounts):
        if existing.get("id") == account_id:
            merged = dict(existing)
            update_fields = {}
            field_inputs = {
                "label": ("label",),
                "auth_user": ("auth_user",),
                "cookie_file": ("cookie_file",),
                "primary_proxy": ("primary_proxy", "proxy", "node_id"),
                "fallback_group": ("fallback_group",),
                "enabled": ("enabled",),
            }
            for key, aliases in field_inputs.items():
                if not any(alias in data for alias in aliases):
                    continue
                value = entry.get(key)
                if value is not None:
                    update_fields[key] = value
            if enabled_provided:
                update_fields["enabled"] = bool(data.get("enabled"))
            merged.update(update_fields)
            accounts[idx] = merged
            saved_account = merged
            replaced = True
            break
    if not replaced:
        accounts.append(entry)
    CONFIG["accounts"] = accounts
    _sync_proxy_account_bindings()
    _save_config_fields(["accounts", "proxy_account_bindings"])
    return {"success": True, "account": saved_account, "accounts": accounts}, 200


def _delete_account(account_id):
    accounts = list(CONFIG.get("accounts") or [])
    next_accounts = [account for account in accounts if account.get("id") != account_id]
    CONFIG["accounts"] = next_accounts
    _sync_proxy_account_bindings()
    _save_config_fields(["accounts", "proxy_account_bindings"])
    return {"success": True, "removed": len(accounts) - len(next_accounts), "accounts": next_accounts}, 200


def _bind_account_proxy(account_id, data):
    data = dict(data or {})
    data["id"] = account_id
    data["primary_proxy"] = data.get("primary_proxy") or data.get("proxy") or data.get("node_id")
    return _upsert_account(data)


def _probe_cookie(cookie_str, sapisid):
    try:
        from .gemini import _account_prefix, _get_ssl_ctx, make_sapisidhash
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cookie": cookie_str,
            "Referer": f"https://gemini.google.com{_account_prefix()}/app",
        }
        if sapisid:
            headers["Authorization"] = make_sapisidhash(sapisid)
        url = f"https://gemini.google.com{_account_prefix()}/app"
        req = urllib.request.Request(url, headers=headers, method="GET")
        proxy = CONFIG.get("proxy") if CONFIG.get("proxy_enabled", True) else None
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=_get_ssl_ctx()),
            )
            resp = opener.open(req, timeout=30)
        else:
            resp = urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=30)
        html = resp.read().decode("utf-8", errors="replace")
        return {
            "reachable": True,
            "http_status": getattr(resp, "status", 200),
            "has_bl": "boq_assistant-bard-web-server_" in html,
            "has_stream_generate": "StreamGenerate" in html,
            "page_bytes": len(html.encode("utf-8")),
        }
    except Exception as e:
        return {
            "reachable": False,
            "error": str(e)[:160],
        }


def check_cookie_health(real_probe=True):
    results = []
    for c in _cookie_pool:
        cookie = c.get("cookie", "")
        sapisid = c.get("sapisid", "")
        item = {
            "healthy": bool(cookie) and c.get("healthy", True),
            "has_sapisid": bool(sapisid),
            "cookie_length": len(cookie),
        }
        if real_probe and cookie:
            item["probe"] = _probe_cookie(cookie, sapisid)
            if not item["probe"].get("reachable"):
                item["healthy"] = False
        results.append(item)
    return results


def handle_admin_request(path, method, body=None, headers=None):
    headers = headers or {}
    admin_key = headers.get("X-Admin-Key", "")

    if CONFIG.get("admin_key") and admin_key != CONFIG.get("admin_key"):
        return {"error": "Unauthorized: invalid admin key"}, 401

    if path == "/admin/apikey":
        if method == "GET":
            return {"keys": list_api_keys()}, 200
        elif method == "POST":
            data = body or {}
            key = data.get("api_key", "")
            if not key:
                return {"error": "Missing api_key"}, 400
            add_api_key(key)
            return {"success": True, "message": "API key added"}, 200
        elif method == "DELETE":
            data = body or {}
            key = data.get("api_key", "")
            if not key:
                return {"error": "Missing api_key"}, 400
            remove_api_key(key)
            return {"success": True, "message": "API key removed"}, 200

    elif path == "/admin/cookie":
        if method == "GET":
            return {"cookies": list_cookies(), "pool_size": len(_cookie_pool)}, 200
        elif method == "POST":
            data = body or {}
            cookie = data.get("cookie", "")
            sapisid = data.get("sapisid", "")
            if not cookie:
                return {"error": "Missing cookie"}, 400
            result = add_cookie(cookie, sapisid)
            return result, 200
        elif method == "DELETE":
            data = body or {}
            index = data.get("index")
            cookie = data.get("cookie")
            result = remove_cookie(index=index, cookie_str=cookie)
            return result, 200

    elif path == "/admin/cookie/health" and method == "GET":
        return {"health": check_cookie_health()}, 200

    elif path == "/admin/proxy":
        if method == "GET":
            return get_proxy_status(), 200

    elif path == "/admin/proxy/nodes":
        if method == "GET":
            return _proxy_nodes_payload(), 200
        if method == "POST":
            data = body or {}
            payload, status = _handle_proxy_test(data) if data.get("test_existing") else (_handle_proxy_import({
                "direct_links": data.get("links") or data.get("proxies") or data.get("url") or data.get("raw") or "",
                "provider": data.get("provider") or "manual",
            }), 200)
            return payload, status

    elif path.startswith("/admin/proxy/nodes/") and method == "DELETE":
        identifier = urllib.parse.unquote(path.rsplit("/", 1)[-1])
        removed = _remove_proxy_node(identifier)
        return {"success": True, "removed": removed}, 200

    elif path == "/admin/proxy/import" and method == "POST":
        return _handle_proxy_import(body or {}), 200

    elif path == "/admin/proxy/health" and method == "GET":
        from .proxy_builtin import get_pool_health
        return {"health": get_pool_health()}, 200

    elif path == "/admin/proxy/test" and method == "POST":
        return _handle_proxy_test(body or {})

    elif path == "/admin/proxy/test-all" and method == "POST":
        data = body or {}
        from .proxy_builtin import check_pool_health, get_pool_health
        result = check_pool_health(
            timeout=data.get("timeout"),
            concurrency=data.get("concurrency"),
            only_stale=bool(data.get("only_stale", False)),
        )
        return {"success": True, "result": result, "health": get_pool_health()}, 200

    elif path == "/admin/proxy/providers" and method == "GET":
        from .proxy_builtin import get_provider_summaries
        return {"providers": get_provider_summaries()}, 200

    elif path == "/admin/proxy/groups" and method == "GET":
        from .proxy_builtin import get_group_summaries
        return {"groups": get_group_summaries()}, 200

    elif path.startswith("/admin/proxy/groups/") and path.endswith("/select") and method == "POST":
        group_name = urllib.parse.unquote(path.split("/")[4])
        return _handle_proxy_group_select(group_name, body or {})

    elif path == "/admin/accounts":
        if method == "GET":
            return {"accounts": _list_accounts()}, 200
        if method == "POST":
            return _upsert_account(body or {})

    elif path.startswith("/admin/accounts/"):
        account_id = _account_id_from_path(path)
        if path.endswith("/bind-proxy") and method == "POST":
            return _bind_account_proxy(account_id, body or {})
        if method == "GET":
            for account in _list_accounts():
                if account.get("id") == account_id:
                    return {"account": account}, 200
            return {"error": "account not found"}, 404
        if method == "POST":
            data = dict(body or {})
            data["id"] = account_id
            return _upsert_account(data)
        if method == "DELETE":
            return _delete_account(account_id)

    elif path == "/admin/requests" and method == "GET":
        dashboard = get_dashboard_data()
        return {"requests": dashboard.get("recent_requests", [])}, 200

    elif path.startswith("/admin/requests/") and method == "GET":
        request_id = path.rsplit("/", 1)[-1]
        detail = get_request_detail(request_id)
        if not detail:
            return {"error": "Request not found"}, 404
        return {"request": detail}, 200

    elif path == "/admin/stats" and method == "GET":
        return get_admin_stats(), 200

    elif path == "/admin" and method == "GET":
        return {"status": "ok", "endpoints": [
            "/admin/apikey", "/admin/cookie", "/admin/cookie/health",
            "/admin/proxy", "/admin/proxy/nodes", "/admin/proxy/import",
            "/admin/proxy/health", "/admin/proxy/providers", "/admin/proxy/groups", "/admin/accounts",
            "/admin/requests", "/admin/stats"
        ]}, 200

    return {"error": "Not found"}, 404
