import base64
import json
import threading
import urllib.request
from pathlib import Path

from gemini_web2api.artifact_store import materialize_media_item, materialize_response_files, resolve_artifact_path
from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer


def test_materialize_response_files_saves_data_url_and_code(tmp_path):
    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path)
    try:
        payload = base64.b64encode(b"hello").decode("ascii")
        files = materialize_response_files(
            media=[{"kind": "file", "url": f"data:text/plain;base64,{payload}"}],
            artifacts=[{"type": "code", "language": "python", "content": "print('ok')"}],
        )

        assert len(files) == 2
        local_paths = [item["local_path"] for item in files]
        assert all(tmp_path in Path(path).parents for path in local_paths)
        assert any(Path(path).read_bytes() == b"hello" for path in local_paths)
        assert any(Path(path).read_text(encoding="utf-8") == "print('ok')" for path in local_paths)
        assert all(item["download_url"].startswith("/artifacts/") for item in files)
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_resolve_artifact_path_rejects_outside_directory(tmp_path):
    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path / "artifacts")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        assert resolve_artifact_path("../outside.txt") == ""
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_materialize_media_item_marks_googleusercontent_placeholder_unresolved(tmp_path):
    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path)
    try:
        item = materialize_media_item({
            "kind": "image",
            "url": "http://googleusercontent.com/image_generation_content/0",
        })
        assert item["source_url"] == "http://googleusercontent.com/image_generation_content/0"
        assert item["materialized"]["status"] == "unresolved"
        assert item["materialized"]["reason"] == "placeholder_url_not_downloadable"
        assert "download_url" not in item
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_materialize_media_item_downloads_with_gemini_browser_headers(monkeypatch, tmp_path):
    from gemini_web2api import artifact_store

    old_values = {
        "artifact_dir": CONFIG.get("artifact_dir"),
        "auth_user": CONFIG.get("auth_user"),
        "proxy_enabled": CONFIG.get("proxy_enabled"),
        "proxy": CONFIG.get("proxy"),
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
    }
    CONFIG["artifact_dir"] = str(tmp_path)
    CONFIG["auth_user"] = "1"
    CONFIG["proxy_enabled"] = False
    CONFIG["proxy"] = None
    CONFIG["proxy_pool_enabled"] = False
    captured_headers = []

    class FakeResponse:
        headers = {"Content-Type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            if getattr(self, "_used", False):
                return b""
            self._used = True
            return b"\x89PNG\r\n\x1a\nfake"

    def fake_urlopen(req, context=None, timeout=None):
        captured_headers.append(dict(req.header_items()))
        return FakeResponse()

    monkeypatch.setattr(artifact_store, "get_current_request_cookie", lambda: ("SID=sid; SAPISID=sapisid", "sapisid"))
    monkeypatch.setattr(artifact_store.urllib.request, "urlopen", fake_urlopen)

    try:
        item = artifact_store.materialize_media_item({
            "kind": "image",
            "url": "https://lh3.googleusercontent.com/gg-dl/generated-token",
        })

        assert item["materialized"]["status"] == "saved"
        headers = captured_headers[-1]
        assert headers["Cookie"] == "SID=sid; SAPISID=sapisid"
        assert headers["Authorization"].startswith("SAPISIDHASH ")
        assert headers["Referer"] == "https://gemini.google.com/u/1/app"
        assert headers["Origin"] == "https://gemini.google.com"
        assert headers["X-goog-authuser"] == "1"
    finally:
        CONFIG.update(old_values)


def test_materialize_generated_image_uses_resolved_download_url(monkeypatch, tmp_path):
    from gemini_web2api import artifact_store

    old_dir = CONFIG.get("artifact_dir")
    CONFIG["artifact_dir"] = str(tmp_path)
    seen = {}

    def fake_download(url, max_bytes=None):
        seen["url"] = url
        return b"\x89PNG\r\n\x1a\nresolved", "image/png"

    monkeypatch.setattr(
        artifact_store,
        "resolve_generated_image_download_url",
        lambda item: "https://example.com/resolved-image",
    )
    monkeypatch.setattr(artifact_store, "_download_url", fake_download)

    try:
        item = artifact_store.materialize_media_item({
            "kind": "image",
            "type": "gemini_generated_image",
            "url": "https://lh3.googleusercontent.com/gg-dl/preview-token",
            "name": "generated.png",
            "cid": "cid",
            "rid": "rid",
            "rcid": "rcid",
            "image_id": "http://googleusercontent.com/image_generation_content/0",
        })

        assert seen["url"] == "https://example.com/resolved-image"
        assert item["materialized"]["status"] == "saved"
        assert item["download_url"].startswith("/artifacts/")
        assert Path(item["local_path"]).read_bytes().startswith(b"\x89PNG")
    finally:
        CONFIG["artifact_dir"] = old_dir


def test_download_url_uses_active_request_proxy(monkeypatch):
    from gemini_web2api import artifact_store

    captured = {"build_opener": False, "opened_url": ""}

    class FakeResponse:
        headers = {"Content-Type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            if getattr(self, "_used", False):
                return b""
            self._used = True
            return b"\x89PNG\r\n\x1a\nproxied"

    class FakeOpener:
        def open(self, req, timeout=None):
            captured["opened_url"] = req.full_url
            return FakeResponse()

    def fake_build_opener(*handlers):
        captured["build_opener"] = True
        assert any(handler.__class__.__name__ == "ProxyHandler" for handler in handlers)
        return FakeOpener()

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("direct urlopen should not be used when a request proxy is active")

    monkeypatch.setattr(artifact_store, "get_current_request_cookie", lambda: ("", None))
    monkeypatch.setattr(artifact_store, "get_current_request_proxy", lambda lease_if_missing=False: ("http://proxy.example.test:8080", False))
    monkeypatch.setattr(artifact_store.urllib.request, "build_opener", fake_build_opener)
    monkeypatch.setattr(artifact_store.urllib.request, "urlopen", fail_urlopen)

    data, mime_type = artifact_store._download_url("https://lh3.googleusercontent.com/gg-dl/generated-token")

    assert data.startswith(b"\x89PNG")
    assert mime_type == "image/png"
    assert captured["build_opener"] is True
    assert captured["opened_url"] == "https://lh3.googleusercontent.com/gg-dl/generated-token"


def test_artifacts_route_serves_saved_file_and_rejects_traversal(tmp_path):
    old_values = {"artifact_dir": CONFIG.get("artifact_dir"), "api_keys": CONFIG.get("api_keys")}
    CONFIG["artifact_dir"] = str(tmp_path / "artifacts")
    CONFIG["api_keys"] = []
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "saved.txt").write_text("download me", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base_url + "/artifacts/saved.txt", timeout=5) as response:
            assert response.status == 200
            assert response.read().decode("utf-8") == "download me"

        try:
            urllib.request.urlopen(base_url + "/artifacts/%2e%2e%2Foutside.txt", timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
            data = json.loads(exc.read().decode("utf-8"))
            assert data["error"]["message"] == "artifact not found"
        else:
            raise AssertionError("path traversal must not be served")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        CONFIG.update(old_values)
