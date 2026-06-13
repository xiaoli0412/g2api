"""Tests for cookie table/header normalization."""

from gemini_web2api.cookies import diagnose_cookie_header, normalize_cookie_input


def test_normalize_cookie_header_extracts_sapisid():
    cookie, sapisid = normalize_cookie_input("SID=abc; SAPISID=secret; HSID=def")
    assert cookie == "SID=abc; SAPISID=secret; HSID=def"
    assert sapisid == "secret"


def test_normalize_browser_export_table_keeps_gemini_scoped_cookies():
    table = "\n".join([
        "LSID account-value accounts.google.com / 2027 10",
        "SID sid-value .google.com / 2027 10",
        "SAPISID sapi-value .google.com / 2027 10",
        "NID nid-value .google.com / 2027 10",
        "SID wrong example.com / 2027 10",
    ])
    cookie, sapisid = normalize_cookie_input(table)
    assert "SID=sid-value" in cookie
    assert "SAPISID=sapi-value" in cookie
    assert "NID=nid-value" in cookie
    assert "LSID=account-value" in cookie
    assert "wrong" not in cookie
    assert sapisid == "sapi-value"


def test_normalize_netscape_cookie_export_keeps_secure_google_cookies():
    netscape = "\n".join([
        "# Netscape HTTP Cookie File",
        "#HttpOnly_.google.com\tTRUE\t/\tTRUE\t1790000000\tSID\tsid-value",
        ".google.com\tTRUE\t/\tTRUE\t1790000000\tSAPISID\tsapi-value",
        ".google.com\tTRUE\t/\tTRUE\t1790000000\t__Secure-1PSID\tsecure-value",
        "example.com\tFALSE\t/\tFALSE\t1790000000\tSID\twrong",
    ])
    cookie, sapisid = normalize_cookie_input(netscape)
    assert "SID=sid-value" in cookie
    assert "SAPISID=sapi-value" in cookie
    assert "__Secure-1PSID=secure-value" in cookie
    assert "wrong" not in cookie
    assert sapisid == "sapi-value"


def test_cookie_diagnostics_distinguish_api_from_full_web_ui():
    diag = diagnose_cookie_header("SID=sid; SAPISID=sapisid; HSID=hsid; SSID=ssid; APISID=apisid")
    assert diag["api_streamgenerate_ready"] is True
    assert diag["web_ui_likely_complete"] is False
    assert "__Secure-1PSID" in diag["web_ui_missing_strong"]


def test_cookie_diagnostics_detect_secure_psid():
    diag = diagnose_cookie_header("SID=sid; SAPISID=sapisid; __Secure-1PSID=secure")
    assert diag["api_streamgenerate_ready"] is True
    assert diag["web_ui_secure_psid_present"] is True
    assert diag["web_ui_likely_complete"] is True


def test_normalize_har_network_export_extracts_cookie_header():
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
    cookie, sapisid = normalize_cookie_input(__import__("json").dumps(har))
    assert "SID=sid" in cookie
    assert "SAPISID=sapisid" in cookie
    assert "__Secure-1PSID=secure" in cookie
    assert sapisid == "sapisid"


def test_normalize_json_cookie_list_extracts_google_cookies():
    exported = [
        {"name": "SID", "value": "sid", "domain": ".google.com"},
        {"name": "SAPISID", "value": "sapisid", "domain": ".google.com"},
        {"name": "SID", "value": "wrong", "domain": "example.com"},
    ]
    cookie, sapisid = normalize_cookie_input(__import__("json").dumps(exported))
    assert "SID=sid" in cookie
    assert "SAPISID=sapisid" in cookie
    assert "wrong" not in cookie
    assert sapisid == "sapisid"
