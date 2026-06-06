"""Tests for gemini_web2api.server HTTP handler structure (no real network)."""
from gemini_web2api.server import GeminiHandler, ThreadedServer


def test_handler_has_routes():
    methods = [m for m in dir(GeminiHandler) if m.startswith("do_") or m.startswith("_handle_")]
    assert "do_GET" in methods
    assert "do_POST" in methods
    assert "do_OPTIONS" in methods
    assert "_handle_chat" in methods
    assert "_handle_responses" in methods
    assert "_handle_google_generate" in methods


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
