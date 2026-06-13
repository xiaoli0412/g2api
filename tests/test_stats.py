"""Tests for request detail and operational statistics."""

from gemini_web2api.stats import get_dashboard_data, get_request_detail, log_request


def test_log_request_keeps_detail_and_masks_sensitive_values():
    request_id = "req_test_detail"
    log_request(
        "gemini-test",
        12,
        8,
        endpoint="/v1/chat/completions",
        request_id=request_id,
        request_body={
            "model": "gemini-test",
            "messages": [{"role": "user", "content": "hello"}],
            "cookies": "SID=secret; SAPISID=secret",
        },
        response_body={"choices": [{"message": {"content": "world"}}]},
        duration_ms=42.4,
        proxy="http://127.0.0.1:7890",
        protocol="openai.chat",
        trace={"tool_calls": [{"name": "identify_self"}], "upstream_raw": "raw text"},
    )

    detail = get_request_detail(request_id)
    assert detail["endpoint"] == "/v1/chat/completions"
    assert detail["request_body"]["model"] == "gemini-test"
    assert detail["request_body"]["cookies"] == "***"
    assert detail["response_body"]["choices"][0]["message"]["content"] == "world"
    assert detail["trace"]["tool_calls"][0]["name"] == "identify_self"
    assert detail["trace"]["upstream_raw"] == "raw text"
    assert detail["duration_ms"] == 42.4
    assert detail["proxy"] == "http://127.0.0.1:7890"

    secret_proxy_id = "req_test_detail_secret_proxy"
    log_request(
        "gemini-test",
        1,
        1,
        request_id=secret_proxy_id,
        proxy="http://user:pass@example.proxy:8080",
    )
    secret_detail = get_request_detail(secret_proxy_id)
    assert secret_detail["proxy"] == "http://***@example.proxy:8080"


def test_log_request_respects_capture_body_toggles():
    from gemini_web2api.config import CONFIG

    old_values = {
        "capture_request_bodies": CONFIG.get("capture_request_bodies"),
        "capture_response_bodies": CONFIG.get("capture_response_bodies"),
    }
    CONFIG["capture_request_bodies"] = False
    CONFIG["capture_response_bodies"] = False
    try:
        request_id = "req_test_capture_toggle"
        log_request(
            "gemini-test",
            1,
            1,
            request_id=request_id,
            request_body={"messages": [{"content": "secret-ish prompt"}]},
            response_body={"choices": [{"message": {"content": "answer"}}]},
        )
        detail = get_request_detail(request_id)
        assert detail["request_body"] == "<disabled>"
        assert detail["response_body"] == "<disabled>"
    finally:
        CONFIG.update(old_values)


def test_dashboard_summary_includes_operations_totals():
    log_request("gemini-ops", 4, 6, request_id="req_test_ops", duration_ms=10)
    data = get_dashboard_data()
    summary = data["summary"]

    assert summary["total_requests"] >= 1
    assert summary["total_tokens"] >= 10
    assert "total_success" in summary
    assert "success_rate" in summary
    assert "avg_latency_ms" in summary
    assert "requests_per_minute" in summary
    assert data["recent_requests"][0]["id"]
