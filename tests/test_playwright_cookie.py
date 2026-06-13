"""Tests for Playwright cookie extraction helpers."""

from gemini_web2api.playwright_cookie import (
    _cookie_urls,
    _extract_cookie_header_from_cookie_list,
    _extract_cookies_from_context,
)


class DummyContext:
    def __init__(self, cookies):
        self._cookies = cookies

    def cookies(self, urls):
        self.urls = urls
        return self._cookies


def test_extract_cookies_keeps_full_google_login_cookie_set():
    context = DummyContext([
        {"name": "SID", "value": "sid", "domain": ".google.com"},
        {"name": "SAPISID", "value": "sapisid", "domain": ".google.com"},
        {"name": "__Secure-3PSID", "value": "secure", "domain": ".google.com"},
        {"name": "LSID", "value": "lsid", "domain": "accounts.google.com"},
        {"name": "other", "value": "wrong", "domain": "example.com"},
    ])

    cookie, sapisid = _extract_cookies_from_context(context)

    assert "SID=sid" in cookie
    assert "SAPISID=sapisid" in cookie
    assert "__Secure-3PSID=secure" in cookie
    assert "LSID=lsid" in cookie
    assert "wrong" not in cookie
    assert sapisid == "sapisid"


def test_extract_cookies_requires_google_auth_markers():
    context = DummyContext([
        {"name": "NID", "value": "nid", "domain": ".google.com"},
    ])

    assert _extract_cookies_from_context(context) == (None, None)


def test_extract_cookie_header_returns_sanitized_diagnostics():
    cookie, sapisid, diagnostics = _extract_cookie_header_from_cookie_list([
        {"name": "SID", "value": "sid", "domain": ".google.com"},
        {"name": "SAPISID", "value": "sapisid", "domain": ".google.com"},
        {"name": "__Secure-1PSID", "value": "secure-1", "domain": ".google.com"},
        {"name": "__Secure-3PSID", "value": "secure-3", "domain": ".google.com"},
    ])

    assert cookie
    assert "SID=sid" in cookie
    assert sapisid == "sapisid"
    assert diagnostics["api_streamgenerate_ready"] is True
    assert diagnostics["web_ui_likely_complete"] is True
    assert "secure-1" not in str(diagnostics)


def test_extract_cookie_header_partial_cookie_explains_missing_secure_psid():
    cookie, sapisid, diagnostics = _extract_cookie_header_from_cookie_list([
        {"name": "SID", "value": "sid", "domain": ".google.com"},
        {"name": "SAPISID", "value": "sapisid", "domain": ".google.com"},
    ])

    assert cookie == "SAPISID=sapisid; SID=sid" or cookie == "SID=sid; SAPISID=sapisid"
    assert sapisid == "sapisid"
    assert diagnostics["api_streamgenerate_ready"] is True
    assert diagnostics["web_ui_likely_complete"] is False


def test_cookie_urls_include_google_account_scopes():
    urls = _cookie_urls()
    assert "https://gemini.google.com" in urls
    assert "https://accounts.google.com" in urls
    assert "https://www.google.com" in urls
