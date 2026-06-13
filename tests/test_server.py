"""Tests for gemini_web2api.server HTTP handler structure (no real network)."""
import json
import threading
import urllib.request

from gemini_web2api.server import (
    GeminiHandler,
    ThreadedServer,
    _generate_with_file_fallback,
    _google_model_object,
    _model_id_from_google_path,
    _model_id_from_openai_path,
    _openai_model_object,
    _response_assets,
    _rewrite_text_media_urls,
    _saved_files_by_kind,
    _web_feature_result,
)


def test_handler_has_routes():
    methods = [m for m in dir(GeminiHandler) if m.startswith("do_") or m.startswith("_handle_")]
    assert "do_GET" in methods
    assert "do_POST" in methods
    assert "do_OPTIONS" in methods
    assert "_handle_chat" in methods
    assert "_handle_image_generation" in methods
    assert "_handle_video_generation" in methods
    assert "_handle_audio_speech" in methods
    assert "_handle_responses" in methods
    assert "_handle_google_generate" in methods
    assert "_handle_claude_messages" in methods
    assert "_handle_admin_get" in methods
    assert "_handle_admin" in methods
    assert "_handle_cookie_import" in methods
    assert "_handle_cookie_browser_login" in methods
    assert "do_DELETE" in methods


def test_handler_uses_safe_json_parsing():
    """Bug regression: all POST handlers must use _parse_body (try/except), not raw json.loads."""
    import inspect
    for m in ("_handle_chat", "_handle_responses", "_handle_google_generate"):
        src = inspect.getsource(getattr(GeminiHandler, m))
        assert "_parse_body" in src, f"{m} must use _parse_body to avoid 500 on bad JSON"
        # Negative check: raw json.loads(body) without try/except
        # (server.py uses _parse_body wrapper which has try/except internally)
        assert "json.loads(body)" not in src, f"{m} calls json.loads(body) directly"


def test_threaded_server_inherits_correctly():
    """ThreadedServer must support concurrent requests and reuse address."""
    from socketserver import ThreadingMixIn
    from http.server import HTTPServer
    assert issubclass(ThreadedServer, ThreadingMixIn)
    assert issubclass(ThreadedServer, HTTPServer)
    assert ThreadedServer.daemon_threads is True
    assert ThreadedServer.allow_reuse_address is True


def test_model_path_helpers_decode_openai_and_google_model_ids():
    assert _model_id_from_openai_path("/v1/models/gemini-3.5-flash") == "gemini-3.5-flash"
    assert _model_id_from_openai_path("/v1/models/gemini-3.5-flash?foo=bar") == "gemini-3.5-flash"
    assert _model_id_from_google_path("/v1beta/models/gemini-3.5-flash") == "gemini-3.5-flash"
    assert _model_id_from_google_path("/v1beta/models/models%2Fgemini-3.5-flash") == "models/gemini-3.5-flash"


def test_model_object_helpers_return_client_compatible_shapes():
    cfg = {"desc": "Fast", "extra": {"web_feature": "canvas"}}
    openai_model = _openai_model_object("gemini-3.5-flash", cfg)
    google_model = _google_model_object("gemini-3.5-flash", cfg)

    assert openai_model["id"] == "gemini-3.5-flash"
    assert openai_model["object"] == "model"
    assert openai_model["web_feature"] == "canvas"
    assert google_model["name"] == "models/gemini-3.5-flash"
    assert "generateContent" in google_model["supportedGenerationMethods"]


