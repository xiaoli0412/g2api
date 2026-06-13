"""Cookie parsing helpers for Gemini web authentication."""

import json
import re


GEMINI_COOKIE_DOMAINS = {".google.com", "google.com", "gemini.google.com"}
API_CORE_COOKIES = {"SID", "HSID", "SSID", "APISID", "SAPISID"}
WEB_UI_STRONG_COOKIES = {"__Secure-1PSID", "__Secure-3PSID"}
WEB_UI_SUPPORT_COOKIES = {
    "__Secure-1PSIDTS", "__Secure-3PSIDTS",
    "__Secure-1PSIDCC", "__Secure-3PSIDCC",
    "__Secure-1PAPISID", "__Secure-3PAPISID",
}


def _looks_like_cookie_name(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_\-]+$", value or ""))


def _is_gemini_cookie_domain(domain: str) -> bool:
    domain = (domain or "").strip().lower()
    return domain in GEMINI_COOKIE_DOMAINS or domain.endswith(".google.com")


def _cookie_sort_key(pair: str) -> tuple:
    name = pair.split("=", 1)[0]
    priority = {
        "SID": 0,
        "__Secure-1PSID": 1,
        "__Secure-3PSID": 2,
        "SAPISID": 3,
        "APISID": 4,
        "HSID": 5,
        "SSID": 6,
    }.get(name, 20)
    return priority, name


def _extract_sapisid(cookie_str: str) -> str:
    try:
        pairs = dict(p.strip().split("=", 1) for p in cookie_str.split(";") if "=" in p)
        return pairs.get("SAPISID", "")
    except Exception:
        return ""


def _append_pair(pairs: list[str], name: str, value: str):
    name = (name or "").strip()
    value = str(value or "").strip()
    if name and value and _looks_like_cookie_name(name):
        pairs.append(f"{name}={value}")


def _pairs_from_cookie_json(data) -> list[str]:
    pairs = []
    if isinstance(data, dict):
        if isinstance(data.get("cookies"), list):
            for cookie in data["cookies"]:
                if isinstance(cookie, dict):
                    domain = cookie.get("domain", ".google.com")
                    if _is_gemini_cookie_domain(domain):
                        _append_pair(pairs, cookie.get("name"), cookie.get("value"))
        if isinstance(data.get("log"), dict):
            for entry in data.get("log", {}).get("entries", []) or []:
                request = entry.get("request", {}) if isinstance(entry, dict) else {}
                for cookie in request.get("cookies", []) or []:
                    if isinstance(cookie, dict):
                        _append_pair(pairs, cookie.get("name"), cookie.get("value"))
                for header in request.get("headers", []) or []:
                    if not isinstance(header, dict):
                        continue
                    if str(header.get("name", "")).lower() == "cookie":
                        for part in str(header.get("value", "")).split(";"):
                            item = part.strip()
                            if "=" in item:
                                name, value = item.split("=", 1)
                                _append_pair(pairs, name, value)
        for key, value in data.items():
            if _looks_like_cookie_name(str(key)) and isinstance(value, str):
                _append_pair(pairs, key, value)
    elif isinstance(data, list):
        for cookie in data:
            if isinstance(cookie, dict):
                domain = cookie.get("domain", ".google.com")
                if _is_gemini_cookie_domain(domain):
                    _append_pair(pairs, cookie.get("name"), cookie.get("value"))
    return pairs


def cookie_names(cookie_str: str) -> set[str]:
    """Return cookie names from a Cookie header without exposing values."""
    names = set()
    for part in (cookie_str or "").split(";"):
        if "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if name:
            names.add(name)
    return names


def diagnose_cookie_header(cookie_str: str) -> dict:
    """Return sanitized diagnostics for backend and full Web UI cookie readiness."""
    names = cookie_names(cookie_str)
    has_secure_psid = bool(names & WEB_UI_STRONG_COOKIES)
    has_secure_support = bool(names & WEB_UI_SUPPORT_COOKIES)
    has_sapisid = "SAPISID" in names
    api_missing = sorted(API_CORE_COOKIES - names)
    web_missing = sorted(WEB_UI_STRONG_COOKIES - names)
    return {
        "cookie_count": len(names),
        "names": sorted(names),
        "has_sapisid": has_sapisid,
        "api_core_missing": api_missing,
        "api_streamgenerate_ready": has_sapisid and "SID" in names,
        "web_ui_secure_psid_present": has_secure_psid,
        "web_ui_support_cookie_present": has_secure_support,
        "web_ui_missing_strong": web_missing,
        "web_ui_likely_complete": has_secure_psid and has_sapisid,
        "note": (
            "Backend text calls can work with SID/SAPISID, but full Gemini Web UI tools "
            "usually require __Secure-1PSID or __Secure-3PSID cookies from the same logged-in browser session."
        ),
    }


def normalize_cookie_input(raw: str) -> tuple[str, str]:
    """Normalize JSON, Cookie header, or browser export table into a cookie string.

    Returns (cookie_header, sapisid). Values are intentionally not logged by callers.
    """
    raw = (raw or "").strip()
    if not raw:
        return "", ""

    if raw.startswith("{") or raw.startswith("["):
        data = json.loads(raw)
        if isinstance(data, dict):
            cookie_value = data.get("cookie") or data.get("cookies") or ""
            cookie = cookie_value.strip() if isinstance(cookie_value, str) else ""
            sapisid = str(data.get("sapisid", "") or "").strip()
            if cookie and isinstance(cookie, str):
                return cookie, sapisid or _extract_sapisid(cookie)
        pairs = _pairs_from_cookie_json(data)
        cookie = "; ".join(sorted(dict.fromkeys(pairs), key=_cookie_sort_key))
        return cookie, _extract_sapisid(cookie)

    if ";\n" not in raw and "\t" not in raw and "SAPISID=" in raw:
        cookie = " ".join(raw.splitlines()).strip()
        return cookie, _extract_sapisid(cookie)

    pairs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("# Netscape"):
            continue

        # Netscape cookie format:
        # .google.com TRUE / TRUE 1790000000 __Secure-1PSID value
        # #HttpOnly_.google.com TRUE / TRUE 1790000000 SID value
        netscape_line = line
        if netscape_line.startswith("#HttpOnly_"):
            netscape_line = netscape_line[len("#HttpOnly_"):]
        netscape_parts = re.split(r"\s+", netscape_line, maxsplit=6)
        if len(netscape_parts) == 7 and _is_gemini_cookie_domain(netscape_parts[0]) and _looks_like_cookie_name(netscape_parts[5]):
            _append_pair(pairs, netscape_parts[5], netscape_parts[6])
            continue

        if "\t" in line:
            parts = line.split("\t")
        else:
            parts = re.split(r"\s+", line)

        if len(parts) >= 3 and _looks_like_cookie_name(parts[0]):
            name, value, domain = parts[0].strip(), parts[1].strip(), parts[2].strip().lower()
            if _is_gemini_cookie_domain(domain):
                _append_pair(pairs, name, value)
            continue

        if ";" in line and "=" in line:
            for part in line.split(";"):
                item = part.strip()
                if item and _looks_like_cookie_name(item.split("=", 1)[0]):
                    name, value = item.split("=", 1)
                    _append_pair(pairs, name, value)

    deduped = []
    seen = set()
    for pair in pairs:
        name = pair.split("=", 1)[0]
        if name in seen:
            continue
        seen.add(name)
        deduped.append(pair)

    cookie = "; ".join(sorted(deduped, key=_cookie_sort_key))
    return cookie, _extract_sapisid(cookie)
