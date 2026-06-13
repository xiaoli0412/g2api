"""Live verification runner for real Gemini Web proxy checks."""
import argparse
import base64
import json
import os
import threading
import time
import uuid

from .config import CONFIG, find_config, load_config


DEFAULT_PROMPT = "Who are you"
PIXEL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
    "AAAADUlEQVR42mP8z8BQDwAFgwJ/l2JxNwAAAABJRU5ErkJggg=="
)


def _shorten(value, limit=360):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return value[:limit] + ("..." if len(value) > limit else "")


def _record(results, name, status, http_status=None, detail="", extra=None):
    item = {
        "name": name,
        "status": status,
    }
    if http_status is not None:
        item["http_status"] = http_status
    if detail:
        item["detail"] = _shorten(detail)
    if extra:
        item.update(extra)
    results.append(item)
    return item


def summarize_results(results):
    counts = {}
    for item in results:
        status = item.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(results),
        "counts": counts,
        "failed": [r["name"] for r in results if r.get("status") == "fail"],
        "limited": [r["name"] for r in results if r.get("status") == "limited"],
    }


def _chat_text(data):
    return data["choices"][0]["message"].get("content") or data["choices"][0]["message"]


def _responses_text(data):
    parts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        elif item.get("type") == "function_call":
            parts.append(f"function_call {item.get('name')} {item.get('arguments')}")
    return " ".join(parts)


def _claude_text(data):
    parts = []
    for item in data.get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
        elif item.get("type") == "tool_use":
            parts.append(f"tool_use {item.get('name')} {json.dumps(item.get('input'), ensure_ascii=False)}")
    return " ".join(parts)


def _google_text(data):
    parts = data["candidates"][0]["content"]["parts"]
    out = []
    for part in parts:
        if "text" in part:
            out.append(part["text"])
        if "functionCall" in part:
            out.append("functionCall " + json.dumps(part["functionCall"], ensure_ascii=False))
    return " ".join(out)


def _headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _get_json(client, results, name, path, api_key=None):
    try:
        response = client.get(path, headers=_headers(api_key))
        data = response.json()
        status = "pass" if response.status_code == 200 and not data.get("error") else "fail"
        _record(results, name, status, response.status_code, extra={"keys": list(data.keys())[:8]})
        return data
    except Exception as exc:
        _record(results, name, "fail", detail=repr(exc))
        return None


def _post_json(client, results, name, path, body, extractor=None, api_key=None):
    try:
        response = client.post(path, json=body, headers=_headers(api_key))
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}
        status = "pass" if response.status_code == 200 and not data.get("error") else "fail"
        detail = extractor(data) if extractor else data
        _record(results, name, status, response.status_code, detail)
        return data
    except Exception as exc:
        _record(results, name, "fail", detail=repr(exc))
        return None


def _stream_openai(client, results, prompt, api_key=None):
    body = {
        "model": "gemini-3.5-flash",
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    chunks = []
    done = False
    http_status = None
    try:
        with client.stream("POST", "/v1/chat/completions", json=body, headers=_headers(api_key)) as response:
            http_status = response.status_code
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload == "[DONE]":
                        done = True
                        break
                    try:
                        obj = json.loads(payload)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            chunks.append(delta)
                    except Exception:
                        pass
        _record(
            results,
            "openai_chat_stream",
            "pass" if http_status == 200 and done and chunks else "fail",
            http_status,
            "".join(chunks),
            {"chunks": len(chunks), "done": done},
        )
    except Exception as exc:
        _record(results, "openai_chat_stream", "fail", http_status, repr(exc))


def _stream_google(client, results, prompt, api_key=None):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    text = []
    http_status = None
    try:
        with client.stream(
            "POST",
            "/v1beta/models/gemini-3.5-flash:streamGenerateContent",
            json=body,
            headers=_headers(api_key),
        ) as response:
            http_status = response.status_code
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                try:
                    obj = json.loads(line[6:])
                    for part in obj.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                        if "text" in part:
                            text.append(part["text"])
                except Exception:
                    pass
        _record(
            results,
            "google_stream_generate_content",
            "pass" if http_status == 200 and text else "fail",
            http_status,
            "".join(text),
            {"chunks": len(text)},
        )
    except Exception as exc:
        _record(results, "google_stream_generate_content", "fail", http_status, repr(exc))


def _multimodal_checks(client, results, api_key=None):
    from .multimodal import upload_file

    file_bytes = base64.b64decode(PIXEL_PNG_B64)
    file_ref = ""
    try:
        file_ref = upload_file(file_bytes, "pixel.png", "image/png")
        _record(
            results,
            "multimodal_upload",
            "pass" if file_ref.startswith("/") else "fail",
            detail={"ref_prefix": file_ref[:48]},
        )
    except Exception as exc:
        _record(results, "multimodal_upload", "fail", detail=repr(exc))

    body = {
        "model": "gemini-3.5-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this image? Answer briefly."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + PIXEL_PNG_B64},
                    },
                ],
            }
        ],
    }
    data = _post_json(client, results, "multimodal_prompt", "/v1/chat/completions", body, api_key=api_key)
    item = results[-1]
    if item["status"] == "fail" and "BardErrorInfo [1003]" in item.get("detail", ""):
        item["status"] = "limited"
        item["note"] = "Upload succeeded, but Gemini Web rejected the final private StreamGenerate handoff."
    elif isinstance(data, dict):
        status = data.get("multimodal_status") or {}
        if status.get("runtime_status") == "limited":
            item["status"] = "limited"
            item["multimodal_status"] = status
            item["note"] = "Image/file input fell back to text-only; no verified visual understanding was returned."