def test_anonymous_single_model_lookup_accepts_gemini_3_5_flash(tmp_path):
    from gemini_web2api.config import CONFIG

    old_values = {
        key: CONFIG.get(key)
        for key in ("cookie_file", "api_keys", "host", "expose_experimental_models", "expose_web_feature_models")
    }
    CONFIG["cookie_file"] = str(tmp_path / "missing-cookie.txt")
    CONFIG["api_keys"] = []
    CONFIG["host"] = "127.0.0.1"
    CONFIG["expose_experimental_models"] = False
    CONFIG["expose_web_feature_models"] = False
    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base_url + "/v1/models/gemini-3.5-flash", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert data["id"] == "gemini-3.5-flash"

        with urllib.request.urlopen(base_url + "/v1/models/", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert [item["id"] for item in data["data"]] == [
            "gemini-3.5-flash",
            "gemini-3.5-flash-thinking",
            "gemini-3.1-pro",
            "gemini-3.1-pro-enhanced",
            "gemini-auto",
            "gemini-3.5-flash-thinking-lite",
            "gemini-flash-lite",
        ]
        assert "nano-banana-2" not in {item["id"] for item in data["data"]}

        with urllib.request.urlopen(base_url + "/v1beta/models/gemini-3.5-flash", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert data["name"] == "models/gemini-3.5-flash"

        with urllib.request.urlopen(base_url + "/v1beta/models/", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert [item["name"] for item in data["models"]] == [
            "models/gemini-3.5-flash",
            "models/gemini-3.5-flash-thinking",
            "models/gemini-3.1-pro",
            "models/gemini-3.1-pro-enhanced",
            "models/gemini-auto",
            "models/gemini-3.5-flash-thinking-lite",
            "models/gemini-flash-lite",
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        CONFIG.update(old_values)


def test_authorized_accepts_comma_separated_bearer_keys():
    """HelloGML compatibility: Authorization may contain a comma-separated key pool."""
    from gemini_web2api.config import CONFIG

    old_keys = CONFIG.get("api_keys")
    CONFIG["api_keys"] = ["key-a", "key-b"]
    handler = object.__new__(GeminiHandler)
    handler.headers = {"Authorization": "Bearer wrong-key, key-b"}
    try:
        assert handler._authorized() is True
    finally:
        CONFIG["api_keys"] = old_keys


def test_authorized_accepts_comma_separated_x_api_key():
    from gemini_web2api.config import CONFIG

    old_keys = CONFIG.get("api_keys")
    CONFIG["api_keys"] = ["key-a", "key-b"]
    handler = object.__new__(GeminiHandler)
    handler.headers = {"x-api-key": "wrong-key,key-a"}
    try:
        assert handler._authorized() is True
    finally:
        CONFIG["api_keys"] = old_keys


def test_api_keys_protect_google_admin_and_api_routes():
    assert GeminiHandler._path_requires_auth("/v1/chat/completions") is True
    assert GeminiHandler._path_requires_auth("/v1/images/generations") is True
    assert GeminiHandler._path_requires_auth("/v1/videos/generations") is True
    assert GeminiHandler._path_requires_auth("/v1/audio/speech") is True
    assert GeminiHandler._path_requires_auth("/v1beta/models/gemini:generateContent") is True
    assert GeminiHandler._path_requires_auth("/admin/cookie") is True
    assert GeminiHandler._path_requires_auth("/api/config") is True
    assert GeminiHandler._path_requires_auth("/") is False


def test_local_dashboard_bypass_allows_loopback_api_only():
    from gemini_web2api.config import CONFIG

    old_values = {
        "api_keys": CONFIG.get("api_keys"),
        "dashboard_local_bypass": CONFIG.get("dashboard_local_bypass"),
    }
    CONFIG["api_keys"] = ["secret"]
    CONFIG["dashboard_local_bypass"] = True
    handler = object.__new__(GeminiHandler)
    try:
        handler.path = "/api/dashboard"
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 12345)
        assert handler._dashboard_local_authorized() is True
        assert handler._authorized() is False

        handler.path = "/v1/chat/completions"
        assert handler._dashboard_local_authorized() is False

        handler.path = "/api/dashboard"
        handler.client_address = ("192.168.1.10", 12345)
        assert handler._dashboard_local_authorized() is False
    finally:
        CONFIG.update(old_values)


def test_safe_config_redacts_sensitive_values():
    from gemini_web2api.config import CONFIG

    old_values = {key: CONFIG.get(key) for key in ("api_keys", "xsrf_token", "proxy", "proxy_subscriptions", "proxy_import_sources", "accounts", "proxy_account_bindings")}
    CONFIG["api_keys"] = ["key-a", "key-b"]
    CONFIG["xsrf_token"] = "secret-token"
    CONFIG["proxy"] = "http://user:pass@example.test:8080"
    CONFIG["proxy_subscriptions"] = ["https://example.test/sub?token=secret"]
    CONFIG["proxy_import_sources"] = {
        "subscriptions": ["https://example.test/sub?token=secret"],
        "direct_links": ["http://user:pass@example.test:8080"],
        "providers": {"http://user:pass@example.test:8080": "vendor-a"},
    }
    CONFIG["accounts"] = [{
        "id": "u/1",
        "label": "Work",
        "primary_proxy": "http://user:pass@account-proxy.test:9001",
        "fallback_group": "Healthy",
        "cookie_file": "cookies/u1.txt",
    }]
    CONFIG["proxy_account_bindings"] = [{
        "account_id": "u/1",
        "primary_proxy": "http://user:pass@account-proxy.test:9001",
        "fallback_group": "Healthy",
    }]
    try:
        safe = GeminiHandler._safe_config()
        assert safe["api_keys"] == ["***", "***"]
        assert safe["xsrf_token"] == "***"
        assert safe["proxy"] == "***"
        assert safe["proxy_subscriptions"] == ["***"]
        assert safe["proxy_import_sources"] == "***"
        assert safe["accounts"][0]["primary_proxy"] == "http://***@account-proxy.test:9001"
        assert safe["proxy_account_bindings"][0]["primary_proxy"] == "http://***@account-proxy.test:9001"
        safe_json = json.dumps(safe)
        assert "user:pass" not in safe_json
        assert "secret-token" not in safe_json
    finally:
        CONFIG.update(old_values)


def test_config_update_reinitializes_proxy_pool(monkeypatch, tmp_path):
    from gemini_web2api.config import CONFIG

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    old_values = {key: CONFIG.get(key) for key in ("proxy_pool_enabled", "proxies", "proxy_pool_health_check")}
    calls = []

    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))
    monkeypatch.setattr("gemini_web2api.admin.init_admin", lambda: None)
    monkeypatch.setattr("gemini_web2api.proxy_builtin.init_pool_from_config", lambda cfg: calls.append(dict(cfg)))

    handler = object.__new__(GeminiHandler)
    sent = {}
    handler.send_json = lambda data, status=200: sent.update({"data": data, "status": status})

    try:
        payload = {
            "proxy_pool_enabled": True,
            "proxies": ["http://127.0.0.1:9001"],
            "proxy_pool_health_check": False,
        }
        handler._handle_config_update(json.dumps(payload).encode("utf-8"))

        assert sent["status"] == 200
        assert sent["data"]["success"] is True
        assert len(calls) == 1
        assert calls[0]["proxy_pool_enabled"] is True
        assert calls[0]["proxies"] == ["http://127.0.0.1:9001"]
    finally:
        CONFIG.update(old_values)


def test_config_update_ignores_masked_api_keys(monkeypatch, tmp_path):
    from gemini_web2api.config import CONFIG

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"api_keys": ["real-key"], "default_model": "gemini-3.5-flash"}),
        encoding="utf-8",
    )
    old_values = {
        "api_keys": CONFIG.get("api_keys"),
        "default_model": CONFIG.get("default_model"),
    }

    monkeypatch.setattr("gemini_web2api.config.find_config", lambda: str(config_path))
    monkeypatch.setattr("gemini_web2api.admin.init_admin", lambda: None)

    handler = object.__new__(GeminiHandler)
    sent = {}
    handler.send_json = lambda data, status=200: sent.update({"data": data, "status": status})
    CONFIG["api_keys"] = ["real-key"]

    try:
        payload = {"api_keys": ["***"], "default_model": "gemini-2.5-flash"}
        handler._handle_config_update(json.dumps(payload).encode("utf-8"))

        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert sent["status"] == 200
        assert sent["data"]["skipped_masked_keys"] == ["api_keys"]
        assert saved["api_keys"] == ["real-key"]
        assert CONFIG["api_keys"] == ["real-key"]
        assert saved["default_model"] == "gemini-2.5-flash"
        assert CONFIG["default_model"] == "gemini-2.5-flash"
    finally:
        CONFIG.update(old_values)


