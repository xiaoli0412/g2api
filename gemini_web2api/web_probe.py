"""Authenticated Gemini Web source/asset capability probe.

The probe uses normal GET requests against the current Gemini Web page and its
JavaScript assets. It records feature keyword evidence without storing script
contents, cookies, prompts, or authorization headers.
"""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

from .config import CONFIG, find_config, load_config
from .gemini import _account_prefix, _build_headers, _get_ssl_ctx
from .har_analyze import KEYWORD_PATTERNS


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
COMMON_JS_WORDS = {
    "Promise", "abort", "click", "depth", "findLast", "load", "message",
    "pagehide", "submit", "toSorted", "with", "zones", "then", "catch",
    "apply", "bind", "call", "event", "target",
}

MODEL_NAME_PATTERNS = [
    re.compile(r"\bgemini-[\w.-]+", re.I),
    re.compile(r"\bimagen-[\w.-]+", re.I),
    re.compile(r"\bveo-[\w.-]+", re.I),
    re.compile(r"\bNano Banana(?:\s+(?:2|Pro))?", re.I),
    re.compile(r"\bOmni\b", re.I),
    re.compile(r"\bLyria\s*\d+\b", re.I),
]

NON_MODEL_NAME_PATTERNS = [
    re.compile(r"^gemini-u-", re.I),
    re.compile(r"^gemini-apps-while-signed-out$", re.I),
    re.compile(r"^imagen-loading-gradient-", re.I),
    re.compile(r"^imagen-selection-dialog-", re.I),
]


def _fetch(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA}, method="GET")
    proxy = CONFIG.get("proxy")
    ctx = _get_ssl_ctx()
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=ctx),
        )
        resp = opener.open(req, timeout=timeout)
    else:
        resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
    body = resp.read()
    return getattr(resp, "status", 200), dict(resp.headers), body


def _script_urls(html, base_url):
    urls = []
    for match in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html):
        urls.append(urllib.parse.urljoin(base_url, match.group(1)))
    return list(dict.fromkeys(urls))


def _keyword_hits(text):
    return [name for name, pattern in KEYWORD_PATTERNS.items() if pattern.search(text)]


def _extract_rpc_like_ids(text, limit=80):
    ids = set()
    for pattern in [
        r'rpcids[=:]["\']([A-Za-z0-9_-]{3,20})["\']',
        r'wrb\.fr["\']\s*,\s*["\']([A-Za-z0-9_-]{3,20})["\']',
        r'["\']([A-Za-z0-9_-]{4,8})["\']\s*,\s*function',
    ]:
        ids.update(re.findall(pattern, text))
    ids = {item for item in ids if item not in COMMON_JS_WORDS and not item.islower()}
    return sorted(ids)[:limit]


def _extract_model_like_names(text, limit=120):
    names = set()
    for pattern in MODEL_NAME_PATTERNS:
        for item in pattern.findall(text):
            value = " ".join(str(item).split()).strip(" .,;:'\"")
            if value and len(value) <= 80 and not any(p.search(value) for p in NON_MODEL_NAME_PATTERNS):
                names.add(value)
    return sorted(names, key=str.lower)[:limit]


def probe_web_assets(max_scripts=12, max_script_bytes=4_000_000):
    account_prefix = _account_prefix()
    app_url = f"https://gemini.google.com{account_prefix}/app"
    headers = _build_headers()
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    page_status, page_headers, page_bytes = _fetch(app_url, headers=headers)
    html = page_bytes.decode("utf-8", errors="replace")
    script_urls = _script_urls(html, app_url)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": app_url,
        "page": {
            "status": page_status,
            "bytes": len(page_bytes),
            "sha256": hashlib.sha256(page_bytes).hexdigest(),
            "bl": (re.search(r"boq_assistant-bard-web-server_[\w.]+", html) or [None])[0],
            "keywords": _keyword_hits(html),
            "script_count": len(script_urls),
        },
        "scripts": [],
        "keyword_counts": {},
        "rpc_like_ids": [],
        "model_like_names": [],
    }

    rpc_ids = set()
    model_names = set(_extract_model_like_names(html))
    keyword_counts = {}
    for url in script_urls[:max_scripts]:
        item = {
            "url_host": urllib.parse.urlparse(url).netloc,
            "url_path": urllib.parse.urlparse(url).path,
            "status": None,
            "bytes": 0,
            "sha256": None,
            "keywords": [],
            "rpc_like_ids": [],
            "truncated": False,
        }
        try:
            status, resp_headers, body = _fetch(url, headers={"User-Agent": UA, "Referer": app_url}, timeout=60)
            item["status"] = status
            item["bytes"] = len(body)
            item["sha256"] = hashlib.sha256(body).hexdigest()
            if len(body) > max_script_bytes:
                body = body[:max_script_bytes]
                item["truncated"] = True
            text = body.decode("utf-8", errors="replace")
            item["keywords"] = _keyword_hits(text)
            item["rpc_like_ids"] = _extract_rpc_like_ids(text)
            item["model_like_names"] = _extract_model_like_names(text, limit=30)
            rpc_ids.update(item["rpc_like_ids"])
            model_names.update(item["model_like_names"])
            for keyword in item["keywords"]:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        except Exception as exc:
            item["error"] = str(exc)[:180]
        report["scripts"].append(item)

    for keyword in report["page"]["keywords"]:
        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
    report["keyword_counts"] = keyword_counts
    report["rpc_like_ids"] = sorted(rpc_ids)
    report["model_like_names"] = sorted(model_names, key=str.lower)[:120]
    return report


def main():
    parser = argparse.ArgumentParser(description="Probe Gemini Web page and JS assets for capability evidence.")
    parser.add_argument("--config")
    parser.add_argument("--cookie-file")
    parser.add_argument("--auth-user")
    parser.add_argument("--proxy")
    parser.add_argument("--max-scripts", type=int, default=12)
    parser.add_argument("--out", default=os.path.join("output", "web_probe.json"))
    args = parser.parse_args()

    cfg_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if cfg_path:
        load_config(cfg_path)
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file
    if args.auth_user is not None:
        CONFIG["auth_user"] = args.auth_user
    if args.proxy:
        CONFIG["proxy"] = args.proxy

    report = probe_web_assets(max_scripts=args.max_scripts)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps({
        "report_path": args.out,
        "page_status": report["page"]["status"],
        "script_count": report["page"]["script_count"],
        "fetched_scripts": len(report["scripts"]),
        "keyword_counts": report["keyword_counts"],
        "model_like_names": report["model_like_names"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