def _media_counts(data):
    media = data.get("media") or []
    images = data.get("images") or []
    return {
        "images": len(images),
        "video": len([item for item in media if item.get("kind") == "video"]),
        "audio": len([item for item in media if item.get("kind") == "audio"]),
    }


def _web_tool_checks(client, results, prompt=DEFAULT_PROMPT, api_key=None):
    source_model_checks = [
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-flash-preview-09-2025",
        "gemini-3-flash-preview",
        "gemini-advanced",
    ]
    for model in source_model_checks:
        _post_json(
            client,
            results,
            f"source_model_alias_{model}",
            "/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )

    alias_checks = [
        ("web_tool_alias_image_generation", "nano-banana-2", "image_generation"),
        ("web_tool_alias_video_generation", "omni", "video_generation"),
        ("web_tool_alias_music", "lyria-3", "music"),
        ("web_tool_alias_text_to_speech", "gemini-2.5-flash-preview-tts", "text_to_speech"),
        ("web_tool_alias_deep_research", "gemini-deep-research", "deep_research"),
        ("web_tool_alias_canvas", "gemini-canvas", "canvas"),
        ("web_tool_alias_photos", "gemini-photos", "photos"),
        ("web_tool_alias_library", "gemini-library", "library"),
        ("web_tool_alias_notebook", "gemini-notebook", "notebook"),
    ]
    for name, model, feature_id in alias_checks:
        data = _post_json(
            client,
            results,
            name,
            "/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )
        item = results[-1]
        web_feature = data.get("web_feature") if isinstance(data, dict) else None
        if item["status"] == "pass" and web_feature:
            item["web_feature"] = web_feature
            item["note"] = f"{feature_id} alias returned a real response for the verification prompt."

    artifact_checks = [
        (
            "web_tool_artifact_image_generation",
            "nano-banana-2",
            "Create an image of a single blue square on a white background. Return the image.",
            "image_generation",
        ),
        (
            "web_tool_artifact_video_generation",
            "omni",
            "Create a two-second video of a single blue square moving left to right.",
            "video_generation",
        ),
        (
            "web_tool_artifact_music",
            "lyria-3",
            "Create a five-second calm instrumental loop and return the audio.",
            "music",
        ),
        (
            "web_tool_artifact_text_to_speech",
            "gemini-2.5-flash-preview-tts",
            "Read these words aloud and return the audio: Who are you",
            "text_to_speech",
        ),
    ]
    for name, model, artifact_prompt, feature_id in artifact_checks:
        data = _post_json(
            client,
            results,
            name,
            "/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": artifact_prompt}]},
            _chat_text,
            api_key,
        )
        item = results[-1]
        web_feature = data.get("web_feature") if isinstance(data, dict) else None
        counts = _media_counts(data) if isinstance(data, dict) else {}
        if item["status"] == "pass" and web_feature:
            runtime = web_feature.get("runtime_status")
            item["web_feature"] = web_feature
            item["media_counts"] = counts
            if runtime != "supported":
                item["status"] = "limited"
                item["note"] = f"{feature_id} alias is callable, but no verified generated artifact was returned."

    endpoint_checks = [
        (
            "openai_image_generation_endpoint",
            "/v1/images/generations",
            {
                "model": "nano-banana-2",
                "prompt": "Create an image of a single blue square on a white background. Return the image.",
            },
            "image_generation",
        ),
        (
            "openai_video_generation_endpoint",
            "/v1/videos/generations",
            {
                "model": "omni",
                "prompt": "Create a two-second video of a single blue square moving left to right.",
            },
            "video_generation",
        ),
        (
            "openai_audio_speech_endpoint",
            "/v1/audio/speech",
            {
                "model": "gemini-2.5-flash-preview-tts",
                "input": prompt,
                "response_format": "json",
            },
            "text_to_speech",
        ),
    ]
    for name, path, body, feature_id in endpoint_checks:
        data = _post_json(client, results, name, path, body, api_key=api_key)
        item = results[-1]
        web_feature = data.get("web_feature") if isinstance(data, dict) else None
        data_count = len(data.get("data") or []) if isinstance(data, dict) else 0
        if item["status"] == "pass" and web_feature:
            item["web_feature"] = web_feature
            item["data_count"] = data_count
            if web_feature.get("runtime_status") != "supported" or data_count == 0:
                item["status"] = "limited"
                item["note"] = f"{feature_id} endpoint is callable, but no verified generated artifact was returned."


