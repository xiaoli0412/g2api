"""Tests for live verification report helpers (no network)."""
from gemini_web2api import live_verify
from gemini_web2api.live_verify import _shorten, summarize_results


def test_shorten_normalizes_whitespace_and_truncates():
    text = "hello\n" + ("world " * 100)
    shortened = _shorten(text, limit=20)
    assert "\n" not in shortened
    assert shortened.endswith("...")
    assert len(shortened) == 23


def test_summarize_results_splits_failures_and_limited():
    summary = summarize_results([
        {"name": "a", "status": "pass"},
        {"name": "b", "status": "fail"},
        {"name": "c", "status": "limited"},
    ])
    assert summary["total"] == 3
    assert summary["counts"] == {"pass": 1, "fail": 1, "limited": 1}
    assert summary["failed"] == ["b"]
    assert summary["limited"] == ["c"]


def test_run_live_checks_passes_api_key_to_protected_gets(monkeypatch):
    seen_gets = []

    def fake_get_json(client, results, name, path, api_key=None):
        seen_gets.append((name, path, api_key))
        if name == "openai_models":
            return {"data": [{"id": "gemini-3.5-flash"}]}
        if name == "cookie_status_api":
            return {}
        return {}

    monkeypatch.setattr(live_verify, "_get_json", fake_get_json)
    monkeypatch.setattr(live_verify, "_post_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(live_verify, "_stream_openai", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_verify, "_stream_google", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_verify, "_multimodal_checks", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_verify, "_web_tool_checks", lambda *args, **kwargs: None)

    live_verify.run_live_checks("http://127.0.0.1:1", api_key="sk-test")

    by_name = {name: key for name, _path, key in seen_gets}
    assert by_name["root"] is None
    assert by_name["openai_models"] == "sk-test"
    assert by_name["gemini_models"] == "sk-test"
    assert by_name["capabilities"] == "sk-test"
    assert by_name["admin_cookie_health"] == "sk-test"
    assert by_name["dashboard_api"] == "sk-test"
    assert by_name["cookie_status_api"] == "sk-test"
