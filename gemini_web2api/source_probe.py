"""Fetch anonymous/authenticated Gemini web page sources for diagnostics."""
import argparse
import difflib
import hashlib
import json
import os
import re
import time
import urllib.request

from .config import CONFIG, find_config, load_config
from .gemini import _account_prefix, _build_headers, _get_ssl_ctx, load_cookie, make_sapisidhash


GEMINI_APP_URL = "https://gemini.google.com/app"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _auth_app_url() -> str:
    return f"https://gemini.google.com{_account_prefix()}/app"


def _fetch(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, context=_get_ssl_ctx(), timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _make_auth_headers(cookie_str: str, sapisid: str = None) -> dict:
    headers = {
        "User-Agent": UA,
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/app",
        "X-Same-Domain": "1",
        "Cookie": cookie_str,
    }
    if sapisid:
        headers["Authorization"] = make_sapisidhash(sapisid)
    return headers


def _summarize(html: str) -> dict:
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    return {
        "bytes": len(html.encode("utf-8")),
        "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "bl": (re.search(r'boq_assistant-bard-web-server_[\w.]+', html) or [None])[0],
        "has_snlm0e": "SNlM0e" in html,
        "has_push_id_key": "qKIAYe" in html,
        "has_pctx_key": "Ylro7b" in html,
        "has_stream_generate": "StreamGenerate" in html,
        "script_count": len(scripts),
        "scripts": scripts[:20],
    }


def probe_sources(out_dir: str, include_auth: bool = True, cookie_override: tuple = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)

    anon_html = _fetch(GEMINI_APP_URL, {"User-Agent": UA})
    anon_path = os.path.join(out_dir, "gemini_anon.html")
    with open(anon_path, "w", encoding="utf-8") as f:
        f.write(anon_html)

    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": GEMINI_APP_URL,
        "anonymous": {"path": anon_path, **_summarize(anon_html)},
        "authenticated": None,
        "diff_path": None,
        "auth_cookie_available": False,
    }

    if include_auth:
        if cookie_override:
            cookie_str, sapisid = cookie_override
        else:
            cookie_str, sapisid = load_cookie()
        result["auth_cookie_available"] = bool(cookie_str)
        if cookie_str:
            auth_headers = _make_auth_headers(cookie_str, sapisid) if cookie_override else _build_headers()
            auth_headers.setdefault("User-Agent", UA)
            auth_html = _fetch(_auth_app_url(), auth_headers)
            auth_path = os.path.join(out_dir, "gemini_auth.html")
            with open(auth_path, "w", encoding="utf-8") as f:
                f.write(auth_html)
            diff_path = os.path.join(out_dir, "gemini_anon_vs_auth.diff")
            with open(diff_path, "w", encoding="utf-8") as f:
                f.writelines(difflib.unified_diff(
                    anon_html.splitlines(keepends=True),
                    auth_html.splitlines(keepends=True),
                    fromfile="gemini_anon.html",
                    tofile="gemini_auth.html",
                    n=3,
                ))
            result["authenticated"] = {
                "path": auth_path,
                "url": _auth_app_url(),
                "has_sapisid": bool(sapisid),
                **_summarize(auth_html),
            }
            result["diff_path"] = diff_path

    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    result["summary_path"] = summary_path
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch Gemini web anonymous/authenticated source snapshots.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--cookie-file", help="Cookie file for authenticated fetch")
    parser.add_argument("--browser-cookie", action="store_true", help="Try local browser cookies for authenticated fetch")
    parser.add_argument("--out", default=None, help="Output directory")
    parser.add_argument("--anonymous-only", action="store_true")
    args = parser.parse_args()

    cfg_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if cfg_path:
        load_config(cfg_path)
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file

    out_dir = args.out or os.path.join(os.getcwd(), "gemini_source_probe")
    cookie_override = None
    if args.browser_cookie and not args.anonymous_only:
        from .cookie_manager import extract_cookies
        cookie_override = extract_cookies()
    result = probe_sources(out_dir, include_auth=not args.anonymous_only, cookie_override=cookie_override)
    printable = dict(result)
    for key in ("anonymous", "authenticated"):
        if printable.get(key):
            printable[key] = {k: v for k, v in printable[key].items() if k != "scripts"}
    print(json.dumps(printable, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