def run_live_checks(base_url, prompt=DEFAULT_PROMPT, api_key=None, include_multimodal=True, include_web_tools=False):
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for live verification") from exc

    timeout = httpx.Timeout(120.0, connect=10.0)
    results = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        _get_json(client, results, "root", "/")
        models = _get_json(client, results, "openai_models", "/v1/models", api_key=api_key)
        if models:
            count = len(models.get("data", []))
            _record(results, "model_count", "pass" if count else "fail", detail=str(count))
        _get_json(client, results, "gemini_models", "/v1beta/models", api_key=api_key)
        _get_json(client, results, "capabilities", "/api/capabilities", api_key=api_key)
        _get_json(client, results, "admin_cookie_health", "/admin/cookie/health", api_key=api_key)
        _get_json(client, results, "dashboard_api", "/api/dashboard", api_key=api_key)
        cookie_status = _get_json(client, results, "cookie_status_api", "/api/cookie/status", api_key=api_key)
        if include_web_tools and isinstance(cookie_status, dict):
            diagnostics = cookie_status.get("diagnostics") or {}
            web_ready = bool(cookie_status.get("web_ui_likely_complete"))
            _record(
                results,
                "cookie_full_web_ui_ready",
                "pass" if web_ready else "limited",
                detail={
                    "api_streamgenerate_ready": cookie_status.get("api_streamgenerate_ready"),
                    "web_ui_likely_complete": web_ready,
                    "missing": diagnostics.get("web_ui_missing_strong", []),
                    "internal_browser": (cookie_status.get("internal_browser") or {}).get("available_backends", []),
                },
            )

        _post_json(
            client,
            results,
            "openai_chat",
            "/v1/chat/completions",
            {"model": "gemini-3.5-flash", "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )
        _stream_openai(client, results, prompt, api_key)
        _post_json(
            client,
            results,
            "responses_api",
            "/v1/responses",
            {"model": "gemini-3.5-flash", "input": prompt},
            _responses_text,
            api_key,
        )
        _post_json(
            client,
            results,
            "claude_messages",
            "/v1/messages",
            {"model": "gemini-3.5-flash", "max_tokens": 256, "messages": [{"role": "user", "content": prompt}]},
            _claude_text,
            api_key,
        )
        _post_json(
            client,
            results,
            "google_generate_content",
            "/v1beta/models/gemini-3.5-flash:generateContent",
            {"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            _google_text,
            api_key,
        )
        _stream_google(client, results, prompt, api_key)
        _post_json(
            client,
            results,
            "openai_tool_call",
            "/v1/chat/completions",
            {
                "model": "gemini-3.5-flash",
                "messages": [{"role": "user", "content": "Who are you? Use the function to identify yourself."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "identify_self",
                            "description": "Identify assistant name",
                            "parameters": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                            },
                        },
                    }
                ],
                "tool_choice": {"type": "function", "function": {"name": "identify_self"}},
            },
            lambda data: data.get("choices", [{}])[0].get("message", {}),
            api_key,
        )
        _post_json(
            client,
            results,
            "google_function_call_any",
            "/v1beta/models/gemini-3.5-flash:generateContent",
            {
                "contents": [{"role": "user", "parts": [{"text": "Who are you? Call identify_self."}]}],
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "identify_self",
                                "description": "Identify assistant name",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                    "required": ["name"],
                                },
                            }
                        ]
                    }
                ],
                "toolConfig": {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": ["identify_self"],
                    }
                },
            },
            _google_text,
            api_key,
        )
        _post_json(
            client,
            results,
            "search_model",
            "/v1/chat/completions",
            {"model": "gemini-3.5-flash-search", "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )
        _post_json(
            client,
            results,
            "thinking_model",
            "/v1/chat/completions",
            {"model": "gemini-3.5-flash-thinking", "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )
        _post_json(
            client,
            results,
            "pro_model_cookie_route",
            "/v1/chat/completions",
            {"model": "gemini-3.1-pro", "messages": [{"role": "user", "content": prompt}]},
            _chat_text,
            api_key,
        )
        if include_multimodal:
            _multimodal_checks(client, results, api_key)
        if include_web_tools:
            _web_tool_checks(client, results, prompt, api_key)
    return results


def _start_server(port, cookie_file=None, config_path=None, proxy=None, auth_user=None):
    from .admin import init_admin
    from .server import GeminiHandler, ThreadedServer

    if config_path:
        load_config(config_path)
    if port:
        CONFIG["port"] = port
    if cookie_file:
        CONFIG["cookie_file"] = cookie_file
    if auth_user is not None:
        CONFIG["auth_user"] = auth_user
    if proxy:
        CONFIG["proxy"] = proxy
    init_admin()

    server = ThreadedServer((CONFIG["host"], CONFIG["port"]), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _wait_for_server(base_url, seconds=30):
    try:
        import httpx
    except ImportError:
        return
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            response = httpx.get(base_url.rstrip("/") + "/", timeout=2)
            if response.status_code < 500:
                return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready: {base_url}")


def _run_source_probe(out_dir, cookie_file=None):
    from .source_probe import probe_sources
    from .gemini import load_cookie

    cookie_override = None
    if cookie_file:
        old_cookie_file = CONFIG.get("cookie_file")
        CONFIG["cookie_file"] = cookie_file
        try:
            cookie_override = load_cookie()
        finally:
            CONFIG["cookie_file"] = old_cookie_file
    return probe_sources(out_dir, include_auth=True, cookie_override=cookie_override)


def main():
    parser = argparse.ArgumentParser(description="Run real live checks against gemini-web2api.")
    parser.add_argument("--base-url", default=None, help="Existing server base URL, e.g. http://127.0.0.1:8081")
    parser.add_argument("--start-server", action="store_true", help="Start a temporary in-process server.")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--config", default=None)
    parser.add_argument("--cookie-file", default=None)
    parser.add_argument("--auth-user", default=None, help="Google account index path, e.g. 1 for /u/1/app")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--skip-multimodal", action="store_true")
    parser.add_argument("--include-web-tools", action="store_true", help="Call experimental Gemini Web tool aliases.")
    parser.add_argument("--source-probe", action="store_true")
    parser.add_argument("--out", default=None, help="Report path or output directory.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on failed checks.")
    parser.add_argument("--strict-limited", action="store_true", help="Treat limited checks as failures.")
    args = parser.parse_args()

    cfg_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if cfg_path and not args.start_server:
        load_config(cfg_path)
    if args.cookie_file and not args.start_server:
        CONFIG["cookie_file"] = args.cookie_file
    if args.auth_user is not None and not args.start_server:
        CONFIG["auth_user"] = args.auth_user
    if args.proxy and not args.start_server:
        CONFIG["proxy"] = args.proxy

    server = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    if args.start_server:
        server, _ = _start_server(args.port, args.cookie_file, cfg_path, args.proxy, args.auth_user)
        _wait_for_server(base_url)

    out_path = args.out
    if not out_path:
        os.makedirs("output", exist_ok=True)
        out_path = os.path.join("output", f"live_verify_{time.strftime('%Y%m%d_%H%M%S')}.json")
    if os.path.isdir(out_path) or out_path.endswith(os.sep):
        os.makedirs(out_path, exist_ok=True)
        out_path = os.path.join(out_path, f"live_verify_{uuid.uuid4().hex[:8]}.json")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    try:
        results = run_live_checks(
            base_url,
            prompt=args.prompt,
            api_key=args.api_key,
            include_multimodal=not args.skip_multimodal,
            include_web_tools=args.include_web_tools,
        )
        report = {
            "base_url": base_url,
            "prompt": args.prompt,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summarize_results(results),
            "results": results,
        }
        if args.source_probe:
            probe_root = os.path.join(os.path.dirname(os.path.abspath(out_path)), "source_probe")
            report["source_probe"] = _run_source_probe(probe_root, args.cookie_file)
            for key in ("anonymous", "authenticated"):
                if report["source_probe"].get(key):
                    report["source_probe"][key].pop("scripts", None)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        print(json.dumps({"summary": report["summary"], "report_path": out_path}, indent=2, ensure_ascii=False))
        if args.strict and report["summary"]["failed"]:
            raise SystemExit(1)
        if args.strict_limited and (report["summary"]["failed"] or report["summary"]["limited"]):
            raise SystemExit(1)
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
