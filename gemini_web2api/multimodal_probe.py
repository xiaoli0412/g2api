"""Real upstream multimodal payload probe.

This module is intentionally diagnostic. It tries several known Gemini Web
file-reference payload shapes and records sanitized outcomes. It does not
print cookies, prompts, upload URLs, or full upstream responses.
"""
import argparse
import base64
import json
import os
import time
import urllib.parse
import urllib.request

from .config import CONFIG, find_config, load_config
from .gemini import _build_headers, _get_ssl_ctx, _get_url, extract_response_text, log
from .multimodal import upload_file


PIXEL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
    "AAAADUlEQVR42mP8z8BQDwAFgwJ/l2JxNwAAAABJRU5ErkJggg=="
)


def _short(value, limit=240):
    value = str(value or "")
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return value[:limit] + ("..." if len(value) > limit else "")


def _payload_for_variant(prompt, file_ref, variant):
    inner_len = variant.get("inner_len", 102)
    inner = [None] * inner_len
    refs = variant["refs"](file_ref)
    inner[0] = [prompt, 0, None, refs, None, None, 0]
    inner[1] = ["en"]
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    for idx, value in {
        6: [0],
        7: 1,
        10: 1,
        11: 0,
        17: [[variant.get("think", 4)]],
        18: 0,
        27: 1,
        30: variant.get("field30", [4]),
        41: variant.get("field41", [2]),
        53: 0,
        59: variant.get("request_id", "00000000-0000-4000-8000-000000000000"),
        61: [],
        68: variant.get("field68", 1),
        79: variant.get("model_id", 1),
        80: variant.get("field80"),
    }.items():
        if idx < inner_len and value is not None:
            inner[idx] = value
    return urllib.parse.urlencode({"f.req": json.dumps([None, json.dumps(inner)])})


def _post_payload(body):
    req = urllib.request.Request(_get_url(), data=body.encode(), headers=_build_headers(), method="POST")
    proxy = CONFIG.get("proxy")
    ctx = _get_ssl_ctx()
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=ctx),
        )
        resp = opener.open(req, timeout=CONFIG["request_timeout_sec"])
    else:
        resp = urllib.request.urlopen(req, context=ctx, timeout=CONFIG["request_timeout_sec"])
    raw = resp.read().decode("utf-8", errors="replace")
    return getattr(resp, "status", 200), raw


def _variants():
    return [
        {
            "name": "current",
            "refs": lambda ref: [[None, None, ref]],
        },
        {
            "name": "current_har_fields",
            "refs": lambda ref: [[None, None, ref]],
            "field68": 2,
            "field80": 1,
            "inner_len": 81,
        },
        {
            "name": "current_68_2",
            "refs": lambda ref: [[None, None, ref]],
            "field68": 2,
        },
        {
            "name": "current_80_1",
            "refs": lambda ref: [[None, None, ref]],
            "field80": 1,
        },
        {
            "name": "list_ref_filename",
            "refs": lambda ref: [[[ref], "pixel.png"]],
        },
        {
            "name": "list_ref_filename_har_fields",
            "refs": lambda ref: [[[ref], "pixel.png"]],
            "field68": 2,
            "field80": 1,
            "inner_len": 81,
        },
        {
            "name": "plain_ref",
            "refs": lambda ref: [ref],
        },
        {
            "name": "nested_ref_only",
            "refs": lambda ref: [[ref]],
        },
        {
            "name": "object_ref",
            "refs": lambda ref: [{"path": ref, "name": "pixel.png", "mimeType": "image/png"}],
        },
    ]


def run_probe(prompt="What color is this image? Answer briefly."):
    png = base64.b64decode(PIXEL_PNG_B64)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "auth_user": CONFIG.get("auth_user"),
        "upload": None,
        "variants": [],
    }
    file_ref = upload_file(png, "pixel.png", "image/png")
    report["upload"] = {
        "ok": bool(file_ref and file_ref.startswith("/")),
        "ref_prefix": file_ref[:48],
    }
    for variant in _variants():
        item = {
            "name": variant["name"],
            "status": "fail",
            "http_status": None,
            "error": None,
            "text_preview": "",
        }
        try:
            body = _payload_for_variant(prompt, file_ref, variant)
            status, raw = _post_payload(body)
            item["http_status"] = status
            text = extract_response_text(raw)
            item["status"] = "pass" if text else "fail"
            item["text_preview"] = _short(text)
        except Exception as exc:
            item["error"] = _short(exc)
            if "BardErrorInfo [1003]" in item["error"]:
                item["status"] = "limited"
        report["variants"].append(item)
        log(f"Multimodal probe {item['name']}: {item['status']} {item.get('error') or item.get('text_preview')}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Probe real Gemini Web multimodal payload variants.")
    parser.add_argument("--config")
    parser.add_argument("--cookie-file")
    parser.add_argument("--auth-user")
    parser.add_argument("--proxy")
    parser.add_argument("--out", default=os.path.join("output", "multimodal_probe.json"))
    parser.add_argument("--prompt", default="What color is this image? Answer briefly.")
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

    report = run_probe(args.prompt)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps({
        "report_path": args.out,
        "upload_ok": report["upload"]["ok"],
        "counts": {
            status: sum(1 for item in report["variants"] if item["status"] == status)
            for status in sorted({item["status"] for item in report["variants"]})
        },
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
