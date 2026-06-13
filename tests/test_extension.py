"""Static checks for the Edge cookie bridge extension."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_extension_manifest_allows_google_cookies_and_local_ports():
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    permissions = set(manifest["permissions"])
    hosts = set(manifest["host_permissions"])

    assert {"cookies", "storage", "alarms", "webNavigation"}.issubset(permissions)
    assert "https://*.google.com/*" in hosts
    assert "https://gemini.google.com/*" in hosts
    assert "http://127.0.0.1/*" in hosts
    assert "http://localhost/*" in hosts
    assert all(":8081" not in host for host in hosts)


def test_extension_background_collects_google_cookie_domains():
    source = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")

    assert 'COOKIE_DOMAINS = [".google.com", "google.com", "gemini.google.com"]' in source
    assert "onHistoryStateUpdated" in source
    assert 'source: "edge-extension"' in source
    assert "__Secure-3PSID" in source


def test_extension_popup_displays_secure_3psid_and_server_diagnostics():
    popup = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
    popup_js = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

    assert "cookie-__Secure-3PSID" in popup
    assert "serverDiag" in popup
    assert "web_ui_likely_complete" in popup_js
    assert "api_streamgenerate_ready" in popup_js
