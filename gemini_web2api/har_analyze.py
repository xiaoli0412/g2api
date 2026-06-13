"""Sanitized HAR analyzer for Gemini Web traffic evidence."""
import argparse
import json
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path


KEYWORD_PATTERNS = {
    "StreamGenerate": re.compile(r"StreamGenerate", re.I),
    "content_push": re.compile(r"content-push|contrib_service|X-Goog-Upload", re.I),
    "BardErrorInfo": re.compile(r"BardErrorInfo", re.I),
    "Create image": re.compile(r"Create image|Imagen|image_generation|generate image", re.I),
    "Create video": re.compile(r"Create video|Veo|video_generation|generate video", re.I),
    "Canvas": re.compile(r"Canvas|canvas", re.I),
    "Deep research": re.compile(r"Deep research|deep_research", re.I),
    "NotebookLM": re.compile(r"NotebookLM", re.I),
    "Music": re.compile(r"Music|music", re.I),
    "Photos": re.compile(r"Photos|photos", re.I),
    "file_related": re.compile(r"attach|upload|file|image/png|image/jpeg|image/webp|video/mp4|audio/", re.I),
}

SENSITIVE_HEADERS = {"cookie", "authorization", "proxy-authorization"}


def _safe_url_parts(url):
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc, parsed.path


def _shape_value(value):
    if value is None:
        return "null"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    if isinstance(value, str):
        return f"str:{len(value)}"
    if isinstance(value, bool):
        return f"bool:{value}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        return "float"
    return type(value).__name__


def _parse_stream_shape(post_text):
    parsed = urllib.parse.parse_qs(post_text or "")
    freq = parsed.get("f.req", [""])[0]
    if not freq:
        return {"parse_error": "missing f.req"}
    try:
        outer = json.loads(freq)
        inner_raw = outer[1] if isinstance(outer, list) and len(outer) > 1 else None
        inner = json.loads(inner_raw) if isinstance(inner_raw, str) else inner_raw
        if not isinstance(inner, list):
            return {"parse_error": "inner payload is not a list"}
        non_null = []
        fields = {}
        for idx, value in enumerate(inner):
            if value is not None:
                shape = _shape_value(value)
                non_null.append([idx, shape])
                fields[str(idx)] = shape
        return {"inner_len": len(inner), "non_null": non_null, "fields": fields}
    except Exception as exc:
        return {"parse_error": repr(exc)[:160]}


