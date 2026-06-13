"""HTTP server: OpenAI-compatible API endpoints."""
import base64
import json
import mimetypes
import os
import time
import uuid
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from .config import CONFIG
from .models import WEB_FEATURES, resolve_model
from .gemini import (
    generate_with_metadata,
    generate_stream,
    log,
    extract_images_from_response,
    extract_media_from_response,
    extract_artifacts_from_response,
)
from .stats import add_log, log_request
from .tools import messages_to_prompt, parse_tool_calls, google_contents_to_prompt, parse_google_function_calls
from .multimodal import upload_file, fetch_file_bytes
from .artifact_store import materialize_response_files, resolve_artifact_path
from .adapters import parse_claude_request, convert_openai_response_to_claude
from . import __version__


PROTECTED_PREFIXES = ("/v1/", "/v1beta/", "/admin", "/api/")
SECRET_CONFIG_KEYS = {"xsrf_token", "api_keys", "proxy", "proxies", "proxy_subscriptions", "proxy_import_sources"}
MASKED_SECRET_VALUES = {"*", "**", "***", "****", "*****", "********", "<redacted>"}
PROXY_CONFIG_KEYS = {
    "proxy_enabled",
    "proxy",
    "proxies",
    "proxy_rotation",
    "proxy_rotation_interval",
    "proxy_pool_enabled",
    "proxy_subscriptions",
    "proxy_pool_strategy",
    "proxy_pool_health_check",
    "proxy_pool_health_check_interval",
    "proxy_pool_max_failures",
    "proxy_pool_auto_update",
    "proxy_pool_update_interval",
    "proxy_pool_isolate_by_process",
    "proxy_workbench_enabled",
    "proxy_import_sources",
    "proxy_health_policy",
    "proxy_ui_preferences",
    "proxy_groups",
    "proxy_group_selections",
    "proxy_account_bindings",
    "accounts",
    "anonymous_route_policy",
    "account_route_policy",
}
_VIDEO_TASKS = {}


def _mask_proxy_url(value: str) -> str:
    text = str(value or "")
    if not text or "@" not in text:
        return text
    scheme, rest = text.split("://", 1) if "://" in text else ("", text)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}" if scheme else f"***@{host}"


def _safe_proxy_bound_record(value):
    if not isinstance(value, dict):
        return value
    safe = dict(value)
    for key in ("primary_proxy", "proxy"):
        if key in safe:
            safe[key] = _mask_proxy_url(safe.get(key) or "")
    return safe


def _is_masked_secret_value(value) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in MASKED_SECRET_VALUES or bool(re.fullmatch(r"\*+", normalized))
    if isinstance(value, list):
        return bool(value) and all(_is_masked_secret_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_is_masked_secret_value(item) for item in value.values())
    return False


def _usage(prompt: str, text: str) -> dict:
    p = len(prompt) // 4
    c = len(text or "") // 4
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def _openai_usage(prompt: str, text: str) -> dict:
    usage = _usage(prompt, text)
    return {
        **usage,
        "prompt_tokens_details": {"cached_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 0},
    }


def _elapsed_ms(start: float) -> float:
    return (time.time() - start) * 1000


def _last_proxy_url() -> str:
    try:
        from .gemini import get_last_proxy_url
        return _mask_proxy_url(get_last_proxy_url())
    except Exception:
        return _mask_proxy_url(CONFIG.get("proxy") or "")


def _web_feature_result(extra_fields: dict, response_images=None, response_media=None, response_artifacts=None) -> dict:
    feature = (extra_fields or {}).get("web_feature")
    if not feature:
        return {}
    info = dict(WEB_FEATURES.get(feature, {}))
    result = {
        "id": feature,
        "name": info.get("name", feature),
        "requested_model": (extra_fields or {}).get("web_model_name"),
        "declared_status": info.get("status", "experimental"),
    }
    image_count = len(response_images or [])
    video_count = len([item for item in (response_media or []) if item.get("kind") == "video"])
    audio_count = len([item for item in (response_media or []) if item.get("kind") == "audio"])
    if feature == "image_generation":
        result["runtime_status"] = "supported" if image_count else "limited"
        result["artifact_count"] = image_count
        if not image_count:
            result["note"] = "No real image artifact was returned by the upstream response."
    elif feature == "video_generation":
        result["runtime_status"] = "supported" if video_count else "limited"
        result["artifact_count"] = video_count
        if not video_count:
            result["note"] = "No real video artifact was returned by the upstream response."
    elif feature in {"music", "text_to_speech"}:
        result["runtime_status"] = "supported" if audio_count else "limited"
        result["artifact_count"] = audio_count
        if not audio_count:
            result["note"] = "No real audio artifact was returned by the upstream response."
    elif feature == "canvas":
        result["runtime_status"] = "supported" if response_artifacts else "limited"
        result["artifact_count"] = len(response_artifacts or [])
    else:
        result["runtime_status"] = "limited"
        result["note"] = info.get("note", "This Gemini Web tool flow still requires dedicated browser/RPC verification.")
    return result


def _response_assets(text: str, raw: str = None) -> tuple[list, list, list]:
    source = "\n".join(part for part in (text, raw) if part)
    if not source:
        return [], [], []
    return (
        extract_images_from_response(source),
        extract_media_from_response(source),
        extract_artifacts_from_response(text or raw or ""),
    )


def _materialize_files(response_media=None, response_artifacts=None, response_images=None) -> list:
    media = []
    seen = set()
    for item in response_media or []:
        if not isinstance(item, dict):
            continue
        key = (item.get("kind"), item.get("url"))
        if key in seen:
            continue
        seen.add(key)
        media.append(item)
    for item in response_images or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        key = ("image", url)
        if key in seen:
            continue
        seen.add(key)
        media.append({"kind": "image", "url": url, "alt": item.get("alt", ""), "type": item.get("type", "image")})
    return materialize_response_files(media, response_artifacts or [])


def _saved_file_url_map(response_files=None) -> dict:
    mapping = {}
    for item in response_files or []:
        if not isinstance(item, dict):
            continue
        materialized = item.get("materialized") or {}
        if materialized.get("status") != "saved":
            continue
        source = item.get("source_url")
        download = item.get("download_url") or materialized.get("download_url")
        if source and download:
            mapping[source] = download
    return mapping


def _is_placeholder_media_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url or "")
    return parsed.netloc.lower() == "googleusercontent.com" and parsed.path.lower().startswith((
        "/image_generation_content/",
        "/video_generation_content/",
        "/audio_generation_content/",
        "/card_content/",
    ))


def _rewrite_text_media_urls(text: str, response_files=None) -> str:
    if not text:
        return text or ""
    result = text
    for item in response_files or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source_url") or ""
        if not source:
            continue
        materialized = item.get("materialized") or {}
        if materialized.get("status") == "saved" and item.get("download_url"):
            result = result.replace(source, item["download_url"])
        elif _is_placeholder_media_url(source):
            result = result.replace(source, "")
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _rewrite_media_items_to_local(items, response_files=None) -> list:
    mapping = _saved_file_url_map(response_files)
    rewritten = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        clone = dict(item)
        source = clone.get("url", "")
        if source in mapping:
            clone["source_url"] = source
            clone["url"] = mapping[source]
            clone["download_url"] = mapping[source]
        elif _is_placeholder_media_url(source):
            continue
        rewritten.append(clone)
    return rewritten


def _saved_files_by_kind(response_files=None, kind: str = "") -> list:
    out = []
    for item in response_files or []:
        if not isinstance(item, dict):
            continue
        if kind and item.get("kind") != kind:
            continue
        materialized = item.get("materialized") or {}
        if materialized.get("status") == "saved" and item.get("download_url"):
            out.append(item)
    return out


def _store_video_task(model: str, prompt: str, result: dict, files: list) -> dict:
    task_id = f"video_{uuid.uuid4().hex[:16]}"
    videos = _saved_files_by_kind(files, "video")
    status = "completed" if videos else "failed"
    task = {
        "id": task_id,
        "object": "video",
        "created_at": int(time.time()),
        "status": status,
        "model": model,
        "prompt": prompt,
        "progress": 100,
        "data": [{"url": item.get("download_url", ""), "filename": item.get("filename", "")} for item in videos],
        "files": files,
        "web_feature": (result or {}).get("web_feature"),
        "message": "" if videos else (result or {}).get("text", ""),
    }
    _VIDEO_TASKS[task_id] = task
    return task


def _request_trace(
    *,
    model_name: str,
    model_id: int,
    think_mode: int,
    search_mode: bool = False,
    extra_fields=None,
    tools=None,
    tool_choice=None,
    tool_calls=None,
    tool_coercion: str = "",
    multimodal_status=None,
    response_artifacts=None,
    response_media=None,
    response_files=None,
    raw: str = "",
) -> dict:
    trace = {
        "model_name": model_name,
        "model_id": model_id,
        "think_mode": think_mode,
        "search_mode": bool(search_mode),
        "extra_fields": extra_fields or {},
        "tool_choice": tool_choice,
        "tools": tools or [],
        "tool_calls": tool_calls or [],
        "tool_coercion": tool_coercion,
        "multimodal_status": multimodal_status or {},
        "response_artifacts": response_artifacts or [],
        "response_media": response_media or [],
        "response_files": response_files or [],
        "visible_thinking_note": (
            "Hidden chain-of-thought is not available. This trace stores only request settings, "
            "tool calls, visible returned content, artifacts, and optional raw upstream text."
        ),
    }
    if CONFIG.get("log_upstream_raw") and raw:
        trace["upstream_raw"] = raw
    return trace


def _media_by_kind(response_media: list, kind: str) -> list:
    return [item for item in (response_media or []) if item.get("kind") == kind]


def _tool_function(tool: dict) -> dict:
    if not isinstance(tool, dict):
        return {}
    return tool.get("function") if isinstance(tool.get("function"), dict) else tool


def _tool_name(tool: dict) -> str:
    fn = _tool_function(tool)
    return str(fn.get("name") or tool.get("name") or "")


def _tool_properties(tool: dict) -> dict:
    params = _tool_function(tool).get("parameters") or {}
    return params.get("properties") if isinstance(params.get("properties"), dict) else {}


def _tool_arg_key(tool: dict, candidates: tuple[str, ...]) -> str:
    props = _tool_properties(tool)
    normalized = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in props}
    for candidate in candidates:
        key = normalized.get(re.sub(r"[^a-z0-9]", "", candidate.lower()))
        if key:
            return key
    return candidates[0]


def _latest_user_text(messages) -> str:
    parts = []
    for msg in messages or []:
        if not isinstance(msg, dict) or msg.get("role", "user") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") in ("text", "input_text"):
                    parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _extract_local_path(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"([A-Za-z]:\\[^\r\n\"'“”]+)", text)
    if not match:
        return ""
    return match.group(1).rstrip(" \t;；,，.。)）]】")