def test_web_feature_result_marks_image_without_artifact_limited():
    result = _web_feature_result({"web_feature": "image_generation", "web_model_name": "Nano Banana 2"}, [])
    assert result["id"] == "image_generation"
    assert result["requested_model"] == "Nano Banana 2"
    assert result["runtime_status"] == "limited"


def test_web_feature_result_marks_canvas_artifact_supported():
    result = _web_feature_result({"web_feature": "canvas"}, response_artifacts=[{"type": "code"}])
    assert result["id"] == "canvas"
    assert result["runtime_status"] == "supported"


def test_web_feature_result_marks_video_artifact_supported():
    result = _web_feature_result(
        {"web_feature": "video_generation"},
        response_media=[{"kind": "video", "url": "https://example.test/a.mp4"}],
    )
    assert result["id"] == "video_generation"
    assert result["runtime_status"] == "supported"
    assert result["artifact_count"] == 1


def test_web_feature_result_marks_audio_artifact_supported():
    result = _web_feature_result(
        {"web_feature": "text_to_speech"},
        response_media=[{"kind": "audio", "url": "data:audio/mp3;base64,AA=="}],
    )
    assert result["id"] == "text_to_speech"
    assert result["runtime_status"] == "supported"
    assert result["artifact_count"] == 1


def test_response_assets_uses_raw_response_for_media():
    raw = '["wrb.fr","x","https:\\/\\/example.test\\/generated.mp4"]'
    images, media, artifacts = _response_assets("Generated.", raw)
    assert images == []
    assert artifacts == []
    assert any(item["kind"] == "video" and item["url"] == "https://example.test/generated.mp4" for item in media)


