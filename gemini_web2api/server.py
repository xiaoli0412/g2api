"""HTTP server: OpenAI-compatible API endpoints."""
import json
import time
import uuid
import re
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from .config import CONFIG
from .models import MODELS, resolve_model
from .gemini import generate, generate_stream, log, HAS_HTTPX
from .tools import messages_to_prompt, parse_tool_calls, google_contents_to_prompt, parse_google_function_calls
from .multimodal import upload_file, fetch_file_bytes
from .tokenizer import count_tokens, count_messages_tokens
from . import stats
from . import cookie_manager
from . import __version__

_DASHBOARD_HTML_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")


def _usage(prompt: str, text: str) -> dict:
    p = count_tokens(prompt)
    c = count_tokens(text or "")
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def _upload_files(images: list) -> list:
    if not images:
        return None
    file_refs = []
    for item in images:
        try:
            if isinstance(item, tuple) and len(item) == 2:
                data, mime = item
                if isinstance(data, str):
                    data = fetch_file_bytes(data)
                    mime = mime or "image/png"
                if data:
                    ref = upload_file(data, "upload", mime or "image/png")
                    file_refs.append(ref)
        except Exception as e:
            log(f"File upload failed: {e}")
    return file_refs if file_refs else None


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
        key = auth[7:] if auth.startswith("Bearer ") else self.headers.get("x-api-key", "")
        return key in keys

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _serve_dashboard(self):
        try:
            with open(_DASHBOARD_HTML_PATH, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_json({"error": "dashboard.html not found"}, 404)

    def do_GET(self):
        try:
            if self.path.startswith("/v1/") and not self._authorized():
                self.send_json({"error": {"message": "invalid api key"}}, 401)
                return
            if self.path == "/dashboard":
                self._serve_dashboard()
            elif self.path == "/api/dashboard":
                self.send_json(stats.get_api_data())
            elif self.path == "/api/cookie/status":
                self.send_json(cookie_manager.get_cookie_status())
            elif self.path == "/v1/models":
                self.send_json({"object": "list", "data": [
                    {"id": n, "object": "model", "created": 1700000000,
                     "owned_by": "google", "description": c["desc"]}
                    for n, c in MODELS.items()
                ]})
            elif self.path.startswith("/v1beta/models"):
                self.send_json({"models": [
                    {"name": f"models/{n}", "displayName": n, "description": c["desc"],
                     "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]}
                    for n, c in MODELS.items()
                ]})
            elif self.path == "/":
                self.send_json({"status": "ok", "version": __version__, "models": list(MODELS.keys()),
                                "dashboard": "/dashboard"})
            else:
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            if self.path.startswith("/v1/") and not self._authorized():
                self.send_json({"error": {"message": "invalid api key"}}, 401)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            if self.path == "/v1/chat/completions":
                self._handle_chat(body)
            elif self.path == "/v1/responses":
                self._handle_responses(body)
            elif self.path == "/api/cookie/refresh":
                self.send_json(cookie_manager.manual_refresh())
            elif self.path == "/api/cookie/start":
                req = self._parse_body(body) or {}
                interval = req.get("interval_hours", 12)
                cookie_manager.start_auto_refresh(interval)
                self.send_json({"success": True, "message": f"Auto-refresh started (every {interval}h)"})
            elif self.path == "/api/cookie/stop":
                cookie_manager.stop_auto_refresh()
                self.send_json({"success": True, "message": "Auto-refresh stopped"})
            elif self.path == "/api/cookie/push":
                req = self._parse_body(body) or {}
                cookies = req.get("cookies", "")
                sapisid = req.get("sapisid", "")
                if cookies:
                    cookie_manager.write_cookie_file(cookies, sapisid)
                    from . import gemini
                    gemini._cookie_cache.update({"str": "", "sapisid": None, "mtime": 0})
                    self.send_json({"success": True, "message": "Cookies received and applied"})
                    log("Cookies pushed from browser extension")
                else:
                    self.send_json({"success": False, "error": "No cookies provided"}, 400)
            elif self.path == "/api/cookie/browser-login":
                from . import playwright_cookie
                if not playwright_cookie.is_playwright_available():
                    self.send_json({"success": False, "error": "playwright not installed"}, 400)
                else:
                    def do_login():
                        result = playwright_cookie.launch_browser_login(port=CONFIG["port"])
                        if result.get("success"):
                            cookie_manager.write_cookie_file(result["cookies"], result.get("sapisid", ""))
                            from . import gemini
                            gemini._cookie_cache.update({"str": "", "sapisid": None, "mtime": 0})
                        stats.add_log(f"Browser login: {'success' if result.get('success') else result.get('error', 'failed')}", "info")
                    threading.Thread(target=do_login, daemon=True).start()
                    self.send_json({"success": True, "message": "Browser window opening, please log in manually..."})
            elif ":generateContent" in self.path:
                self._handle_google_generate(body, stream=False)
            elif ":streamGenerateContent" in self.path:
                self._handle_google_generate(body, stream=True)
            else:
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            log(f"POST error: {e}")
            try:
                self.send_json({"error": {"message": str(e)}}, 500)
            except:
                pass

    # ─── /v1/chat/completions ─────────────────────────────────────────────────

    def _handle_chat(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields = resolve_model(
            req.get("model", CONFIG["default_model"]))
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

        tools = req.get("tools")
        tool_choice = req.get("tool_choice", "auto")
        prompt, images = messages_to_prompt(req.get("messages", []), tools, tool_choice)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty prompt"}}, 400)
            return

        stream = req.get("stream", False)
        cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        prompt_tokens = count_tokens(prompt)
        file_refs = _upload_files(images)
        stream_mode = CONFIG.get("stream_mode", "auto")

        if stream and (not tools or tool_choice == "none"):
            try:
                self._start_sse()
                full_text = ""
                use_fake = stream_mode == "fake"

                if not use_fake:
                    for delta in generate_stream(prompt, model_id, think_mode, file_refs, extra_fields):
                        full_text += delta
                        chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                                 "model": model_name, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                        self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                        self.wfile.flush()
                    if not full_text:
                        pass
                    elif stream_mode == "auto" and not HAS_HTTPX:
                        use_fake = True

                if use_fake and full_text:
                    delay = CONFIG.get("fake_stream_delay_ms", 5) / 1000.0
                    chunk_size = 8
                    for i in range(0, len(full_text), chunk_size):
                        delta_text = full_text[i:i + chunk_size]
                        chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                                 "model": model_name, "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}]}
                        self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                        self.wfile.flush()
                        if delay > 0:
                            time.sleep(delay)

                end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                       "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                self.wfile.write(f"data: {json.dumps(end)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                completion_tokens = count_tokens(full_text)
                stats.log_request(model_name, prompt_tokens, completion_tokens, "ok")
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        try:
            text = generate(prompt, model_id, think_mode, file_refs, extra_fields)
        except Exception as e:
            stats.log_request(model_name, prompt_tokens, 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return

        tool_calls = None
        if tools and text and tool_choice != "none":
            text, tool_calls = parse_tool_calls(text)
        msg = {"role": "assistant", "content": text or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        finish = "tool_calls" if tool_calls else "stop"
        completion_tokens = count_tokens(text or "")

        if stream:
            self._start_sse()
            if stream_mode != "true" and text:
                delay = CONFIG.get("fake_stream_delay_ms", 5) / 1000.0
                chunk_size = 8
                for i in range(0, len(text), chunk_size):
                    delta_text = text[i:i + chunk_size]
                    chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                             "model": model_name, "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    if delay > 0:
                        time.sleep(delay)
            else:
                chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                         "model": model_name, "choices": [{"index": 0, "delta": msg, "finish_reason": finish}]}
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
            end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                   "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(end)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            self.send_json({
                "id": cid, "object": "chat.completion", "created": int(time.time()),
                "model": model_name,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                          "total_tokens": prompt_tokens + completion_tokens},
            })
        stats.log_request(model_name, prompt_tokens, completion_tokens, "ok")

    # ─── /v1/responses (Codex CLI) ───────────────────────────────────────────

    def _handle_responses(self, body: bytes):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields = resolve_model(
            req.get("model", CONFIG["default_model"]))
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

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
                            content = " ".join(c.get("text", "") for c in content if c.get("type") in ("text", "input_text"))
                        messages.append({"role": role, "content": content})

        if tools:
            tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters", {})}}
                     if t.get("type") == "function" and "function" not in t else t for t in tools]

        tool_choice = req.get("tool_choice", "auto")
        prompt, images = messages_to_prompt(messages, tools, tool_choice)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty input"}}, 400)
            return

        try:
            text = generate(prompt, model_id, think_mode, _upload_files(images), extra_fields)
        except Exception as e:
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return

        tool_calls = None
        if tools and text and tool_choice != "none":
            text, tool_calls = parse_tool_calls(text)

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
                    ev = {"type": "response.function_call_arguments.done", "item_id": item["id"], "call_id": item["call_id"], "name": item["name"], "arguments": item["arguments"]}
                    self.wfile.write(f"event: response.function_call_arguments.done\ndata: {json.dumps(ev)}\n\n".encode())
                elif item["type"] == "message":
                    for ci, cp in enumerate(item["content"]):
                        ev = {"type": "response.output_text.done", "item_id": item["id"], "content_index": ci, "text": cp["text"]}
                        self.wfile.write(f"event: response.output_text.done\ndata: {json.dumps(ev)}\n\n".encode())
            resp_obj = {"id": rid, "object": "response", "status": "completed", "model": model_name, "output": output,
                        "usage": {"input_tokens": count_tokens(prompt), "output_tokens": count_tokens(text or ""), "total_tokens": count_tokens(prompt) + count_tokens(text or "")}}
            self.wfile.write(f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': resp_obj})}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_json({"id": rid, "object": "response", "created_at": int(time.time()), "status": "completed",
                            "model": model_name, "output": output,
                            "usage": {"input_tokens": count_tokens(prompt), "output_tokens": count_tokens(text or ""), "total_tokens": count_tokens(prompt) + count_tokens(text or "")}})

    # ─── /v1beta/models (Google Gemini CLI) ──────────────────────────────────

    def _handle_google_generate(self, body: bytes, stream: bool):
        req = self._parse_body(body)
        if req is None:
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        m = re.match(r'/v1beta/models/([^:?]+)', self.path)
        model_name = m.group(1) if m else CONFIG["default_model"]
        model_name, model_id, think_mode, err, extra_fields = resolve_model(model_name)
        if err:
            self.send_json({"error": {"message": err}}, 400)
            return

        tool_config = req.get("toolConfig", {})
        fc_mode = tool_config.get("functionCallingConfig", {}).get("mode", "AUTO")
        has_tools = bool(req.get("tools")) and fc_mode != "NONE"
        prompt, images = google_contents_to_prompt(req)
        if not prompt.strip():
            self.send_json({"error": {"message": "empty content"}}, 400)
            return

        file_refs = _upload_files(images)
        log(f"Google API: model={model_name} stream={stream} tools={has_tools} prompt_len={len(prompt)}")

        if stream and not has_tools:
            try:
                self._start_sse()
                full_text = ""
                for delta in generate_stream(prompt, model_id, think_mode, file_refs, extra_fields):
                    if not delta:
                        continue
                    full_text += delta
                    chunk_obj = {
                        "candidates": [{"content": {"parts": [{"text": delta}], "role": "model"}, "index": 0}],
                        "modelVersion": model_name,
                    }
                    self.wfile.write(f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                final_chunk = {
                    "candidates": [{"finishReason": "STOP", "index": 0}],
                    "usageMetadata": {
                        "promptTokenCount": count_tokens(prompt),
                        "candidatesTokenCount": count_tokens(full_text),
                        "totalTokenCount": count_tokens(prompt) + count_tokens(full_text),
                    },
                    "modelVersion": model_name,
                }
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                stats.log_request(model_name, count_tokens(prompt), count_tokens(full_text), "ok")
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        try:
            text = generate(prompt, model_id, think_mode, file_refs, extra_fields)
        except Exception as e:
            stats.log_request(model_name, count_tokens(prompt), 0, "error", str(e))
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return

        if not text:
            log("Warning: empty response from Gemini")

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
            "promptTokenCount": count_tokens(prompt),
            "candidatesTokenCount": count_tokens(text or ""),
            "totalTokenCount": count_tokens(prompt) + count_tokens(text or ""),
        }
        response_obj = {
            "candidates": [candidate],
            "usageMetadata": usage,
            "modelVersion": model_name,
        }

        if stream:
            self._start_sse()
            self.wfile.write(f"data: {json.dumps(response_obj, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_json(response_obj)
        stats.log_request(model_name, count_tokens(prompt), count_tokens(text or ""), "ok")


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
