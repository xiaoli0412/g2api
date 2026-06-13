"""End-to-end HTTP checks for the three cookie acquisition paths."""

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


def _json_request(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _json_get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_cookie_import_push_and_internal_browser_routes(tmp_path, monkeypatch):
    port = _free_port()
    cookie_file = tmp_path / "cookie.txt"
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "cookie_file", "host", "port")}
    CONFIG["api_keys"] = []
    CONFIG["cookie_file"] = str(cookie_file)
    CONFIG["host"] = "127.0.0.1"
    CONFIG["port"] = port

    calls = []

    def fake_browser_login(target_file, service_port):
        calls.append({"target_file": target_file, "service_port": service_port})
        return {"success": True, "status": "opening_browser"}

    monkeypatch.setattr("gemini_web2api.playwright_cookie.start_browser_login_async", fake_browser_login)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        har = {
            "log": {
                "entries": [{
                    "request": {
                        "headers": [
                            {"name": "Cookie", "value": "SID=sid; SAPISID=sapisid; __Secure-1PSID=secure"}
                        ]
                    }
                }]
            }
        }
        status, imported = _json_request(
            f"http://127.0.0.1:{port}/api/cookie/import",
            {"raw": json.dumps(har), "source": "network-file"},
        )
        assert status == 200
        assert imported["success"] is True
        assert imported["method"] == "manual_import"
        assert imported["diagnostics"]["web_ui_likely_complete"] is True
        assert "SID=sid" in cookie_file.read_text(encoding="utf-8")

        status, pushed = _json_request(
            f"http://127.0.0.1:{port}/api/cookie/push",
            {"cookies": "SID=edge; SAPISID=edge-sapisid; __Secure-3PSID=edge-secure", "sapisid": "edge-sapisid", "source": "edge-extension"},
        )
        assert status == 200
        assert pushed["success"] is True
        assert pushed["method"] == "edge_extension"
        assert pushed["diagnostics"]["web_ui_likely_complete"] is True
        assert "SID=edge" in cookie_file.read_text(encoding="utf-8")

        status, cookie_status = _json_get(f"http://127.0.0.1:{port}/api/cookie/status")
        assert status == 200
        assert cookie_status["sources"]["manual_import"]["source"] == "network-file"
        assert cookie_status["sources"]["edge_extension"]["source"] == "edge-extension"
        assert cookie_status["sources"]["edge_extension"]["diagnostics"]["web_ui_likely_complete"] is True
        assert cookie_status["last_refresh_source"] == "edge-extension"

        status, browser = _json_request(
            f"http://127.0.0.1:{port}/api/cookie/browser-login",
            {},
        )
        assert status == 200
        assert browser["success"] is True
        assert calls == [{"target_file": str(cookie_file), "service_port": port}]
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)