def test_assets_and_files_adds_absolute_download_url(tmp_path):
    from gemini_web2api.config import CONFIG

    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path)
    handler = object.__new__(GeminiHandler)
    handler.headers = {"Host": "127.0.0.1:8081"}
    try:
        images, media, artifacts, files = handler._assets_and_files("```python\nprint('ok')\n```")
        assert images == []
        assert media == []
        assert len(artifacts) == 1
        assert len(files) == 1
        assert files[0]["download_url"].startswith("http://127.0.0.1:8081/artifacts/")
        assert files[0]["materialized"]["download_url"].startswith("http://127.0.0.1:8081/artifacts/")
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_assets_and_files_drops_unfetchable_googleusercontent_placeholder(tmp_path):
    from gemini_web2api.config import CONFIG

    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path)
    handler = object.__new__(GeminiHandler)
    handler.headers = {"Host": "127.0.0.1:8081"}
    try:
        text = "http://googleusercontent.com/image_generation_content/0"
        images, media, artifacts, files = handler._assets_and_files(text)

        assert images == []
        assert media == []
        assert artifacts == []
        assert len(files) == 1
        assert files[0]["source_url"] == text
        assert files[0]["materialized"]["status"] == "unresolved"
        assert files[0]["materialized"]["reason"] == "placeholder_url_not_downloadable"
        assert _rewrite_text_media_urls(text, files) == ""
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_rewrite_text_media_urls_replaces_saved_source_with_download_url():
    files = [{
        "kind": "image",
        "source_url": "https://lh3.googleusercontent.com/generated-token",
        "download_url": "http://127.0.0.1:8081/artifacts/generated.png",
        "materialized": {"status": "saved"},
    }]

    assert _rewrite_text_media_urls("see https://lh3.googleusercontent.com/generated-token", files) == (
        "see http://127.0.0.1:8081/artifacts/generated.png"
    )
    assert _saved_files_by_kind(files, "image") == files


def test_generate_with_file_fallback_retries_text_only_on_bard_1003(monkeypatch):
    calls = []

    monkeypatch.setattr("gemini_web2api.server._upload_images", lambda images: ["/contrib_service/ref"])

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        calls.append({"prompt": prompt, "file_refs": file_refs})
        if file_refs:
            raise RuntimeError("Gemini upstream rejected request: BardErrorInfo [1003]")
        return {"text": "text-only fallback", "raw": ""}

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    response, status = _generate_with_file_fallback(
        "describe this", 1, 4, images=[(b"image", "image/png")])

    assert response["text"] == "text-only fallback"
    assert status["runtime_status"] == "limited"
    assert status["reason"] == "BardErrorInfo [1003]"
    assert status["fallback"] == "text_only"
    assert calls[0]["file_refs"] == ["/contrib_service/ref"]
    assert calls[1]["file_refs"] is None
    assert "do not pretend to inspect" in calls[1]["prompt"]


def test_generate_with_file_fallback_does_not_swallow_other_errors(monkeypatch):
    monkeypatch.setattr("gemini_web2api.server._upload_images", lambda images: ["/contrib_service/ref"])

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None):
        raise RuntimeError("unrelated upstream failure")

    monkeypatch.setattr("gemini_web2api.server.generate_with_metadata", fake_generate)

    try:
        _generate_with_file_fallback("describe this", 1, 4, images=[(b"image", "image/png")])
    except RuntimeError as exc:
        assert "unrelated upstream failure" in str(exc)
    else:
        raise AssertionError("non-file-handoff errors must be preserved")
