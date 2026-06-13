"""End-to-end HTTP checks for request detail capture without real upstream calls."""

import json
import socket
import threading
import urllib.request
import base64

from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _json_request(url, payload=None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _raw_post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode("utf-8")


def test_chat_completion_records_real_request_and_response_body(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        assert "hello detail" in prompt
        return {"text": "captured response body", "raw": ""}

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        payload = {
            "model": "gemini-3.5-flash",
            "messages": [{"role": "user", "content": "hello detail"}],
        }
        response = _json_request(f"http://127.0.0.1:{port}/v1/chat/completions", payload)
        detail = _json_request(f"http://127.0.0.1:{port}/api/request/{response['id']}")["request"]

        assert response["choices"][0]["message"]["content"] == "captured response body"
        assert detail["endpoint"] == "/v1/chat/completions"
        assert detail["protocol"] == "openai.chat"
        assert detail["request_body"]["messages"][0]["content"] == "hello detail"
        assert detail["response_body"]["choices"][0]["message"]["content"] == "captured response body"
        assert detail["total_tokens"] > 0
        assert detail["duration_ms"] is not None
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)


def test_streaming_chat_records_complete_stream_text(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"

    def fake_stream(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        assert "hello stream detail" in prompt
        yield "captured "
        yield "stream body"

    monkeypatch.setattr("gemini_web2api.server.generate_stream", fake_stream)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        payload = {
            "model": "gemini-3.5-flash",
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": "hello stream detail"}],
        }
        sse = _raw_post(f"http://127.0.0.1:{port}/v1/chat/completions", payload)
        first_chunk = next(
            json.loads(line.removeprefix("data: "))
            for line in sse.splitlines()
            if line.startswith("data: {")
        )
        detail = _json_request(f"http://127.0.0.1:{port}/api/request/{first_chunk['id']}")["request"]

        assert "captured " in sse
        assert "stream body" in sse
        assert detail["stream"] is True
        assert detail["request_body"]["messages"][0]["content"] == "hello stream detail"
        assert detail["response_body"]["stream"] is True
        assert detail["response_body"]["text"] == "captured stream body"
        assert detail["total_tokens"] > 0
        assert '"usage"' in sse
        assert '"choices": []' in sse
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)


def test_opencode_style_stream_refusal_is_converted_to_tool_call(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        assert "Tool Use" in prompt
        return {"text": "I cannot fulfill this request.", "raw": ""}

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        payload = {
            "model": "gemini-3.5-flash-thinking",
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": '"D:\\workspaces\\2api\\HelloGML" 审查这个仓库'}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read a file or directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"filePath": {"type": "string"}},
                        "required": ["filePath"],
                    },
                },
            }],
            "tool_choice": "auto",
        }
        sse = _raw_post(f"http://127.0.0.1:{port}/v1/chat/completions", payload)
        first_chunk = next(
            json.loads(line.removeprefix("data: "))
            for line in sse.splitlines()
            if line.startswith("data: {")
        )
        detail = _json_request(f"http://127.0.0.1:{port}/api/request/{first_chunk['id']}")["request"]

        events = [
            json.loads(line.removeprefix("data: "))
            for line in sse.splitlines()
            if line.startswith("data: {")
        ]
        argument_chunks = []
        tool_name = ""
        for event in events:
            for choice in event.get("choices") or []:
                for call in choice.get("delta", {}).get("tool_calls") or []:
                    fn = call.get("function") or {}
                    tool_name = fn.get("name") or tool_name
                    argument_chunks.append(fn.get("arguments") or "")
        arguments = json.loads("".join(argument_chunks) or "{}")
        assert tool_name == "read"
        assert arguments["filePath"] == "D:\\workspaces\\2api\\HelloGML"
        assert '"finish_reason": "tool_calls"' in sse
        assert '"usage"' in sse
        assert "I cannot fulfill this request" not in sse
        assert detail["trace"]["tool_coercion"] == "forced_from_refusal"
        assert detail["trace"]["tool_calls"][0]["function"]["name"] == "read"
        assert detail["trace"]["response_files"] == []
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)


def test_streaming_chat_forced_tool_choice_does_not_call_upstream(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"

    def fail_generate(*args, **kwargs):
        raise AssertionError("forced tool_choice should not call Gemini upstream")

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fail_generate)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        payload = {
            "model": "gemini-3.5-flash",
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": "Who are you? Use the function."}],
            "tools": [{
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
            }],
            "tool_choice": {"type": "function", "function": {"name": "identify_self"}},
        }
        sse = _raw_post(f"http://127.0.0.1:{port}/v1/chat/completions", payload)
        chunks = [
            json.loads(line.removeprefix("data: "))
            for line in sse.splitlines()
            if line.startswith("data: {")
        ]
        args = []
        for chunk in chunks:
            for choice in chunk.get("choices") or []:
                for call in choice.get("delta", {}).get("tool_calls") or []:
                    args.append((call.get("function") or {}).get("arguments") or "")
        assert '"finish_reason": "tool_calls"' in sse
        assert '"name": "identify_self"' in sse
        assert json.loads("".join(args)) == {"name": "Gemini"}
        assert '"usage"' in sse
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)


def test_responses_api_preserves_input_image_and_file(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"
    captured = {}

    def fake_upload(images):
        captured["images"] = images
        return ["/contrib_service/ref-image", "/contrib_service/ref-file"]

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        captured["prompt"] = prompt
        captured["file_refs"] = file_refs
        return {"text": "responses saw attachments", "raw": ""}

    monkeypatch.setattr("gemini_web2api.server._upload_images", fake_upload)
    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        png = base64.b64encode(b"png").decode()
        txt = base64.b64encode(b"hello").decode()
        payload = {
            "model": "gemini-3.5-flash",
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "please inspect"},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{png}", "filename": "a.png"},
                    {"type": "input_file", "filename": "note.txt", "file_data": f"data:text/plain;base64,{txt}"},
                ],
            }],
        }
        response = _json_request(f"http://127.0.0.1:{port}/v1/responses", payload)

        assert response["output_text"] == "responses saw attachments"
        assert response["output"][0]["content"][0]["text"] == "responses saw attachments"
        assert captured["images"][0] == (b"png", "image/png", "a.png")
        assert captured["images"][1] == (b"hello", "text/plain", "note.txt")
        assert captured["file_refs"] == ["/contrib_service/ref-image", "/contrib_service/ref-file"]
        assert "please inspect" in captured["prompt"]
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)


def test_responses_stream_emits_delta_events(monkeypatch):
    port = _free_port()
    old_config = {key: CONFIG.get(key) for key in ("api_keys", "default_model", "host", "stream_chunk_chars")}
    CONFIG["api_keys"] = []
    CONFIG["default_model"] = "gemini-3.5-flash"
    CONFIG["host"] = "127.0.0.1"
    CONFIG["stream_chunk_chars"] = 3

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        return {"text": "abcdef", "raw": ""}

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    server = ThreadedServer(("127.0.0.1", port), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        payload = {"model": "gemini-3.5-flash", "stream": True, "input": "hello"}
        sse = _raw_post(f"http://127.0.0.1:{port}/v1/responses", payload)

        assert "event: response.output_text.delta" in sse
        assert '"delta": "abc"' in sse
        assert '"delta": "def"' in sse
        assert "event: response.completed" in sse
        assert "data: [DONE]" in sse
    finally:
        server.shutdown()
        server.server_close()
        CONFIG.update(old_config)
