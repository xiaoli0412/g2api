"""Tests for sanitized real-browser probe helpers."""

from gemini_web2api.browser_probe import (
    _assess_web_ui_login,
    _cookie_header_to_playwright_cookies,
    _cookie_input_to_playwright_cookies,
    _effective_cookie_file,
    _keyword_pattern_specs,
)
from gemini_web2api.config import CONFIG


def test_cookie_header_to_playwright_cookies_keeps_secure_cookie_names():
    cookies = _cookie_header_to_playwright_cookies("SID=sid; SAPISID=sapisid; __Secure-3PSID=secure")
    names = {item["name"] for item in cookies}

    assert names == {"SID", "SAPISID", "__Secure-3PSID"}
    assert all(item["domain"] == ".google.com" for item in cookies)
    assert all(item["secure"] is True for item in cookies)


def test_cookie_header_to_playwright_cookies_handles_host_prefix():
    cookies = _cookie_header_to_playwright_cookies("__Host-1PLSID=hosted; SID=sid")
    host_cookie = next(item for item in cookies if item["name"] == "__Host-1PLSID")

    assert "domain" not in host_cookie
    assert host_cookie["url"] == "https://accounts.google.com/"
    assert "path" not in host_cookie


def test_cookie_input_to_playwright_cookies_preserves_browser_table_domains():
    raw = "\n".join([
        "ACCOUNT_CHOOSER\tchooser\taccounts.google.com\t/\t2027\t1\t✓\t✓\t\t\tHigh",
        "__Secure-3PSID\tpsid\t.google.com\t/\t2027\t1\t\t✓\tNone\t\tHigh",
        "__Host-1PLSID\thosted\taccounts.google.com\t/\t2027\t1\t✓\t✓\t\t\tHigh",
    ])

    cookies = _cookie_input_to_playwright_cookies(raw, "SID=sid")
    by_name = {item["name"]: item for item in cookies}

    assert by_name["ACCOUNT_CHOOSER"]["domain"] == "accounts.google.com"
    assert by_name["__Secure-3PSID"]["domain"] == ".google.com"
    assert by_name["__Secure-3PSID"]["sameSite"] == "None"
    assert by_name["__Host-1PLSID"]["url"] == "https://accounts.google.com/"
    assert "domain" not in by_name["__Host-1PLSID"]


def test_keyword_pattern_specs_are_json_ready():
    specs = _keyword_pattern_specs()
    create_image = next(item for item in specs if item["name"] == "Create image")
    assert create_image["source"]
    assert create_image["flags"] == "i"
    assert all({"name", "source", "flags"} <= set(item) for item in specs)


def test_assess_web_ui_login_allows_hidden_sign_in_text_with_complete_cookie():
    browser = {
        "status": 200,
        "final_url": "https://gemini.google.com/u/1/app",
        "sign_in_visible": True,
        "has_text_entry": True,
        "visible_signin_control_present": False,
    }
    diagnostics = {"web_ui_likely_complete": True}

    assert _assess_web_ui_login(browser, diagnostics) is True


def test_assess_web_ui_login_rejects_visible_signin_control():
    browser = {
        "status": 200,
        "final_url": "https://gemini.google.com/app",
        "sign_in_visible": True,
        "has_text_entry": True,
        "visible_signin_control_present": True,
    }
    diagnostics = {"web_ui_likely_complete": True}

    assert _assess_web_ui_login(browser, diagnostics) is False


def test_assess_web_ui_login_rejects_accounts_signin_redirect():
    browser = {
        "status": 200,
        "final_url": "https://accounts.google.com/ServiceLogin?continue=https://gemini.google.com/app",
        "sign_in_visible": False,
        "has_text_entry": True,
    }
    diagnostics = {"web_ui_likely_complete": True}

    assert _assess_web_ui_login(browser, diagnostics) is False


def test_effective_cookie_file_uses_config_when_cli_omitted():
    old_cookie_file = CONFIG.get("cookie_file")
    try:
        CONFIG["cookie_file"] = "configured-cookie.txt"

        assert _effective_cookie_file(None) == "configured-cookie.txt"
        assert _effective_cookie_file("cli-cookie.txt") == "cli-cookie.txt"
    finally:
        CONFIG["cookie_file"] = old_cookie_file