def _safe_json_loads(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _shape_leaf(value):
    if value is None:
        return "null"
    if isinstance(value, str):
        return f"str:{len(value)}"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    return type(value).__name__


def _shape_tree(value, depth=0, max_depth=3):
    """Return a compact shape for nested values without preserving content."""
    if depth >= max_depth:
        return _shape_leaf(value)
    if isinstance(value, list):
        preview = [_shape_tree(item, depth + 1, max_depth) for item in value[:8]]
        result = {"type": "list", "len": len(value)}
        if preview:
            result["items"] = preview
        return result
    if isinstance(value, dict):
        return {"type": "dict", "len": len(value)}
    return _shape_leaf(value)


def _parse_batchexecute_calls(post_text):
    """Parse batchexecute f.req calls and return sanitized call records.

    Expected Gemini Web shape:
      f.req=[[[rpcid, args_json, null, "generic"]]]

    The returned records intentionally exclude argument values and response text.
    """
    parsed = urllib.parse.parse_qs(post_text or "")
    freq = parsed.get("f.req", [""])[0]
    if not freq:
        return []
    outer = _safe_json_loads(freq)
    if not isinstance(outer, list):
        return []

    records = []
    batches = outer if outer and isinstance(outer[0], list) else [outer]
    for batch in batches:
        if not isinstance(batch, list):
            continue
        for call in batch:
            if not (isinstance(call, list) and call and isinstance(call[0], str)):
                continue
            rpcid = call[0]
            args_raw = call[1] if len(call) > 1 else None
            args = _safe_json_loads(args_raw)
            records.append({
                "rpcid": rpcid,
                "call_len": len(call),
                "args_json": isinstance(args_raw, str),
                "args_shape": _shape_tree(args) if args is not None else _shape_value(args_raw),
                "protocol": _shape_value(call[3]) if len(call) > 3 else "missing",
            })
    return records


def _marker_counts(value: str) -> dict:
    value = value or ""
    return {
        "http_url": len(re.findall(r"https?://", value)),
        "googleusercontent": len(re.findall(r"googleusercontent", value, re.I)),
        "image": len(re.findall(r"\bimage\b|image/|image_url|Imagen|Nano Banana", value, re.I)),
        "video": len(re.findall(r"\bvideo\b|video/|video_url|mp4|webm|Veo|Omni", value, re.I)),
        "audio": len(re.findall(r"\baudio\b|audio/|audio_url|mp3|wav|Lyria|Music", value, re.I)),
        "task_status": len(re.findall(r"\btask\b|\bstatus\b|\bjob\b|\boperation\b", value, re.I)),
    }


def _parse_batchexecute_response_records(content):
    """Parse sanitized wrb.fr records from a batchexecute response."""
    records = []
    for line in (content or "").splitlines():
        line = line.strip()
        if not line or line.startswith(")]}'"):
            continue
        obj = _safe_json_loads(line)
        if not isinstance(obj, list):
            continue
        for rec in obj:
            if not (isinstance(rec, list) and len(rec) >= 3 and rec[0] == "wrb.fr"):
                continue
            rpcid = rec[1] if isinstance(rec[1], str) else ""
            payload_raw = rec[2] if isinstance(rec[2], str) else ""
            payload = _safe_json_loads(payload_raw)
            records.append({
                "rpcid": rpcid,
                "record_len": len(rec),
                "payload_json": payload is not None,
                "payload_shape": _shape_tree(payload) if payload is not None else _shape_leaf(payload_raw),
                "payload_markers": _marker_counts(payload_raw),
            })
    return records


def _size_range(existing, value):
    if existing is None:
        return {"min": value, "max": value}
    existing["min"] = min(existing["min"], value)
    existing["max"] = max(existing["max"], value)
    return existing


def analyze_har(path, max_items=80):
    """Analyze a HAR file without returning sensitive header values or prompt text."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        har = json.load(handle)

    entries = har.get("log", {}).get("entries", [])
    hosts = Counter()
    paths = Counter()
    statuses = Counter()
    rpcids = Counter()
    keywords = Counter()
    sensitive_header_counts = Counter()
    stream_generate = []
    upload_or_file_related = []
    batchexecute_features = []
    rpc_catalog = {}

    for index, entry in enumerate(entries):
        request = entry.get("request", {})
        response = entry.get("response", {})
        method = request.get("method", "")
        url = request.get("url", "")
        host, path_only = _safe_url_parts(url)
        hosts[host] += 1
        paths[(method, host, path_only)] += 1
        statuses[str(response.get("status"))] += 1

        for header in request.get("headers", []):
            name = header.get("name", "").lower()
            if name in SENSITIVE_HEADERS or name.startswith("x-goog-"):
                sensitive_header_counts[name] += 1

        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        for rpcid in query.get("rpcids", []):
            rpcids[rpcid] += 1

        post_text = (request.get("postData") or {}).get("text") or ""
        content = (response.get("content") or {}).get("text") or ""
        searchable = " ".join([url, post_text[:200000], content[:200000]])
        hits = [name for name, pattern in KEYWORD_PATTERNS.items() if pattern.search(searchable)]
        for hit in hits:
            keywords[hit] += 1

        base_item = {
            "index": index,
            "method": method,
            "host": host,
            "path": path_only,
            "status": response.get("status"),
            "mime": (response.get("content") or {}).get("mimeType"),
            "response_size": (response.get("content") or {}).get("size"),
            "post_length": len(post_text),
            "keywords": hits,
        }
        if "StreamGenerate" in path_only:
            stream_generate.append({**base_item, "shape": _parse_stream_shape(post_text)})
        if "content-push" in host or "content_push" in hits or "file_related" in hits:
            upload_or_file_related.append(base_item)
        if path_only.endswith("/batchexecute"):
            calls = _parse_batchexecute_calls(post_text)
            for call in calls:
                rpcid = call["rpcid"]
                rpcids[rpcid] += 1
                item = rpc_catalog.setdefault(rpcid, {
                    "rpcid": rpcid,
                    "count": 0,
                    "statuses": Counter(),
                    "keywords": Counter(),
                    "post_length": None,
                    "response_size": None,
                    "arg_shapes": Counter(),
                    "response_payload_shapes": Counter(),
                    "response_markers": Counter(),
                    "protocols": Counter(),
                    "sample_indexes": [],
                })
                item["count"] += 1
                item["statuses"][str(response.get("status"))] += 1
                for hit in hits:
                    item["keywords"][hit] += 1
                item["post_length"] = _size_range(item["post_length"], len(post_text))
                item["response_size"] = _size_range(item["response_size"], (response.get("content") or {}).get("size") or 0)
                item["arg_shapes"][json.dumps(call["args_shape"], sort_keys=True, ensure_ascii=False)] += 1
                item["protocols"][call["protocol"]] += 1
                if len(item["sample_indexes"]) < 8:
                    item["sample_indexes"].append(index)
            for response_record in _parse_batchexecute_response_records(content):
                rpcid = response_record["rpcid"]
                if not rpcid:
                    continue
                item = rpc_catalog.setdefault(rpcid, {
                    "rpcid": rpcid,
                    "count": 0,
                    "statuses": Counter(),
                    "keywords": Counter(),
                    "post_length": None,
                    "response_size": None,
                    "arg_shapes": Counter(),
                    "response_payload_shapes": Counter(),
                    "response_markers": Counter(),
                    "protocols": Counter(),
                    "sample_indexes": [],
                })
                item["response_payload_shapes"][
                    json.dumps(response_record["payload_shape"], sort_keys=True, ensure_ascii=False)
                ] += 1
                for marker, count in response_record["payload_markers"].items():
                    item["response_markers"][marker] += count

        if path_only.endswith("/batchexecute") and hits:
            batchexecute_features.append({
                **base_item,
                "rpcids": query.get("rpcids", [])[:8],
            })

    rpc_catalog_items = []
    for item in sorted(rpc_catalog.values(), key=lambda value: (-value["count"], value["rpcid"]))[:max_items]:
        arg_shapes = []
        for shape_json, count in item["arg_shapes"].most_common(5):
            shape = _safe_json_loads(shape_json)
            arg_shapes.append({"count": count, "shape": shape if shape is not None else shape_json})
        response_payload_shapes = []
        for shape_json, count in item["response_payload_shapes"].most_common(5):
            shape = _safe_json_loads(shape_json)
            response_payload_shapes.append({"count": count, "shape": shape if shape is not None else shape_json})
        rpc_catalog_items.append({
            "rpcid": item["rpcid"],
            "count": item["count"],
            "statuses": dict(item["statuses"]),
            "keywords": dict(item["keywords"]),
            "post_length": item["post_length"],
            "response_size": item["response_size"],
            "arg_shapes": arg_shapes,
            "response_payload_shapes": response_payload_shapes,
            "response_markers": dict(item["response_markers"]),
            "protocols": dict(item["protocols"]),
            "sample_indexes": item["sample_indexes"],
        })

    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "entries": len(entries),
        "creator": har.get("log", {}).get("creator", {}),
        "hosts": hosts.most_common(30),
        "paths": [
            {"method": method, "host": host, "path": path_only, "count": count}
            for (method, host, path_only), count in paths.most_common(60)
        ],
        "statuses": dict(statuses),
        "rpcids": rpcids.most_common(80),
        "keywords": dict(keywords),
        "sensitive_header_counts": dict(sensitive_header_counts),
        "stream_generate": stream_generate[:max_items],
        "upload_or_file_related": upload_or_file_related[:max_items],
        "batchexecute_features": batchexecute_features[:max_items],
        "rpc_catalog": rpc_catalog_items,
    }


def main():
    parser = argparse.ArgumentParser(description="Create a sanitized Gemini Web HAR analysis report.")
    parser.add_argument("har", help="Path to .har file")
    parser.add_argument("--out", help="Output JSON path")
    parser.add_argument("--max-items", type=int, default=80)
    args = parser.parse_args()

    report = analyze_har(args.har, max_items=args.max_items)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        print(json.dumps({"report_path": args.out, "entries": report["entries"]}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