def _is_local_access_refusal(text: str) -> bool:
    lower = (text or "").lower()
    return any(phrase in lower for phrase in (
        "i cannot fulfill this request",
        "i can't fulfill this request",
        "i cannot access",
        "i can't access",
        "cannot access your",
        "cannot read local",
        "unable to access",
        "unable to inspect",
    ))


def _make_tool_call(name: str, arguments: dict, index: int = 0) -> dict:
    return {
        "id": f"call_{uuid.uuid4().hex[:8]}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        "index": index,
    }


def _explicit_tool_choice_name(tool_choice) -> str:
    if not isinstance(tool_choice, dict):
        return ""
    if isinstance(tool_choice.get("function"), dict):
        return str(tool_choice["function"].get("name") or "")
    return str(tool_choice.get("name") or "")


def _schema_default(prop: dict, *, user_text: str, key: str, tool_name: str):
    if not isinstance(prop, dict):
        prop = {}
    if prop.get("enum"):
        return prop["enum"][0]
    ptype = prop.get("type")
    if isinstance(ptype, list):
        ptype = next((item for item in ptype if item != "null"), ptype[0] if ptype else "string")
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
    path = _extract_local_path(user_text)
    if path and normalized_key in {"filepath", "filename", "path", "file", "dir", "directory"}:
        return path
    if normalized_key in {"query", "q", "prompt", "input", "text", "content", "command"}:
        return user_text
    if normalized_key in {"name", "model", "assistant", "identity"} or tool_name.lower() in {"identify_self", "identity"}:
        return "Gemini"
    if ptype == "integer":
        return 0
    if ptype == "number":
        return 0
    if ptype == "boolean":
        return False
    if ptype == "array":
        return []
    if ptype == "object":
        return {}
    return user_text or ""


def _infer_tool_arguments(tool: dict, messages) -> dict:
    fn = _tool_function(tool)
    tool_name = _tool_name(tool)
    params = fn.get("parameters") or {}
    properties = params.get("properties") if isinstance(params.get("properties"), dict) else {}
    required = params.get("required") if isinstance(params.get("required"), list) else []
    user_text = _latest_user_text(messages)
    arguments = {}

    if not properties:
        return arguments

    keys = required or list(properties.keys())[:1]
    for key in keys:
        arguments[key] = _schema_default(
            properties.get(key) or {},
            user_text=user_text,
            key=key,
            tool_name=tool_name,
        )
    return arguments


def _forced_tool_call_from_choice(tools, tool_choice, messages) -> list:
    name = _explicit_tool_choice_name(tool_choice)
    if not name:
        return []
    for tool in tools or []:
        if _tool_name(tool) == name:
            return [_make_tool_call(name, _infer_tool_arguments(tool, messages))]
    return []


def _forced_tool_call_from_refusal(text: str, tools, messages) -> list:
    if not tools or not _is_local_access_refusal(text):
        return []
    user_text = _latest_user_text(messages)
    path = _extract_local_path(user_text)
    tool_map = {_tool_name(tool): tool for tool in tools or [] if _tool_name(tool)}

    if path and "read" in tool_map:
        key = _tool_arg_key(tool_map["read"], ("filePath", "file_path", "path"))
        return [_make_tool_call("read", {key: path})]
    if path and "glob" in tool_map:
        path_key = _tool_arg_key(tool_map["glob"], ("path", "directory", "dir"))
        pattern_key = _tool_arg_key(tool_map["glob"], ("pattern", "glob"))
        return [_make_tool_call("glob", {pattern_key: "**/*", path_key: path})]
    if path and "grep" in tool_map:
        path_key = _tool_arg_key(tool_map["grep"], ("path", "directory", "dir"))
        pattern_key = _tool_arg_key(tool_map["grep"], ("pattern", "query"))
        return [_make_tool_call("grep", {pattern_key: ".", path_key: path})]
    if "todowrite" in tool_map:
        key = _tool_arg_key(tool_map["todowrite"], ("todos",))
        return [_make_tool_call("todowrite", {key: [{
            "content": "Inspect the requested project with available tools",
            "status": "in_progress",
            "priority": "high",
        }]})]
    return []


def _coerce_tool_calls(text: str, tools, tool_choice, messages) -> tuple[str, list, str]:
    tool_calls = []
    clean_text = text or ""
    if tools and tool_choice != "none":
        forced_choice = _forced_tool_call_from_choice(tools, tool_choice, messages)
        if forced_choice:
            return "", forced_choice, "forced_from_tool_choice"
        clean_text, tool_calls = parse_tool_calls(clean_text)
        forced = _forced_tool_call_from_refusal(clean_text, tools, messages)
        if forced:
            return "", forced, "forced_from_refusal"
    return clean_text, tool_calls, ""


def _openai_model_object(model_id: str, cfg: dict) -> dict:
    result = {
        "id": model_id,
        "object": "model",
        "created": 1700000000,
        "owned_by": "google",
        "description": cfg["desc"],
    }
    web_feature = cfg.get("extra", {}).get("web_feature")
    if web_feature:
        result["web_feature"] = web_feature
    return result


def _google_model_object(model_id: str, cfg: dict) -> dict:
    return {
        "name": f"models/{model_id}",
        "displayName": model_id,
        "description": cfg["desc"],
        "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
    }


def _expose_experimental_models() -> bool:
    return bool(CONFIG.get("expose_experimental_models") or CONFIG.get("expose_web_feature_models"))


def _model_id_from_openai_path(path: str) -> str:
    parsed = urllib.parse.urlparse(path)
    prefix = "/v1/models/"
    if not parsed.path.startswith(prefix):
        return ""
    return urllib.parse.unquote(parsed.path[len(prefix):]).strip("/")


def _model_id_from_google_path(path: str) -> str:
    parsed = urllib.parse.urlparse(path)
    prefix = "/v1beta/models/"
    if not parsed.path.startswith(prefix):
        return ""
    return urllib.parse.unquote(parsed.path[len(prefix):]).strip("/")


def _upload_files(images: list) -> list:
    """Upload files (images, video, audio, documents) and return list of file references.
    Returns None if no files."""
    if not images:
        return None
    file_refs = []
    for item in images:
        try:
            if isinstance(item, tuple) and len(item) >= 2:
                data, mime = item[0], item[1]
                filename = item[2] if len(item) >= 3 and item[2] else "upload"
                if isinstance(data, str):
                    # URL - fetch first
                    data = fetch_file_bytes(data)
                    mime = mime or "application/octet-stream"
                if data:
                    ref = upload_file(data, filename, mime or "application/octet-stream")
                    file_refs.append(ref)
        except Exception as e:
            log(f"File upload failed: {e}")
    return file_refs if file_refs else None


# Legacy alias
_upload_images = _upload_files


def _is_file_handoff_error(exc: Exception) -> bool:
    return "BardErrorInfo [1003]" in str(exc)


def _file_fallback_prompt(prompt: str, file_count: int, reason: str) -> str:
    noun = "attachment" if file_count == 1 else "attachments"
    return (
        "[System note]: The user included "
        f"{file_count} {noun}, but Gemini Web rejected the file handoff ({reason}). "
        "You did not receive the visual/audio/file content. Answer using the text "
        "conversation only, and do not pretend to inspect the attachment.\n\n"
        f"{prompt}"
    )


def _without_search_fields(extra_fields):
    """Remove only the fields that force Gemini Web search routing."""
    if not extra_fields:
        return extra_fields
    retry_extra = dict(extra_fields)
    retry_extra.pop("search", None)
    if retry_extra.get(30) == [5]:
        retry_extra.pop(30, None)
    return retry_extra or None


def _generate_with_search_control_fallback(
    prompt: str,
    model_id: int,
    think_mode: int,
    file_refs=None,
    extra_fields=None,
    status=None,
) -> dict:
    response = generate_with_metadata(prompt, model_id, think_mode, file_refs, extra_fields)
    if response.get("internal_control_only") and (extra_fields or {}).get("search"):
        if status is not None:
            status["search_fallback"] = {
                "reason": "websearch_not_needed",
                "fallback": "plain_generation",
            }
        retry_extra = _without_search_fields(extra_fields)
        retry = generate_with_metadata(prompt, model_id, think_mode, file_refs, retry_extra)
        retry["search_fallback"] = "websearch_not_needed"
        retry["search_fallback_extra_fields"] = retry_extra or {}
        return retry
    return response


def _requires_buffered_stream(extra_fields=None) -> bool:
    """Routes with control probes/artifacts need full-response handling before SSE."""
    fields = extra_fields or {}
    return bool(fields.get("search") or fields.get("web_feature"))


def _generate_with_file_fallback(prompt: str, model_id: int, think_mode: int, images=None, extra_fields=None) -> tuple[dict, dict]:
    """Generate with uploaded files, then retry text-only if Gemini rejects file handoff."""
    images = images or []
    status = {}
    if not images:
        return _generate_with_search_control_fallback(
            prompt, model_id, think_mode, None, extra_fields, status
        ), status

    file_refs = _upload_images(images)
    status = {
        "runtime_status": "attempted",
        "input_count": len(images),
        "uploaded_count": len(file_refs or []),
        "fallback": None,
    }
    if not file_refs:
        status.update({
            "runtime_status": "limited",
            "reason": "upload_failed",
            "fallback": "text_only",
        })
        fallback_prompt = _file_fallback_prompt(prompt, len(images), "upload_failed")
        return _generate_with_search_control_fallback(
            fallback_prompt, model_id, think_mode, None, extra_fields, status
        ), status

    try:
        response = _generate_with_search_control_fallback(
            prompt, model_id, think_mode, file_refs, extra_fields, status
        )
        status["runtime_status"] = "supported"
        return response, status
    except Exception as exc:
        if not _is_file_handoff_error(exc):
            raise
        status.update({
            "runtime_status": "limited",
            "reason": "BardErrorInfo [1003]",
            "fallback": "text_only",
        })
        fallback_prompt = _file_fallback_prompt(prompt, len(images), "BardErrorInfo [1003]")
        return _generate_with_search_control_fallback(
            fallback_prompt, model_id, think_mode, None, extra_fields, status
        ), status


class GeminiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log(fmt % args)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _start_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _write_sse_data(self, payload):
        self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()

    def _write_chat_completion_stream(
        self,
        *,
        cid: str,
        model_name: str,
        text: str,
        tool_calls=None,
        finish: str = "stop",
        usage=None,
        include_usage: bool = False,
        extra_chunk_fields=None,
    ):
        tool_calls = tool_calls or []
        extra_chunk_fields = extra_chunk_fields or {}
        now = int(time.time())
        self._start_sse()

        self._write_sse_data({
            "id": cid,
            "object": "chat.completion.chunk",
            "created": now,
            "model": model_name,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        })

        if tool_calls:
            for index, tc in enumerate(tool_calls):
                fn = tc.get("function") or {}
                arguments = fn.get("arguments") or "{}"
                first = {
                    "index": index,
                    "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {"name": fn.get("name", ""), "arguments": ""},
                }
                self._write_sse_data({
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": now,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {"tool_calls": [first]}, "finish_reason": None}],
                })
                if arguments:
                    self._write_sse_data({
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": now,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"tool_calls": [{"index": index, "function": {"arguments": arguments}}]},
                            "finish_reason": None,
                        }],
                    })
            self._write_sse_data({
                "id": cid,
                "object": "chat.completion.chunk",
                "created": now,
                "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            })
        else:
            if text:
                chunk = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": now,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                    **extra_chunk_fields,
                }
                self._write_sse_data(chunk)
            self._write_sse_data({
                "id": cid,
                "object": "chat.completion.chunk",
                "created": now,
                "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
            })

        if include_usage:
            self._write_sse_data({
                "id": cid,
                "object": "chat.completion.chunk",
                "created": now,
                "model": model_name,
                "choices": [],
                "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            })
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _write_claude_stream_text(self, message_id: str, model_name: str, text: str, usage_input_tokens: int):
        self._start_sse()
        self._write_sse_data({
            "type": "message_start",
            "message": {
                "id": message_id, "type": "message", "role": "assistant",
                "content": [], "model": model_name, "stop_reason": None,
                "stop_sequence": None, "usage": {"input_tokens": usage_input_tokens, "output_tokens": 0},
            },
        })
        self._write_sse_data({
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        if text:
            self._write_sse_data({
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": text},
            })
        self._write_sse_data({"type": "content_block_stop", "index": 0})
        self._write_sse_data({
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": len(text or "") // 4},
        })
        self._write_sse_data({"type": "message_stop"})

    def _send_bytes(self, body: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _absolute_url(self, path: str) -> str:
        if not path or path.startswith(("http://", "https://", "data:")):
            return path
        host = self.headers.get("Host") or f"127.0.0.1:{CONFIG.get('port', 8081)}"
        return f"http://{host}{path}"

    def _add_absolute_download_urls(self, items):
        for item in items or []:
            if isinstance(item, dict) and item.get("download_url"):
                item["download_url"] = self._absolute_url(item["download_url"])
            materialized = item.get("materialized") if isinstance(item, dict) else None
            if isinstance(materialized, dict) and materialized.get("download_url"):
                materialized["download_url"] = self._absolute_url(materialized["download_url"])
        return items

    def _send_artifact_file(self, parsed_path: str):
        name = parsed_path.rsplit("/", 1)[-1]
        path = resolve_artifact_path(name)
        if not path:
            self.send_json({"error": {"message": "artifact not found"}}, 404)
            return
        with open(path, "rb") as handle:
            body = handle.read()
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _assets_and_files(self, text: str, raw: str = None):
        response_images, response_media, response_artifacts = _response_assets(text, raw)
        response_files = self._add_absolute_download_urls(
            _materialize_files(response_media, response_artifacts, response_images)
        )
        response_images = _rewrite_media_items_to_local(response_images, response_files)
        response_media = _rewrite_media_items_to_local(response_media, response_files)
        return response_images, response_media, response_artifacts, response_files

    def _parse_body(self, body: bytes) -> dict:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None

    def _authorized(self):
        keys = CONFIG.get("api_keys") or []
        if not keys:
            return True
        auth = self.headers.get("Authorization", "")
        candidates = []
        if auth.lower().startswith("bearer "):
            candidates.extend(k.strip() for k in auth[7:].split(",") if k.strip())
        x_api_key = self.headers.get("x-api-key", "")
        if x_api_key:
            candidates.extend(k.strip() for k in x_api_key.split(",") if k.strip())
        return any(key in keys for key in candidates)

    def _dashboard_local_authorized(self):
        if not CONFIG.get("dashboard_local_bypass", True):
            return False
        parsed_path = urllib.parse.urlparse(self.path).path
        if not (parsed_path == "/admin" or parsed_path.startswith("/admin/") or parsed_path.startswith("/api/")):
            return False
        remote = self.client_address[0] if getattr(self, "client_address", None) else ""
        return remote in {"127.0.0.1", "::1", "localhost"} or remote.startswith("127.")

    @staticmethod
    def _path_requires_auth(path: str) -> bool:
        return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PROTECTED_PREFIXES)

    @staticmethod
    def _safe_config() -> dict:
        safe = {}
        for key, value in CONFIG.items():
            if key in SECRET_CONFIG_KEYS:
                if isinstance(value, list):
                    safe[key] = ["***"] * len(value) if value else []
                elif value:
                    safe[key] = "***"
                else:
                    safe[key] = value
            else:
                if key == "accounts" and isinstance(value, list):
                    safe[key] = [_safe_proxy_bound_record(item) for item in value]
                elif key == "proxy_account_bindings" and isinstance(value, list):
                    safe[key] = [_safe_proxy_bound_record(item) for item in value]
                else:
                    safe[key] = value
        return safe

    def _reject_if_unauthorized(self) -> bool:
        if self._path_requires_auth(self.path) and not (self._authorized() or self._dashboard_local_authorized()):
            self.send_json({"error": {"message": "invalid api key"}}, 401)
            return True
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        try:
            if self._reject_if_unauthorized():
                return
            parsed_path = urllib.parse.urlparse(self.path).path
            normalized_path = parsed_path.rstrip("/") or "/"
            if parsed_path.startswith("/v1/videos/") or parsed_path.startswith("/v1/video/generations/"):
                self._handle_video_task_get(parsed_path)
                return
            if parsed_path == "/admin" or parsed_path.startswith("/admin/"):
                self._handle_admin_get()
                return
            if parsed_path.startswith("/artifacts/"):
                self._send_artifact_file(parsed_path)
                return
            if parsed_path in ("/dashboard", "/dashboard.html"):
                self._send_dashboard()
                return
            if normalized_path == "/v1/models":
                # Check if cookie is available
                from .gemini import get_request_cookie
                cookie_str, _ = get_request_cookie()
                has_cookie = bool(cookie_str)
                # Get available models based on login status
                from .models import get_available_models
                available = get_available_models(has_cookie, expose_experimental=_expose_experimental_models())
                self.send_json({"object": "list", "data": [
                    _openai_model_object(n, c) for n, c in available.items()
                ]})
            elif parsed_path.startswith("/v1/models/"):
                from .gemini import get_request_cookie
                from .models import get_available_models, resolve_model
                cookie_str, _ = get_request_cookie()
                available = get_available_models(bool(cookie_str), expose_experimental=_expose_experimental_models())
                requested = _model_id_from_openai_path(self.path)
                resolved, _, _, err, _, _ = resolve_model(requested)
                if err or resolved not in available:
                    self.send_json({"error": {"message": f"model not found: {requested}"}}, 404)
                else:
                    self.send_json(_openai_model_object(resolved, available[resolved]))
            elif normalized_path == "/v1beta/models":
                from .gemini import get_request_cookie
                cookie_str, _ = get_request_cookie()
                has_cookie = bool(cookie_str)
                from .models import get_available_models
                available = get_available_models(has_cookie, expose_experimental=_expose_experimental_models())
                self.send_json({"models": [
                    _google_model_object(n, c) for n, c in available.items()
                ]})
            elif parsed_path.startswith("/v1beta/models/"):
                from .gemini import get_request_cookie
                from .models import get_available_models, resolve_model
                cookie_str, _ = get_request_cookie()
                available = get_available_models(bool(cookie_str), expose_experimental=_expose_experimental_models())
                requested = _model_id_from_google_path(self.path)
                resolved, _, _, err, _, _ = resolve_model(requested)
                if err or resolved not in available:
                    self.send_json({"error": {"message": f"model not found: {requested}"}}, 404)
                else:
                    self.send_json(_google_model_object(resolved, available[resolved]))
            elif parsed_path == "/api/config":
                self.send_json(self._safe_config())
            elif parsed_path == "/api/dashboard":
                from .stats import get_api_data
                self.send_json(get_api_data())
            elif parsed_path.startswith("/api/request/"):
                from .stats import get_request_detail
                request_id = urllib.parse.unquote(parsed_path.rsplit("/", 1)[-1])
                detail = get_request_detail(request_id)
                if detail:
                    self.send_json({"request": detail})
                else:
                    self.send_json({"error": "request not found"}, 404)
            elif parsed_path == "/api/proxy/status":
                from .admin import get_proxy_status
                self.send_json(get_proxy_status())
            elif parsed_path == "/api/capabilities":
                from .gemini import get_request_cookie
                from .capabilities import get_capability_report
                cookie_str, _ = get_request_cookie()
                self.send_json(get_capability_report(bool(cookie_str)))
            elif parsed_path == "/api/cookie/status":
                from . import cookie_manager
                status = cookie_manager.get_cookie_status()
                try:
                    from .playwright_cookie import get_browser_login_status, is_playwright_available
                    status["internal_browser"] = get_browser_login_status()
                    status["internal_browser"]["available"] = is_playwright_available()
                except Exception as e:
                    status["internal_browser"] = {"available": False, "error": str(e)}
                self.send_json(status)
            elif parsed_path == "/":
                from .gemini import get_request_cookie
                cookie_str, _ = get_request_cookie()
                has_cookie = bool(cookie_str)
                from .models import get_available_models
                available = get_available_models(has_cookie, expose_experimental=_expose_experimental_models())
                self.send_json({"status": "ok", "version": __version__,
                               "models": list(available.keys()),
                               "has_cookie": has_cookie})
            else:
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_DELETE(self):
        try:
            if self._reject_if_unauthorized():
                return
            if not (self.path == "/admin" or self.path.startswith("/admin/")):
                self.send_json({"error": "not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            self._handle_admin(body, method="DELETE")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            log(f"DELETE error: {e}")
            self.send_json({"error": {"message": str(e)}}, 500)

    def _send_dashboard(self):
        dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
        try:
            with open(dashboard_path, "r", encoding="utf-8") as f:
                body = f.read().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            fallback = f"<!doctype html><html><body><h1>Dashboard unavailable</h1><pre>{e}</pre></body></html>".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(fallback)))
            self.end_headers()
            self.wfile.write(fallback)

    def do_POST(self):
        try:
            if self._reject_if_unauthorized():
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            if self.path == "/v1/chat/completions":
                self._handle_chat(body)
            elif self.path in ("/v1/images/generations", "/v1/images/edits", "/v1/images/variations"):
                self._handle_image_generation(body)
            elif self.path in ("/v1/videos", "/v1/videos/generations", "/v1/video/generations"):
                self._handle_video_generation(body)
            elif self.path in ("/v1/audio/speech", "/v1/audio/generations"):
                self._handle_audio_speech(body)
            elif self.path == "/v1/responses":
                self._handle_responses(body)
            elif self.path == "/v1/messages":
                self._handle_claude_messages(body)
            elif self.path.startswith("/admin/"):
                self._handle_admin(body)
            elif self.path == "/api/config":
                self._handle_config_update(body)
            elif self.path == "/api/cookie/refresh":
                self._handle_cookie_refresh()
            elif self.path == "/api/cookie/push":
                self._handle_cookie_push(body)
            elif self.path == "/api/cookie/import":
                self._handle_cookie_import(body)
            elif self.path == "/api/cookie/browser-login":
                self._handle_cookie_browser_login()
            elif self.path == "/api/cookie/start":
                self._handle_cookie_start(body)
            elif self.path == "/api/cookie/stop":
                self._handle_cookie_stop()
            elif ":generateImages" in self.path:
                self._handle_google_media_generation(body, "image")
            elif ":generateVideos" in self.path:
                self._handle_google_media_generation(body, "video")
            elif ":generateAudio" in self.path or ":textToSpeech" in self.path:
                self._handle_google_media_generation(body, "audio")
            elif ":generateContent" in self.path:
                self._handle_google_generate(body, stream=False)
            elif ":streamGenerateContent" in self.path:
                self._handle_google_generate(body, stream=True)
            else:
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            log(f"POST error: {e}")
            try:
                self.send_json({"error": {"message": str(e)}}, 500)
            except:
                pass

    # ─── /admin/* ─────────────────────────────────────────────────────────────

    def _handle_admin_get(self):
        from .admin import handle_admin_request
        data, status = handle_admin_request(self.path, "GET", headers=self.headers)
        self.send_json(data, status)

    def _handle_admin(self, body: bytes, method: str = "POST"):
        req = self._parse_body(body) if body else {}
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        from .admin import handle_admin_request
        data, status = handle_admin_request(self.path, method, req, self.headers)
        self.send_json(data, status)

    # ─── /api/config POST ────────────────────────────────────────────────────

    def _handle_config_update(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        from .config import find_config
        cfg_path = find_config() or "config.json"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}
        applied = {}
        skipped_masked = []
        for k, v in req.items():
            if k == "xsrf_token":
                continue
            if k in SECRET_CONFIG_KEYS and _is_masked_secret_value(v):
                skipped_masked.append(k)
                continue
            current[k] = v
            applied[k] = v
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            CONFIG.update(applied)
            from .admin import init_admin
            init_admin()
            if PROXY_CONFIG_KEYS.intersection(applied):
                try:
                    from .gemini import reset_http_client
                    reset_http_client()
                except Exception:
                    pass
                try:
                    from .proxy_builtin import init_pool_from_config
                    init_pool_from_config(CONFIG)
                except Exception as e:
                    add_log(f"Proxy pool reinitialization failed: {e}", "error")
            add_log(f"Config updated via dashboard: {list(applied.keys())}")
            payload = {"success": True, "updated_keys": list(applied.keys())}
            if skipped_masked:
                payload["skipped_masked_keys"] = skipped_masked
            self.send_json(payload)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def _handle_cookie_refresh(self):
        from . import cookie_manager
        self.send_json(cookie_manager.manual_refresh())

    def _handle_cookie_push(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        cookies = req.get("cookies") or req.get("cookie") or ""
        sapisid = req.get("sapisid") or ""
        if not cookies:
            self.send_json({"success": False, "message": "missing cookies"}, 400)
            return
        from . import cookie_manager
        result = cookie_manager.accept_cookie_source(
            cookies,
            sapisid,
            source=req.get("source") or "edge-extension",
            target=CONFIG.get("cookie_file") or "cookie.txt",
        )
        self.send_json(result, 200 if result.get("success") else 500)

    def _handle_cookie_import(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        raw = req.get("raw") or req.get("content") or req.get("cookie") or req.get("cookies") or ""
        if not raw:
            self.send_json({"success": False, "message": "missing cookie content"}, 400)
            return
        from . import cookie_manager
        result = cookie_manager.accept_cookie_source(
            raw,
            source=req.get("source") or "manual-import",
            target=CONFIG.get("cookie_file") or "cookie.txt",
        )
        if result.get("success") and result.get("message") == "cookies saved":
            result["message"] = "cookies imported"
        self.send_json(result, 200 if result.get("success") else 400)

    def _handle_cookie_browser_login(self):
        from .playwright_cookie import start_browser_login_async
        result = start_browser_login_async(CONFIG.get("cookie_file") or "cookie.txt", CONFIG.get("port", 8081))
        self.send_json(result, 200 if result.get("success") else 500)

    def _handle_cookie_start(self, body: bytes):
        req = self._parse_body(body) or {}
        interval = req.get("interval_hours", 12)
        from . import cookie_manager
        cookie_manager.start_auto_refresh(interval)
        self.send_json({"success": True, "interval_hours": interval})

    def _handle_cookie_stop(self):
        from . import cookie_manager
        cookie_manager.stop_auto_refresh()
        self.send_json({"success": True})

    # ─── /v1/chat/completions ─────────────────────────────────────────────────

    def _generate_for_model(self, model: str, prompt: str, images=None):
        model_name, model_id, think_mode, err, extra_fields, search_mode = resolve_model(
            model or CONFIG["default_model"])
        if err:
            return {"error": err}
        if search_mode:
            extra_fields = extra_fields or {}
            extra_fields["search"] = True
        response, multimodal_status = _generate_with_file_fallback(prompt, model_id, think_mode, images, extra_fields)
        text = response.get("text", "")
        raw = response.get("raw", "")
        response_images, response_media, response_artifacts = _response_assets(text, raw)
        response_files = self._add_absolute_download_urls(
            _materialize_files(response_media, response_artifacts, response_images)
        )
        response_images = _rewrite_media_items_to_local(response_images, response_files)
        response_media = _rewrite_media_items_to_local(response_media, response_files)
        text = _rewrite_text_media_urls(text, response_files)
        result = {
            "model_name": model_name,
            "text": text,
            "extra_fields": extra_fields,
            "images": response_images,
            "media": response_media,
            "artifacts": response_artifacts,
            "files": response_files,
            "web_feature": _web_feature_result(extra_fields, response_images, response_media, response_artifacts),
        }
        if multimodal_status:
            result["multimodal_status"] = multimodal_status
        return result

    def _handle_image_generation(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            self.send_json({"error": {"message": "missing prompt"}}, 400)
            return
        model = req.get("model") or "nano-banana-2"
        response_format = req.get("response_format", "url")
        started = time.time()
        try:
            generated = self._generate_for_model(model, prompt)
        except Exception as e:
            log_request(model, len(prompt) // 4, 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        if generated.get("error"):
            self.send_json({"error": {"message": generated["error"]}}, 400)
            return

        data = []
        files = self._add_absolute_download_urls(generated.get("files") or [])
        for item in _saved_files_by_kind(files, "image"):
            url = item.get("download_url", "")
            if response_format == "b64_json":
                try:
                    with open(item["local_path"], "rb") as handle:
                        data.append({
                            "b64_json": base64.b64encode(handle.read()).decode("ascii"),
                            "revised_prompt": generated["text"],
                        })
                except Exception as exc:
                    log(f"Image b64 conversion failed: {exc}")
            elif url:
                data.append({"url": url, "revised_prompt": generated["text"]})
        result = {
            "created": int(time.time()),
            "data": data,
            "model": generated["model_name"],
            "object": "list",
            "web_feature": generated["web_feature"],
            "files": files,
            "message": generated["text"] if not data else None,
            "elapsed_ms": round(_elapsed_ms(started), 2),
        }
        self.send_json(result)
        log_request(
            generated["model_name"], len(prompt) // 4, len(generated["text"] or "") // 4,
            endpoint=self.path, request_body=req, response_body=result,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=f"img_{uuid.uuid4().hex[:16]}", protocol="openai.images",
            trace=_request_trace(
                model_name=generated["model_name"], model_id=-1, think_mode=-1,
                extra_fields=generated.get("extra_fields"), response_artifacts=generated.get("artifacts"),
                response_media=generated.get("media"), response_files=files,
            ),
        )

    def _handle_video_generation(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            self.send_json({"error": {"message": "missing prompt"}}, 400)
            return
        if req.get("image_url"):
            prompt = f"{prompt}\nReference image URL: {req['image_url']}"
        for key in ("video_style", "duration", "resolution"):
            if req.get(key):
                prompt = f"{prompt}\n{key}: {req[key]}"
        model = req.get("model") or "omni"
        started = time.time()
        try:
            generated = self._generate_for_model(model, prompt)
        except Exception as e:
            log_request(model, len(prompt) // 4, 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        if generated.get("error"):
            self.send_json({"error": {"message": generated["error"]}}, 400)
            return

        data = []
        files = self._add_absolute_download_urls(generated.get("files") or [])
        for item in _saved_files_by_kind(files, "video"):
            url = item.get("download_url", "")
            if url:
                data.append({"url": url, "video_url": url, "revised_prompt": generated["text"]})
        task = _store_video_task(generated["model_name"], prompt, generated, files)
        result = {
            "id": task["id"],
            "created": int(time.time()),
            "data": data,
            "model": generated["model_name"],
            "object": "list",
            "status": task["status"],
            "web_feature": generated["web_feature"],
            "files": files,
            "message": generated["text"] if not data else None,
            "elapsed_ms": round(_elapsed_ms(started), 2),
        }
        if self.path == "/v1/videos":
            result = {
                **task,
                "usage": {
                    "prompt_tokens": len(prompt) // 4,
                    "completion_tokens": len(generated["text"] or "") // 4,
                    "total_tokens": (len(prompt) + len(generated["text"] or "")) // 4,
                },
                "elapsed_ms": round(_elapsed_ms(started), 2),
            }
        self.send_json(result)
        log_request(
            generated["model_name"], len(prompt) // 4, len(generated["text"] or "") // 4,
            endpoint=self.path, request_body=req, response_body=result,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=f"vid_{uuid.uuid4().hex[:16]}", protocol="openai.videos",
            trace=_request_trace(
                model_name=generated["model_name"], model_id=-1, think_mode=-1,
                extra_fields=generated.get("extra_fields"), response_artifacts=generated.get("artifacts"),
                response_media=generated.get("media"), response_files=files,
            ),
        )

    def _handle_video_task_get(self, parsed_path: str):
        parts = [p for p in parsed_path.split("/") if p]
        if len(parts) < 3:
            self.send_json({"error": {"message": "missing video id"}}, 404)
            return
        if parts[-1] == "content":
            task_id = parts[-2]
            task = _VIDEO_TASKS.get(task_id)
            if not task:
                self.send_json({"error": {"message": "video task not found"}}, 404)
                return
            videos = _saved_files_by_kind(task.get("files") or [], "video")
            if not videos:
                self.send_json({"error": {"message": "video content not available"}}, 404)
                return
            path = videos[0].get("local_path")
            if not path or not os.path.exists(path):
                self.send_json({"error": {"message": "video file not found"}}, 404)
                return
            with open(path, "rb") as handle:
                self._send_bytes(handle.read(), (videos[0].get("materialized") or {}).get("mime_type") or "video/mp4")
            return
        task_id = parts[-1]
        task = _VIDEO_TASKS.get(task_id)
        if not task:
            self.send_json({"error": {"message": "video task not found"}}, 404)
            return
        self.send_json(task)

    def _handle_audio_speech(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        text_input = (req.get("input") or req.get("prompt") or "").strip()
        if not text_input:
            self.send_json({"error": {"message": "missing input"}}, 400)
            return
        model = req.get("model") or "gemini-2.5-flash-preview-tts"
        prompt = f"Read this aloud and return the audio: {text_input}"
        response_format = req.get("response_format") or req.get("format") or "mp3"
        started = time.time()
        try:
            generated = self._generate_for_model(model, prompt)
        except Exception as e:
            log_request(model, len(prompt) // 4, 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        if generated.get("error"):
            self.send_json({"error": {"message": generated["error"]}}, 400)
            return

        audio_items = _media_by_kind(generated["media"], "audio")
        files = self._add_absolute_download_urls(generated.get("files") or [])
        saved_audio = _saved_files_by_kind(files, "audio")
        if saved_audio and response_format != "json":
            try:
                first_audio = saved_audio[0]
                with open(first_audio["local_path"], "rb") as handle:
                    audio_bytes = handle.read()
                content_type = (first_audio.get("materialized") or {}).get("mime_type") or "audio/mpeg"
                self._send_bytes(audio_bytes, content_type)
                log_request(
                    generated["model_name"], len(prompt) // 4, len(generated["text"] or "") // 4,
                    endpoint=self.path, request_body=req,
                    response_body={"audio_bytes": len(audio_bytes), "content_type": content_type},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=f"aud_{uuid.uuid4().hex[:16]}", protocol="openai.audio",
                    trace=_request_trace(
                        model_name=generated["model_name"], model_id=-1, think_mode=-1,
                        extra_fields=generated.get("extra_fields"), response_artifacts=generated.get("artifacts"),
                        response_media=generated.get("media"), response_files=files,
                    ),
                )
                return
            except Exception as e:
                log(f"Audio fetch failed, returning JSON fallback: {e}")

        result = {
            "created": int(time.time()),
            "data": [{"url": item.get("download_url", "")} for item in saved_audio],
            "model": generated["model_name"],
            "object": "list",
            "web_feature": generated["web_feature"],
            "files": files,
            "message": generated["text"] if not saved_audio else None,
            "elapsed_ms": round(_elapsed_ms(started), 2),
        }
        self.send_json(result)
        log_request(
            generated["model_name"], len(prompt) // 4, len(generated["text"] or "") // 4,
            endpoint=self.path, request_body=req, response_body=result,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=f"aud_{uuid.uuid4().hex[:16]}", protocol="openai.audio",
            trace=_request_trace(
                model_name=generated["model_name"], model_id=-1, think_mode=-1,
                extra_fields=generated.get("extra_fields"), response_artifacts=generated.get("artifacts"),
                response_media=generated.get("media"), response_files=files,
            ),
        )

    def _media_prompt_from_google_body(self, req: dict) -> tuple[str, list]:
        prompt = req.get("prompt") or req.get("input") or req.get("text") or ""
        images = []
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip(), images
        if isinstance(req.get("instances"), list):
            parts = []
            for item in req["instances"]:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("prompt") or item.get("text") or item.get("input") or ""))
            prompt = "\n".join(part for part in parts if part).strip()
            if prompt:
                return prompt, images
        if req.get("contents"):
            return google_contents_to_prompt(req)
        return "", images

    @staticmethod
    def _media_model_for_google_endpoint(model: str, kind: str) -> str:
        model = (model or "").strip() or {
            "image": "nano-banana-2",
            "video": "omni",
            "audio": "gemini-2.5-flash-preview-tts",
        }.get(kind, CONFIG["default_model"])
        lower = model.lower()
        if kind == "image" and not any(token in lower for token in ("image", "imagen", "nano-banana", "banana")):
            return f"{model}-image"
        if kind == "video" and not any(token in lower for token in ("video", "veo", "omni")):
            return f"{model}-video"
        if kind == "audio" and not any(token in lower for token in ("audio", "tts", "speech", "lyria")):
            return f"{model}-tts"
        return model

    def _handle_google_media_generation(self, body: bytes, kind: str):
        started = time.time()
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        prompt, images = self._media_prompt_from_google_body(req)
        if not prompt:
            self.send_json({"error": {"message": "missing prompt"}}, 400)
            return
        requested_model = (_model_id_from_google_path(self.path) or req.get("model") or "").split(":", 1)[0]
        model = self._media_model_for_google_endpoint(requested_model, kind)
        try:
            generated = self._generate_for_model(model, prompt, images)
        except Exception as e:
            log_request(model, len(prompt) // 4, 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        if generated.get("error"):
            self.send_json({"error": {"message": generated["error"]}}, 400)
            return

        files = self._add_absolute_download_urls(generated.get("files") or [])
        saved = _saved_files_by_kind(files, kind)
        predictions = []
        for item in saved:
            materialized = item.get("materialized") or {}
            prediction = {
                "mimeType": materialized.get("mime_type") or "application/octet-stream",
                "uri": item.get("download_url", ""),
                "url": item.get("download_url", ""),
                "filename": item.get("filename", ""),
            }
            if req.get("includeBase64") or req.get("response_format") in {"b64_json", "base64"}:
                try:
                    with open(item["local_path"], "rb") as handle:
                        prediction["bytesBase64Encoded"] = base64.b64encode(handle.read()).decode("ascii")
                except Exception as exc:
                    prediction["base64Error"] = str(exc)[:180]
            predictions.append(prediction)

        response_obj = {
            "model": generated["model_name"],
            "predictions": predictions,
            "generatedMedia": predictions,
            "files": files,
            "webFeature": generated["web_feature"],
            "text": generated["text"],
            "usageMetadata": {
                "promptTokenCount": len(prompt) // 4,
                "candidatesTokenCount": len(generated["text"] or "") // 4,
                "totalTokenCount": (len(prompt) + len(generated["text"] or "")) // 4,
            },
            "elapsedMs": round(_elapsed_ms(started), 2),
        }
        parts = []
        if generated["text"]:
            parts.append({"text": generated["text"]})
        for prediction in predictions:
            parts.append({"fileData": {"mimeType": prediction["mimeType"], "fileUri": prediction["uri"]}})
        response_obj["candidates"] = [{
            "content": {"role": "model", "parts": parts or [{"text": ""}]},
            "finishReason": "STOP",
            "index": 0,
        }]
        self.send_json(response_obj)
        log_request(
            generated["model_name"], len(prompt) // 4, len(generated["text"] or "") // 4,
            endpoint=self.path, request_body=req, response_body=response_obj,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=f"gmedia_{uuid.uuid4().hex[:16]}",
            protocol=f"google.{kind}", stream=False,
            trace=_request_trace(
                model_name=generated["model_name"], model_id=-1, think_mode=-1,
                extra_fields=generated.get("extra_fields"), response_artifacts=generated.get("artifacts"),
                response_media=generated.get("media"), response_files=files,
            ),
        )

    def _handle_chat(self, body: bytes):
        started = time.time()
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields, search_mode = resolve_model(
            req.get("model", CONFIG["default_model"]))
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

        # Enable search if search_mode is True
        if search_mode:
            extra_fields = extra_fields or {}
            extra_fields["search"] = True

        tools = req.get("tools")
        tool_choice = req.get("tool_choice", "auto")
        prompt, images = messages_to_prompt(req.get("messages", []), tools, tool_choice)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty prompt"}}, 400)
            return

        stream = req.get("stream", False)
        cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        forced_choice_calls = _forced_tool_call_from_choice(tools, tool_choice, req.get("messages", [])) if tools else []
        if forced_choice_calls:
            msg = {"role": "assistant", "content": None, "tool_calls": forced_choice_calls}
            usage = _openai_usage(prompt, "")
            if stream:
                self._write_chat_completion_stream(
                    cid=cid,
                    model_name=model_name,
                    text="",
                    tool_calls=forced_choice_calls,
                    finish="tool_calls",
                    usage=usage,
                    include_usage=bool((req.get("stream_options") or {}).get("include_usage")),
                )
                response_body = {"stream": True, "message": msg}
            else:
                response_body = {
                    "id": cid, "object": "chat.completion", "created": int(time.time()),
                    "model": model_name,
                    "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls"}],
                    "usage": usage,
                }
                self.send_json(response_body)
            log_request(
                model_name, len(prompt) // 4, 0,
                endpoint=self.path, request_body=req, response_body=response_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=cid, protocol="openai.chat", stream=stream,
                trace=_request_trace(
                    model_name=model_name, model_id=model_id, think_mode=think_mode,
                    search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                    tool_choice=tool_choice, tool_calls=forced_choice_calls,
                    tool_coercion="forced_from_tool_choice",
                ))
            return

        if stream and (images or _requires_buffered_stream(extra_fields)) and (not tools or tool_choice == "none"):
            try:
                response, multimodal_status = _generate_with_file_fallback(
                    prompt, model_id, think_mode, images, extra_fields)
                text = response.get("text", "")
                raw = response.get("raw", "")
                response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
                text = _rewrite_text_media_urls(text, response_files)
                self._start_sse()
                msg = {"content": text}
                chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                         "model": model_name, "choices": [{"index": 0, "delta": msg, "finish_reason": None}]}
                if multimodal_status:
                    chunk["multimodal_status"] = multimodal_status
                if response_images:
                    chunk["images"] = response_images
                if response_media:
                    chunk["media"] = response_media
                if response_artifacts:
                    chunk["artifacts"] = response_artifacts
                if response_files:
                    chunk["files"] = response_files
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                       "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                self.wfile.write(f"data: {json.dumps(end)}\n\n".encode())
                if (req.get("stream_options") or {}).get("include_usage"):
                    usage_chunk = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [],
                        "usage": _openai_usage(prompt, text or ""),
                    }
                    self.wfile.write(f"data: {json.dumps(usage_chunk)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                log_request(
                    model_name, len(prompt) // 4, len(text or "") // 4,
                    endpoint=self.path, request_body=req,
                    response_body={
                        "stream": True,
                        "text": text,
                        "multimodal_status": multimodal_status,
                        "images": response_images,
                        "media": response_media,
                        "artifacts": response_artifacts,
                        "files": response_files,
                    },
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=cid, protocol="openai.chat", stream=True,
                    trace=_request_trace(
                        model_name=model_name, model_id=model_id, think_mode=think_mode,
                        search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                        tool_choice=tool_choice, multimodal_status=multimodal_status,
                        response_artifacts=response_artifacts, response_media=response_media,
                        response_files=response_files, raw=raw,
                    ))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=cid, protocol="openai.chat", stream=True)
                self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return

        if stream and (not tools or tool_choice == "none"):
            try:
                self._start_sse()
                full_text = ""
                for delta in generate_stream(prompt, model_id, think_mode, _upload_images(images), extra_fields):
                    full_text += delta or ""
                    chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                             "model": model_name, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                response_images, response_media, response_artifacts, response_files = self._assets_and_files(full_text)
                full_text = _rewrite_text_media_urls(full_text, response_files)
                if response_images or response_media or response_artifacts or response_files:
                    asset_chunk = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                    }
                    if response_images:
                        asset_chunk["images"] = response_images
                    if response_media:
                        asset_chunk["media"] = response_media
                    if response_artifacts:
                        asset_chunk["artifacts"] = response_artifacts
                    if response_files:
                        asset_chunk["files"] = response_files
                    self.wfile.write(f"data: {json.dumps(asset_chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                       "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                self.wfile.write(f"data: {json.dumps(end)}\n\n".encode())
                if (req.get("stream_options") or {}).get("include_usage"):
                    usage_chunk = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [],
                        "usage": _openai_usage(prompt, full_text),
                    }
                    self.wfile.write(f"data: {json.dumps(usage_chunk)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                log_request(
                    model_name, len(prompt) // 4, len(full_text) // 4,
                    endpoint=self.path, request_body=req,
                    response_body={
                        "stream": True,
                        "text": full_text,
                        "images": response_images,
                        "media": response_media,
                        "artifacts": response_artifacts,
                        "files": response_files,
                    },
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=cid, protocol="openai.chat", stream=True,
                    trace=_request_trace(
                        model_name=model_name, model_id=model_id, think_mode=think_mode,
                        search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                        tool_choice=tool_choice, response_artifacts=response_artifacts,
                        response_media=response_media, response_files=response_files,
                    ))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=cid, protocol="openai.chat", stream=True)
                raise
            return

        try:
            response, multimodal_status = _generate_with_file_fallback(
                prompt, model_id, think_mode, images, extra_fields)
            text = response.get("text", "")
            raw = response.get("raw", "")
        except Exception as e:
            error_body = {"error": {"message": f"upstream error: {e}"}}
            log_request(
                model_name, len(prompt) // 4, 0, "error", str(e),
                endpoint=self.path, request_body=req, response_body=error_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=cid, protocol="openai.chat", stream=stream)
            self.send_json(error_body, 502)
            return

        tool_calls = None
        tool_coercion = ""
        if tools:
            text, tool_calls, tool_coercion = _coerce_tool_calls(
                text, tools, tool_choice, req.get("messages", []))
        msg = {"role": "assistant", "content": text or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        finish = "tool_calls" if tool_calls else "stop"

        if tool_calls:
            response_images, response_media, response_artifacts, response_files = [], [], [], []
        else:
            response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
            text = _rewrite_text_media_urls(text, response_files)
            msg["content"] = text or None

        result = None
        if stream:
            extra_chunk_fields = {}
            if multimodal_status:
                extra_chunk_fields["multimodal_status"] = multimodal_status
            if response_files:
                extra_chunk_fields["files"] = response_files
            self._write_chat_completion_stream(
                cid=cid,
                model_name=model_name,
                text=text or "",
                tool_calls=tool_calls,
                finish=finish,
                usage=_openai_usage(prompt, text or ""),
                include_usage=bool((req.get("stream_options") or {}).get("include_usage")),
                extra_chunk_fields=extra_chunk_fields,
            )
        else:
            result = {
                "id": cid, "object": "chat.completion", "created": int(time.time()),
                "model": model_name,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": {"prompt_tokens": len(prompt)//4, "completion_tokens": len(text or "")//4,
                          "total_tokens": (len(prompt)+len(text or ""))//4},
            }
            # Include images if found
            if response_images:
                result["images"] = response_images
            if response_media:
                result["media"] = response_media
            # Include artifacts if found (Canvas-like functionality)
            if response_artifacts:
                result["artifacts"] = response_artifacts
            if response_files:
                result["files"] = response_files
            web_feature = _web_feature_result(extra_fields, response_images, response_media, response_artifacts)
            if web_feature:
                result["web_feature"] = web_feature
            if multimodal_status:
                result["multimodal_status"] = multimodal_status
            self.send_json(result)
        log_request(
            model_name, len(prompt) // 4, len(text or "") // 4,
            endpoint=self.path, request_body=req,
            response_body=(result if result is not None else {"stream": True, "message": msg}),
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=cid, protocol="openai.chat", stream=stream,
            trace=_request_trace(
                model_name=model_name, model_id=model_id, think_mode=think_mode,
                search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                tool_choice=tool_choice, tool_calls=tool_calls,
                tool_coercion=tool_coercion,
                multimodal_status=multimodal_status, response_artifacts=response_artifacts,
                response_media=response_media, response_files=response_files, raw=raw,
            ))

    # ─── /v1/messages (Claude Messages API) ─────────────────────────────────

    def _handle_claude_messages(self, body: bytes):
        started = time.time()
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return

        openai_req = parse_claude_request(req)
        model_name, model_id, think_mode, err, extra_fields, search_mode = resolve_model(
            openai_req.get("model", CONFIG["default_model"]))
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return
        if search_mode:
            extra_fields = extra_fields or {}
            extra_fields["search"] = True

        tools = openai_req.get("tools")
        tool_choice = openai_req.get("tool_choice", "auto")
        prompt, images = messages_to_prompt(openai_req.get("messages", []), tools, tool_choice)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty prompt"}}, 400)
            return

        def write_claude_event(event):
            etype = event.get("type", "message_delta")
            self.wfile.write(f"event: {etype}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        forced_choice_calls = _forced_tool_call_from_choice(
            tools, tool_choice, openai_req.get("messages", [])) if tools else []
        if forced_choice_calls:
            openai_resp = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": None, "tool_calls": forced_choice_calls},
                    "finish_reason": "tool_calls",
                }],
                "usage": _usage(prompt, ""),
            }
            claude_resp = convert_openai_response_to_claude(openai_resp)
            if openai_req.get("stream"):
                message_id = claude_resp["id"]
                self._start_sse()
                write_claude_event({
                    "type": "message_start",
                    "message": {
                        "id": message_id, "type": "message", "role": "assistant",
                        "content": [], "model": model_name, "stop_reason": None,
                        "stop_sequence": None, "usage": {"input_tokens": len(prompt) // 4, "output_tokens": 0},
                    },
                })
                for index, call in enumerate(forced_choice_calls):
                    fn = call.get("function") or {}
                    args = fn.get("arguments") or "{}"
                    write_claude_event({
                        "type": "content_block_start", "index": index,
                        "content_block": {
                            "type": "tool_use",
                            "id": call.get("id"),
                            "name": fn.get("name", ""),
                            "input": {},
                        },
                    })
                    write_claude_event({
                        "type": "content_block_delta", "index": index,
                        "delta": {"type": "input_json_delta", "partial_json": args},
                    })
                    write_claude_event({"type": "content_block_stop", "index": index})
                write_claude_event({
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {"output_tokens": 0},
                })
                write_claude_event({"type": "message_stop"})
                response_body = {"stream": True, "message": claude_resp}
            else:
                self.send_json(claude_resp)
                response_body = claude_resp
            log_request(
                model_name, len(prompt) // 4, 0,
                endpoint=self.path, request_body=req, response_body=response_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=claude_resp.get("id", openai_resp["id"]),
                protocol="claude.messages", stream=bool(openai_req.get("stream")),
                trace=_request_trace(
                    model_name=model_name, model_id=model_id, think_mode=think_mode,
                    search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                    tool_choice=tool_choice, tool_calls=forced_choice_calls,
                    tool_coercion="forced_from_tool_choice",
                ))
            return

        if openai_req.get("stream") and (images or _requires_buffered_stream(extra_fields)) and (not tools or tool_choice == "none"):
            message_id = f"msg_{uuid.uuid4().hex[:24]}"
            try:
                response, multimodal_status = _generate_with_file_fallback(
                    prompt, model_id, think_mode, images, extra_fields)
                text = response.get("text", "")
                raw = response.get("raw", "")
                response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
                text = _rewrite_text_media_urls(text, response_files)
                self._write_claude_stream_text(message_id, model_name, text, len(prompt) // 4)
                log_request(
                    model_name, len(prompt) // 4, len(text or "") // 4,
                    endpoint=self.path, request_body=req,
                    response_body={"stream": True, "text": text, "multimodal_status": multimodal_status,
                                   "images": response_images, "media": response_media,
                                   "artifacts": response_artifacts, "files": response_files},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=message_id, protocol="claude.messages", stream=True,
                    trace=_request_trace(
                        model_name=model_name, model_id=model_id, think_mode=think_mode,
                        search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                        tool_choice=tool_choice, multimodal_status=multimodal_status,
                        response_artifacts=response_artifacts, response_media=response_media,
                        response_files=response_files, raw=raw,
                    ))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=message_id, protocol="claude.messages", stream=True)
                raise
            return

        if openai_req.get("stream") and (not tools or tool_choice == "none"):
            message_id = f"msg_{uuid.uuid4().hex[:24]}"
            try:
                self._start_sse()
                write_claude_event({
                    "type": "message_start",
                    "message": {
                        "id": message_id, "type": "message", "role": "assistant",
                        "content": [], "model": model_name, "stop_reason": None,
                        "stop_sequence": None, "usage": {"input_tokens": len(prompt) // 4, "output_tokens": 0},
                    },
                })
                write_claude_event({
                    "type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""},
                })
                full_text = ""
                for delta in generate_stream(prompt, model_id, think_mode, _upload_images(images), extra_fields):
                    if not delta:
                        continue
                    full_text += delta
                    write_claude_event({
                        "type": "content_block_delta", "index": 0,
                        "delta": {"type": "text_delta", "text": delta},
                    })
                write_claude_event({"type": "content_block_stop", "index": 0})
                write_claude_event({
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": len(full_text) // 4},
                })
                write_claude_event({"type": "message_stop"})
                log_request(
                    model_name, len(prompt) // 4, len(full_text) // 4,
                    endpoint=self.path, request_body=req,
                    response_body={"stream": True, "text": full_text},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=message_id, protocol="claude.messages", stream=True)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=message_id, protocol="claude.messages", stream=True)
                raise
            return

        try:
            response, multimodal_status = _generate_with_file_fallback(
                prompt, model_id, think_mode, images, extra_fields)
            text = response.get("text", "")
            raw = response.get("raw", "")
        except Exception as e:
            error_body = {"error": {"message": f"upstream error: {e}"}}
            log_request(
                model_name, len(prompt) // 4, 0, "error", str(e),
                endpoint=self.path, request_body=req, response_body=error_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=f"msg_{uuid.uuid4().hex[:24]}",
                protocol="claude.messages", stream=bool(openai_req.get("stream")))
            self.send_json(error_body, 502)
            return

        tool_calls = None
        tool_coercion = ""
        if tools:
            text, tool_calls, tool_coercion = _coerce_tool_calls(
                text, tools, tool_choice, openai_req.get("messages", []))
        msg = {"role": "assistant", "content": text or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        finish = "tool_calls" if tool_calls else "stop"
        if tool_calls:
            response_images, response_media, response_artifacts, response_files = [], [], [], []
        else:
            response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
            text = _rewrite_text_media_urls(text, response_files)
            msg["content"] = text or None
        openai_resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": _usage(prompt, text or ""),
        }
        claude_resp = convert_openai_response_to_claude(openai_resp)
        if response_files:
            claude_resp["files"] = response_files
        if response_artifacts:
            claude_resp["artifacts"] = response_artifacts
        if multimodal_status:
            claude_resp["multimodal_status"] = multimodal_status
        self.send_json(claude_resp)
        log_request(
            model_name, len(prompt) // 4, len(text or "") // 4,
            endpoint=self.path, request_body=req, response_body=claude_resp,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=claude_resp.get("id", openai_resp["id"]),
            protocol="claude.messages", stream=False,
            trace=_request_trace(
                model_name=model_name, model_id=model_id, think_mode=think_mode,
                search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                tool_choice=tool_choice, tool_calls=tool_calls,
                tool_coercion=tool_coercion,
                multimodal_status=multimodal_status, response_artifacts=response_artifacts,
                response_media=response_media, response_files=response_files, raw=raw,
            ))

    # ─── /v1/responses (Codex CLI) ───────────────────────────────────────────

    def _handle_responses(self, body: bytes):
        started = time.time()
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields, search_mode = resolve_model(
            req.get("model", CONFIG["default_model"]))
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

        # Enable search if search_mode is True
        if search_mode:
            extra_fields = extra_fields or {}
            extra_fields["search"] = True

        input_items = req.get("input", [])
        tools = req.get("tools")
        messages = []
        if req.get("instructions"):
            messages.append({"role": "system", "content": req["instructions"]})
        if isinstance(input_items, str):
            messages.append({"role": "user", "content": input_items})
        elif isinstance(input_items, list):
            for item in input_items:
                if isinstance(item, str):
                    messages.append({"role": "user", "content": item})
                elif isinstance(item, dict):
                    if item.get("type") in ("input_text", "input_image", "input_file"):
                        messages.append({"role": "user", "content": [item]})
                        continue
                    if item.get("type") == "function_call_output":
                        messages.append({"role": "tool", "tool_call_id": item.get("call_id", ""),
                                         "name": item.get("name", ""), "content": item.get("output", "")})
                    elif item.get("role") == "assistant" or (item.get("type") == "message" and item.get("role") == "assistant"):
                        cp = item.get("content", [])
                        text_acc, tc_list = "", []
                        if isinstance(cp, list):
                            for c in cp:
                                if isinstance(c, dict):
                                    if c.get("type") == "output_text": text_acc += c.get("text", "")
                                    elif c.get("type") == "function_call": tc_list.append(c)
                        elif isinstance(cp, str):
                            text_acc = cp
                        m = {"role": "assistant", "content": text_acc or None}
                        if tc_list:
                            m["tool_calls"] = [{"id": tc.get("call_id", f"call_{i}"), "type": "function",
                                                "function": {"name": tc.get("name",""), "arguments": tc.get("arguments","{}")}}
                                               for i, tc in enumerate(tc_list)]
                        messages.append(m)
                    else:
                        role = item.get("role", "user")
                        content = item.get("content", "")
                        if isinstance(content, list):
                            normalized_content = []
                            for c in content:
                                if not isinstance(c, dict):
                                    continue
                                ctype = c.get("type")
                                if ctype in ("text", "input_text"):
                                    normalized_content.append({"type": "text", "text": c.get("text", "")})
                                elif ctype in (
                                    "image_url", "input_image", "input_file", "file",
                                    "file_url", "video_url", "audio_url", "input_audio",
                                ):
                                    normalized_content.append(c)
                            content = normalized_content
                        messages.append({"role": role, "content": content})

        if tools:
            tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters", {})}}
                     if t.get("type") == "function" and "function" not in t else t for t in tools]

        tool_choice = req.get("tool_choice", "auto")
        prompt, images = messages_to_prompt(messages, tools, tool_choice)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty input"}}, 400)
            return

        forced_choice_calls = _forced_tool_call_from_choice(tools, tool_choice, messages) if tools else []
        if forced_choice_calls:
            rid = f"resp_{uuid.uuid4().hex[:16]}"
            output = [
                {"type": "function_call", "id": tc["id"], "call_id": tc["id"],
                 "name": tc["function"]["name"], "arguments": tc["function"]["arguments"], "status": "completed"}
                for tc in forced_choice_calls
            ]
            usage = {
                "input_tokens": len(prompt) // 4,
                "output_tokens": 0,
                "total_tokens": len(prompt) // 4,
            }
            if req.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                ev = {"type": "response.created", "response": {"id": rid, "object": "response", "status": "in_progress", "model": model_name, "output": []}}
                self.wfile.write(f"event: response.created\ndata: {json.dumps(ev)}\n\n".encode())
                for item in output:
                    ev = {"type": "response.output_item.added", "item": item, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.added\ndata: {json.dumps(ev)}\n\n".encode())
                    ev = {"type": "response.function_call_arguments.done", "item_id": item["id"], "call_id": item["call_id"], "name": item["name"], "arguments": item["arguments"]}
                    self.wfile.write(f"event: response.function_call_arguments.done\ndata: {json.dumps(ev)}\n\n".encode())
                    ev = {"type": "response.output_item.done", "item": item, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.done\ndata: {json.dumps(ev)}\n\n".encode())
                resp_obj = {
                    "id": rid, "object": "response", "status": "completed", "model": model_name,
                    "output": output, "output_text": "", "usage": usage,
                }
                self.wfile.write(f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': resp_obj})}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                response_body = {"stream": True, "response": resp_obj}
            else:
                response_body = {
                    "id": rid, "object": "response", "created_at": int(time.time()), "status": "completed",
                    "model": model_name, "output": output, "output_text": "", "usage": usage,
                }
                self.send_json(response_body)
            log_request(
                model_name, len(prompt) // 4, 0,
                endpoint=self.path, request_body=req, response_body=response_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=rid, protocol="openai.responses", stream=bool(req.get("stream")),
                trace=_request_trace(
                    model_name=model_name, model_id=model_id, think_mode=think_mode,
                    search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                    tool_choice=tool_choice, tool_calls=forced_choice_calls,
                    tool_coercion="forced_from_tool_choice",
                ))
            return

        try:
            response, multimodal_status = _generate_with_file_fallback(
                prompt, model_id, think_mode, images, extra_fields)
            text = response.get("text", "")
            raw = response.get("raw", "")
        except Exception as e:
            error_body = {"error": {"message": f"upstream error: {e}"}}
            log_request(
                model_name, len(prompt) // 4, 0, "error", str(e),
                endpoint=self.path, request_body=req, response_body=error_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=f"resp_{uuid.uuid4().hex[:16]}",
                protocol="openai.responses", stream=bool(req.get("stream")))
            self.send_json(error_body, 502)
            return

        tool_calls = None
        tool_coercion = ""
        if tools:
            text, tool_calls, tool_coercion = _coerce_tool_calls(text, tools, tool_choice, messages)

        rid = f"resp_{uuid.uuid4().hex[:16]}"
        mid = f"msg_{uuid.uuid4().hex[:12]}"
        output = []
        if tool_calls:
            for tc in tool_calls:
                output.append({"type": "function_call", "id": tc["id"], "call_id": tc["id"],
                               "name": tc["function"]["name"], "arguments": tc["function"]["arguments"], "status": "completed"})
        if text or not tool_calls:
            output.append({"type": "message", "id": mid, "role": "assistant", "status": "completed",
                           "content": [{"type": "output_text", "text": text or "", "annotations": []}]})

        if tool_calls:
            response_images, response_media, response_artifacts, response_files = [], [], [], []
        else:
            response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
            text = _rewrite_text_media_urls(text, response_files)
            for item in output:
                if item.get("type") == "message":
                    for content in item.get("content") or []:
                        if content.get("type") == "output_text":
                            content["text"] = text or ""
        response_extra = {}
        if response_images:
            response_extra["images"] = response_images
        if response_media:
            response_extra["media"] = response_media
        if response_artifacts:
            response_extra["artifacts"] = response_artifacts
        if response_files:
            response_extra["files"] = response_files
        if multimodal_status:
            response_extra["multimodal_status"] = multimodal_status

        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            ev = {"type": "response.created", "response": {"id": rid, "object": "response", "status": "in_progress", "model": model_name, "output": []}}
            self.wfile.write(f"event: response.created\ndata: {json.dumps(ev)}\n\n".encode())
            for item in output:
                if item["type"] == "function_call":
                    ev = {"type": "response.output_item.added", "item": item, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.added\ndata: {json.dumps(ev)}\n\n".encode())
                    ev = {"type": "response.function_call_arguments.done", "item_id": item["id"], "call_id": item["call_id"], "name": item["name"], "arguments": item["arguments"]}
                    self.wfile.write(f"event: response.function_call_arguments.done\ndata: {json.dumps(ev)}\n\n".encode())
                    ev = {"type": "response.output_item.done", "item": item, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.done\ndata: {json.dumps(ev)}\n\n".encode())
                elif item["type"] == "message":
                    ev = {"type": "response.output_item.added", "item": {**item, "content": []}, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.added\ndata: {json.dumps(ev)}\n\n".encode())
                    for ci, cp in enumerate(item["content"]):
                        ev = {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0, "content_index": ci, "part": {"type": "output_text", "text": "", "annotations": []}}
                        self.wfile.write(f"event: response.content_part.added\ndata: {json.dumps(ev)}\n\n".encode())
                        chunk_chars = max(1, int(CONFIG.get("stream_chunk_chars") or 1))
                        for offset in range(0, len(cp["text"]), chunk_chars):
                            delta = cp["text"][offset:offset + chunk_chars]
                            ev = {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0, "content_index": ci, "delta": delta}
                            self.wfile.write(f"event: response.output_text.delta\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                        ev = {"type": "response.output_text.done", "item_id": item["id"], "content_index": ci, "text": cp["text"]}
                        self.wfile.write(f"event: response.output_text.done\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                        ev = {"type": "response.content_part.done", "item_id": item["id"], "output_index": 0, "content_index": ci, "part": cp}
                        self.wfile.write(f"event: response.content_part.done\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                    ev = {"type": "response.output_item.done", "item": item, "output_index": 0}
                    self.wfile.write(f"event: response.output_item.done\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
            resp_obj = {
                "id": rid, "object": "response", "status": "completed", "model": model_name, "output": output,
                "output_text": text or "",
                "usage": {"input_tokens": len(prompt)//4, "output_tokens": len(text or "")//4, "total_tokens": (len(prompt)+len(text or ""))//4},
                **response_extra,
            }
            self.wfile.write(f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': resp_obj})}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            response_body = {"stream": True, "response": resp_obj}
        else:
            response_body = {
                "id": rid, "object": "response", "created_at": int(time.time()), "status": "completed",
                "model": model_name, "output": output,
                "output_text": text or "",
                "usage": {"input_tokens": len(prompt)//4, "output_tokens": len(text or "")//4, "total_tokens": (len(prompt)+len(text or ""))//4},
                **response_extra,
            }
            self.send_json(response_body)
        log_request(
            model_name, len(prompt) // 4, len(text or "") // 4,
            endpoint=self.path, request_body=req, response_body=response_body,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=rid, protocol="openai.responses", stream=bool(req.get("stream")),
            trace=_request_trace(
                model_name=model_name, model_id=model_id, think_mode=think_mode,
                search_mode=search_mode, extra_fields=extra_fields, tools=tools,
                tool_choice=tool_choice, tool_calls=tool_calls,
                tool_coercion=tool_coercion,
                multimodal_status=multimodal_status, response_artifacts=response_artifacts,
                response_media=response_media, response_files=response_files, raw=raw,
            ))

    # ─── /v1beta/models (Google Gemini CLI) ──────────────────────────────────

    def _handle_google_generate(self, body: bytes, stream: bool):
        started = time.time()
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        m = re.match(r'/v1beta/models/([^:?]+)', self.path)
        model_name = m.group(1) if m else CONFIG["default_model"]
        model_name, model_id, think_mode, err, extra_fields, search_mode = resolve_model(model_name)
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

        # Enable search if search_mode is True
        if search_mode:
            extra_fields = extra_fields or {}
            extra_fields["search"] = True

        tool_config = req.get("toolConfig", {})
        fc_mode = tool_config.get("functionCallingConfig", {}).get("mode", "AUTO")
        has_tools = bool(req.get("tools")) and fc_mode != "NONE"
        prompt, images = google_contents_to_prompt(req)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty content"}}, 400)
            return

        log(f"Google API: model={model_name} stream={stream} tools={has_tools} prompt_len={len(prompt)}")

        if stream and (images or _requires_buffered_stream(extra_fields)) and not has_tools:
            try:
                response, multimodal_status = _generate_with_file_fallback(
                    prompt, model_id, think_mode, images, extra_fields)
                text = response.get("text", "")
                raw = response.get("raw", "")
                response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
                text = _rewrite_text_media_urls(text, response_files)
                self._start_sse()
                chunk_obj = {
                    "candidates": [{"content": {"parts": [{"text": text}], "role": "model"}, "index": 0}],
                    "modelVersion": model_name,
                }
                if multimodal_status:
                    chunk_obj["multimodalStatus"] = multimodal_status
                if response_images:
                    chunk_obj["images"] = response_images
                if response_media:
                    chunk_obj["media"] = response_media
                if response_artifacts:
                    chunk_obj["artifacts"] = response_artifacts
                if response_files:
                    chunk_obj["files"] = response_files
                self.wfile.write(f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n".encode())
                final_chunk = {
                    "candidates": [{"finishReason": "STOP", "index": 0}],
                    "usageMetadata": {
                        "promptTokenCount": len(prompt) // 4,
                        "candidatesTokenCount": len(text or "") // 4,
                        "totalTokenCount": (len(prompt) + len(text or "")) // 4,
                    },
                    "modelVersion": model_name,
                }
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                log_request(
                    model_name, len(prompt) // 4, len(text or "") // 4,
                    endpoint=self.path, request_body=req,
                    response_body={"stream": True, "final": final_chunk, "text": text,
                                   "multimodal_status": multimodal_status,
                                   "images": response_images,
                                   "media": response_media,
                                   "artifacts": response_artifacts,
                                   "files": response_files},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=f"google_{uuid.uuid4().hex[:16]}",
                    protocol="google.generate", stream=True,
                    trace=_request_trace(
                        model_name=model_name, model_id=model_id, think_mode=think_mode,
                        search_mode=search_mode, extra_fields=extra_fields,
                        multimodal_status=multimodal_status, response_artifacts=response_artifacts,
                        response_media=response_media, response_files=response_files, raw=raw,
                    ))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=f"google_{uuid.uuid4().hex[:16]}",
                    protocol="google.generate", stream=True)
                self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return

        if stream and not has_tools:
            try:
                self._start_sse()
                full_text = ""
                for delta in generate_stream(prompt, model_id, think_mode, None, extra_fields):
                    if not delta:
                        continue
                    full_text += delta
                    chunk_obj = {
                        "candidates": [{"content": {"parts": [{"text": delta}], "role": "model"}, "index": 0}],
                        "modelVersion": model_name,
                    }
                    self.wfile.write(f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                response_images, response_media, response_artifacts, response_files = self._assets_and_files(full_text)
                full_text = _rewrite_text_media_urls(full_text, response_files)
                final_chunk = {
                    "candidates": [{"finishReason": "STOP", "index": 0}],
                    "usageMetadata": {
                        "promptTokenCount": len(prompt) // 4,
                        "candidatesTokenCount": len(full_text) // 4,
                        "totalTokenCount": (len(prompt) + len(full_text)) // 4,
                    },
                    "modelVersion": model_name,
                }
                if response_images:
                    final_chunk["images"] = response_images
                if response_media:
                    final_chunk["media"] = response_media
                if response_artifacts:
                    final_chunk["artifacts"] = response_artifacts
                if response_files:
                    final_chunk["files"] = response_files
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                log_request(
                    model_name, len(prompt) // 4, len(full_text) // 4,
                    endpoint=self.path, request_body=req,
                    response_body={
                        "stream": True,
                        "final": final_chunk,
                        "text": full_text,
                        "images": response_images,
                        "media": response_media,
                        "artifacts": response_artifacts,
                        "files": response_files,
                    },
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=f"google_{uuid.uuid4().hex[:16]}",
                    protocol="google.generate", stream=True,
                    trace=_request_trace(
                        model_name=model_name, model_id=model_id, think_mode=think_mode,
                        search_mode=search_mode, extra_fields=extra_fields,
                        response_artifacts=response_artifacts, response_media=response_media,
                        response_files=response_files,
                    ))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                log_request(
                    model_name, len(prompt) // 4, 0, "error", str(e),
                    endpoint=self.path, request_body=req,
                    response_body={"error": {"message": str(e)}},
                    duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                    request_id=f"google_{uuid.uuid4().hex[:16]}",
                    protocol="google.generate", stream=True)
                raise
            return

        try:
            response, multimodal_status = _generate_with_file_fallback(
                prompt, model_id, think_mode, images, extra_fields)
            text = response.get("text", "")
            raw = response.get("raw", "")
        except Exception as e:
            error_body = {"error": {"message": f"upstream error: {e}"}}
            log_request(
                model_name, len(prompt) // 4, 0, "error", str(e),
                endpoint=self.path, request_body=req, response_body=error_body,
                duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
                request_id=f"google_{uuid.uuid4().hex[:16]}",
                protocol="google.generate", stream=stream)
            self.send_json(error_body, 502)
            return

        if not text:
            log("Warning: empty response from Gemini")

        response_images, response_media, response_artifacts, response_files = self._assets_and_files(text, raw)
        text = _rewrite_text_media_urls(text, response_files)

        response_parts = []
        if has_tools and text:
            clean_text, function_calls = parse_google_function_calls(text)
            if function_calls:
                if clean_text:
                    response_parts.append({"text": clean_text})
                for fc in function_calls:
                    response_parts.append({"functionCall": {"name": fc["name"], "args": fc["args"]}})
            else:
                response_parts.append({"text": text})
        else:
            response_parts.append({"text": text or "I apologize, but I was unable to generate a response. Please try again."})

        candidate = {
            "content": {"parts": response_parts, "role": "model"},
            "finishReason": "STOP",
            "index": 0,
        }
        usage = {
            "promptTokenCount": len(prompt) // 4,
            "candidatesTokenCount": len(text or "") // 4,
            "totalTokenCount": (len(prompt) + len(text or "")) // 4,
        }
        response_obj = {
            "candidates": [candidate],
            "usageMetadata": usage,
            "modelVersion": model_name,
        }
        if response_images:
            response_obj["images"] = response_images
        if response_media:
            response_obj["media"] = response_media
        if response_artifacts:
            response_obj["artifacts"] = response_artifacts
        if response_files:
            response_obj["files"] = response_files
        if multimodal_status:
            response_obj["multimodalStatus"] = multimodal_status

        if stream:
            self._start_sse()
            self.wfile.write(f"data: {json.dumps(response_obj, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_json(response_obj)
        log_request(
            model_name, len(prompt) // 4, len(text or "") // 4,
            endpoint=self.path, request_body=req, response_body=response_obj,
            duration_ms=_elapsed_ms(started), proxy=_last_proxy_url(),
            request_id=f"google_{uuid.uuid4().hex[:16]}",
            protocol="google.generate", stream=stream,
            trace=_request_trace(
                model_name=model_name, model_id=model_id, think_mode=think_mode,
                search_mode=search_mode, extra_fields=extra_fields, tools=req.get("tools"),
                tool_choice=fc_mode, multimodal_status=multimodal_status,
                response_artifacts=response_artifacts, response_media=response_media,
                response_files=response_files, raw=raw,
            ))


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
