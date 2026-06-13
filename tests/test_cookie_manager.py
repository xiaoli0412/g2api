"""Tests for cookie refresh and readiness upgrade behavior."""

from gemini_web2api import cookie_manager
from gemini_web2api.config import CONFIG


def test_manual_refresh_upgrades_api_cookie_to_full_web_cookie(monkeypatch):
    monkeypatch.setattr(cookie_manager, "load_cookie", lambda: ("SID=sid; SAPISID=sapisid", "sapisid"))
    monkeypatch.setattr(
        cookie_manager,
        "_refresh_from_local_sources",
        lambda require_web_ui=False: (
            "SID=sid; SAPISID=sapisid; __Secure-1PSID=secure",
            "sapisid",
            "internal-browser-profile",
        ),
    )
    saved = {}

    def fake_save(cookie_str, sapisid="", source="refresh"):
        saved.update({"cookie": cookie_str, "sapisid": sapisid, "source": source})
        return True

    monkeypatch.setattr(cookie_manager, "_save_cookie_candidate", fake_save)

    result = cookie_manager.manual_refresh()

    assert result["success"] is True
    assert result["source"] == "internal-browser-profile"
    assert result["diagnostics"]["web_ui_likely_complete"] is True
    assert saved["source"] == "internal-browser-profile"


def test_manual_refresh_reports_api_cookie_when_no_full_web_upgrade(monkeypatch):
    monkeypatch.setattr(cookie_manager, "load_cookie", lambda: ("SID=sid; SAPISID=sapisid", "sapisid"))
    monkeypatch.setattr(cookie_manager, "_refresh_from_local_sources", lambda require_web_ui=False: ("", None, ""))

    result = cookie_manager.manual_refresh()

    assert result["success"] is True
    assert result["needs_browser_login"] is True
    assert result["diagnostics"]["api_streamgenerate_ready"] is True
    assert result["diagnostics"]["web_ui_likely_complete"] is False


def test_manual_refresh_accepts_api_candidate_when_current_cookie_is_invalid(monkeypatch):
    monkeypatch.setattr(cookie_manager, "load_cookie", lambda: ("NID=nid", ""))
    seen = {}

    def fake_refresh(require_web_ui=False):
        seen["require_web_ui"] = require_web_ui
        return "SID=sid; SAPISID=sapisid", "sapisid", "installed-browser:Edge"

    monkeypatch.setattr(cookie_manager, "_refresh_from_local_sources", fake_refresh)
    monkeypatch.setattr(cookie_manager, "_save_cookie_candidate", lambda *args, **kwargs: True)

    result = cookie_manager.manual_refresh()

    assert seen["require_web_ui"] is False
    assert result["success"] is True
    assert result["source"] == "installed-browser:Edge"
    assert result["diagnostics"]["api_streamgenerate_ready"] is True
    assert result["needs_browser_login"] is True


def test_cookie_status_exposes_api_and_web_ui_readiness(monkeypatch):
    monkeypatch.setattr(cookie_manager, "load_cookie", lambda: ("SID=sid; SAPISID=sapisid", "sapisid"))

    status = cookie_manager.get_cookie_status()

    assert status["cookie_valid"] is True
    assert status["api_streamgenerate_ready"] is True
    assert status["web_ui_likely_complete"] is False
    assert "__Secure-1PSID" in status["diagnostics"]["web_ui_missing_strong"]


def test_local_source_refresh_rejects_non_auth_google_cookies(monkeypatch):
    monkeypatch.setattr(cookie_manager, "_extract_installed_browser_cookies", lambda: ("NID=nid; _ga=ga", "", "Edge"))
    monkeypatch.setattr("gemini_web2api.playwright_cookie.refresh_cookie_via_playwright", lambda: ("", None))

    cookie, sapisid, source = cookie_manager._refresh_from_local_sources()

    assert cookie == ""
    assert sapisid is None
    assert source == ""


def test_accept_cookie_source_records_manual_extension_and_internal_states(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookie.json"
    old_cookie_file = CONFIG.get("cookie_file")
    CONFIG["cookie_file"] = str(cookie_file)
    cookie_manager._source_states = {
        "manual_import": {"status": "idle"},
        "edge_extension": {"status": "idle"},
        "internal_browser": {"status": "idle"},
    }
    added = []

    def fake_add_cookie(cookie, sapisid="", source="api"):
        added.append({"cookie": cookie, "sapisid": sapisid, "source": source})
        return {"success": True}

    monkeypatch.setattr("gemini_web2api.admin.add_cookie", fake_add_cookie)
    try:
        manual = cookie_manager.accept_cookie_source(
            '{"cookies":[{"name":"SID","value":"sid","domain":".google.com"},{"name":"SAPISID","value":"sapisid","domain":".google.com"}]}',
            source="network-file",
        )
        edge = cookie_manager.accept_cookie_source(
            "SID=edge; SAPISID=edge-sapisid; __Secure-3PSID=secure",
            source="edge-extension",
        )
        internal = cookie_manager.accept_cookie_source(
            "SID=browser; SAPISID=browser-sapisid; __Secure-1PSID=secure",
            source="internal-browser",
        )

        status = cookie_manager.get_cookie_status()

        assert manual["method"] == "manual_import"
        assert edge["method"] == "edge_extension"
        assert internal["method"] == "internal_browser"
        assert status["sources"]["manual_import"]["source"] == "network-file"
        assert status["sources"]["edge_extension"]["diagnostics"]["web_ui_likely_complete"] is True
        assert status["sources"]["internal_browser"]["status"] == "ok_full_web"
        assert status["last_refresh_source"] == "internal-browser"
        assert "SID=browser" in cookie_file.read_text(encoding="utf-8")
        assert [item["source"] for item in added] == ["network-file", "edge-extension", "internal-browser"]
    finally:
        CONFIG["cookie_file"] = old_cookie_file
