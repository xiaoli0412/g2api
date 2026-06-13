"""Tests for gemini_web2api.gemini (payload building, header building, BL discovery)."""
import json
import urllib.parse
import time
import pytest

from gemini_web2api.gemini import (
    _build_payload,
    _extract_xsrf_token_from_html,
    clean_text,
    extract_response_text,
    extract_generated_image_items,
    extract_images_from_response,
    extract_media_from_response,
    extract_artifacts_from_response,
    get_full_size_image_url,
    make_sapisidhash,
    _get_url,
    _resolve_bl,
    _discover_bl,
    _bl_cache,
)


def test_clean_text_strips_code_artifacts():
    assert clean_text('```python?code_reference&code_event_index=0\nprint(1)\n```\nhello') == 'hello'


def test_clean_text_strips_card_content():
    assert clean_text('hello http://googleusercontent.com/card_content/123\nworld') == 'hello world'


def test_clean_text_keeps_valid_code():
    assert clean_text('```python\nprint(1)\n```') == '```python\nprint(1)\n```'


def test_clean_text_can_preserve_stream_delta_spacing():
    assert clean_text(" Gemini", strip=False) == " Gemini"


def test_extract_response_text_empty():
    assert extract_response_text("") == ""
    assert extract_response_text("garbage") == ""


def test_make_sapisidhash_format():
    h = make_sapisidhash("test")
    assert h.startswith("SAPISIDHASH ")
    ts_str, _ = h.split(" ", 1)[1].split("_", 1)
    assert int(ts_str) > 0


def test_build_payload_basic():
    body = _build_payload("hi", 1, 4)
    parsed = urllib.parse.parse_qs(body)
    outer = json.loads(parsed["f.req"][0])
    inner = json.loads(outer[1])
    assert inner[79] == 1
    assert inner[17] == [[4]]


def test_build_payload_with_thinking():
    body = _build_payload("hi", 2, 0)
    parsed = urllib.parse.parse_qs(body)
    inner = json.loads(json.loads(parsed["f.req"][0])[1])
    assert inner[79] == 2
    assert inner[17] == [[0]]  # deepest thinking


def test_generate_stream_fake_mode_uses_configured_chunk_size(monkeypatch):
    from gemini_web2api import gemini
    from gemini_web2api.config import CONFIG

    old_values = {
        "stream_mode": CONFIG.get("stream_mode"),
        "stream_chunk_chars": CONFIG.get("stream_chunk_chars"),
        "fake_stream_delay_ms": CONFIG.get("fake_stream_delay_ms"),
    }
    CONFIG["stream_mode"] = "fake"
    CONFIG["stream_chunk_chars"] = 2
    CONFIG["fake_stream_delay_ms"] = 0
    monkeypatch.setattr(gemini, "generate", lambda *args, **kwargs: "abcdef")
    try:
        assert list(gemini.generate_stream("p", 1, 4)) == ["ab", "cd", "ef"]
    finally:
        CONFIG.update(old_values)


def test_build_payload_with_extra_fields():
    extra = {31: 2, 80: 3}
    body = _build_payload("hi", 3, 4, extra_fields=extra)
    parsed = urllib.parse.parse_qs(body)
    inner = json.loads(json.loads(parsed["f.req"][0])[1])
    assert inner[31] == 2
    assert inner[80] == 3
    assert extra == {31: 2, 80: 3}


def test_build_payload_search_does_not_mutate_extra_fields():
    extra = {"search": True, 80: 3}
    body = _build_payload("hi", 1, 4, extra_fields=extra)
    parsed = urllib.parse.parse_qs(body)
    inner = json.loads(json.loads(parsed["f.req"][0])[1])
    assert inner[30] == [5]
    assert inner[80] == 3
    assert extra == {"search": True, 80: 3}


def test_build_payload_with_file_refs():
    body = _build_payload("hi", 1, 4, file_refs=["/uploaded/abc"])
    parsed = urllib.parse.parse_qs(body)
    inner = json.loads(json.loads(parsed["f.req"][0])[1])
    assert inner[0][3] == [[None, None, "/uploaded/abc"]]


def test_build_payload_includes_xsrf_token():
    from gemini_web2api import gemini
    original = gemini.CONFIG.get("xsrf_token")
    gemini.CONFIG["xsrf_token"] = "TEST_TOKEN_123"
    try:
        body = _build_payload("hi", 1, 4)
        assert "at=TEST_TOKEN_123" in body
    finally:
        gemini.CONFIG["xsrf_token"] = original


def test_extract_xsrf_token_from_html():
    assert _extract_xsrf_token_from_html('{"SNlM0e":"AOOh0P_token:123"}') == "AOOh0P_token:123"
    assert _extract_xsrf_token_from_html("{}") == ""


def test_build_payload_auto_discovers_xsrf_token(monkeypatch):
    from gemini_web2api import gemini

    original = gemini.CONFIG.get("xsrf_token")
    gemini.CONFIG["xsrf_token"] = None
    monkeypatch.setattr(gemini, "_resolve_xsrf_token", lambda: "AUTO_XSRF")
    try:
        body = _build_payload("hi", 1, 4)
        assert "at=AUTO_XSRF" in body
    finally:
        gemini.CONFIG["xsrf_token"] = original


def test_get_url_uses_bl_token():
    url = _get_url()
    assert "bl=" in url
    bl = url.split("bl=", 1)[1].split("&", 1)[0]
    assert bl.startswith("boq_assistant-bard-web-server_")
    assert "_p0" in bl


def test_resolve_bl_returns_nonempty():
    bl = _resolve_bl()
    assert bl
    assert bl.startswith("boq_assistant-bard-web-server_")


def test_discover_bl_uses_cache(monkeypatch):
    """_discover_bl should not hit the network if cache is fresh."""
    _bl_cache["bl"] = "cached_bl_value"
    _bl_cache["ts"] = time.time()
    # If network was called this would fail without internet; cache must serve
    assert _discover_bl() == "cached_bl_value"


def test_extract_response_text_synthetic_line():
    """Build a synthetic StreamGenerate line and parse it back.

    Parser contract:
      - line must contain '"wrb.fr"' and have length >= 200
      - arr[0][2] is a JSON string >= 50 chars
      - that JSON parses to a list with len > 4 and truthy element [4]
      - element [4] is a list of [str_key, [str, ...]] parts
    """
    inner = [None, None, None, None, [["k", ["hello world"]]]]
    inner_str = json.dumps(inner)
    assert len(inner_str) >= 50
    # arr[0] = ["wrb.fr", "...", inner_str]; pad to reach length >= 200
    arr = [["wrb.fr", "x", inner_str, "p" * 200]]
    raw_line = json.dumps(arr)
    assert '"wrb.fr"' in raw_line and len(raw_line) >= 200, f"raw_line too short: {len(raw_line)}"
    raw = ")]}'\n123\n" + raw_line + "\n"
    out = extract_response_text(raw)
    assert "hello" in out, f"failed to parse synthetic: {out!r}"


def test_extract_response_text_bard_error_json_form():
    raw = '[["wrb.fr",null,null,null,null,[3,null,[["type.googleapis.com/assistant.boq.bard.application.BardErrorInfo",[1003]]]]]]'
    try:
        extract_response_text(raw)
    except RuntimeError as exc:
        assert "BardErrorInfo [1003]" in str(exc)
    else:
        raise AssertionError("BardErrorInfo should raise a RuntimeError")


def test_extract_images_from_response_markdown():
    """Test extracting markdown image syntax."""
    text = "Here is an image: ![cat](https://example.com/cat.png) and more text"
    images = extract_images_from_response(text)
    assert len(images) == 1
    assert images[0]["url"] == "https://example.com/cat.png"
    assert images[0]["alt"] == "cat"
    assert images[0]["type"] == "markdown"


def test_extract_images_from_response_empty():
    """Test extracting images from empty text."""
    assert extract_images_from_response("") == []
    assert extract_images_from_response("no images here") == []


def test_extract_images_from_response_deduplication():
    """Test that duplicate URLs are deduplicated."""
    text = "![img](https://example.com/a.png) and ![img](https://example.com/a.png)"
    images = extract_images_from_response(text)
    assert len(images) == 1


def test_extract_images_from_response_wrb_raw_non_text_field():
    """Media URLs can live outside final text in Gemini wrb.fr payloads."""
    inner = [None, None, None, None, [["k", ["Here is the generated image."]]], None, None, None]
    inner.append(["https://lh3.googleusercontent.com/generated-image.png"])
    raw = json.dumps([["wrb.fr", "x", json.dumps(inner), "p" * 200]]).replace("/", "\\/")

    images = extract_images_from_response(raw)

    assert any(item["url"] == "https://lh3.googleusercontent.com/generated-image.png" for item in images)


def test_extract_media_filters_gemini_web_ui_assets():
    text = (
        "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/expand/default/24px.svg "
        "https://www.gstatic.com/lamda/images/gemini_sparkle_aurora.svg "
        "https://lh3.googleusercontent.com/a/default-user=s64-c "
        "https://lh3.googleusercontent.com/generated-image.png"
    )

    images = extract_images_from_response(text)
    media = extract_media_from_response(text)

    assert [item["url"] for item in images] == ["https://lh3.googleusercontent.com/generated-image.png"]
    assert {item["url"] for item in media} == {"https://lh3.googleusercontent.com/generated-image.png"}


def test_extract_artifacts_from_response_code():
    """Test extracting code blocks."""
    text = "Here is code:\n```python\nprint('hello')\n```\nAnd more text"
    artifacts = extract_artifacts_from_response(text)
    assert len(artifacts) == 1
    assert artifacts[0]["type"] == "code"
    assert artifacts[0]["language"] == "python"
    assert "print('hello')" in artifacts[0]["content"]


def test_extract_artifacts_from_response_html():
    """Test extracting HTML blocks."""
    text = "Here is HTML:\n```html\n<div>Hello</div>\n```"
    artifacts = extract_artifacts_from_response(text)
    # HTML blocks are extracted twice: once as code block with lang=html, once as html block
    # This is expected behavior - the code block extraction catches all ``` blocks
    assert len(artifacts) >= 1
    html_artifacts = [a for a in artifacts if a["language"] == "html"]
    assert len(html_artifacts) >= 1
    assert "<div>Hello</div>" in html_artifacts[0]["content"]


def test_extract_artifacts_from_response_empty():
    """Test extracting artifacts from empty text."""
    assert extract_artifacts_from_response("") == []
    assert extract_artifacts_from_response("no code here") == []


def test_extract_artifacts_from_response_file_tag_and_generated_filename():
    text = (
        "Your PDF is ready.\n"
        "[file-tag: code-generated-file-2023_awards.pdf]\n"
        "Also see code-generated-file-summary.xlsx"
    )

    artifacts = extract_artifacts_from_response(text)

    assert {"code-generated-file-2023_awards.pdf", "code-generated-file-summary.xlsx"} == {
        item["name"] for item in artifacts if item["type"] == "file"
    }


def test_clean_text_keeps_googleusercontent_media_urls():
    """Generated media can be returned through googleusercontent URLs."""
    text = "Hello https://lh3.googleusercontent.com/abc123/test.png world"
    result = clean_text(text)
    assert "googleusercontent.com" in result
    assert "Hello" in result
    assert "world" in result


def test_extract_media_from_response_finds_image_video_audio():
    text = (
        "![img](https://example.com/a.png) "
        "https://example.com/clip.mp4 "
        "https://example.com/sound.mp3"
    )
    media = extract_media_from_response(text)
    assert {item["kind"] for item in media} == {"image", "video", "audio"}


def test_extract_media_from_response_wrb_raw_non_text_field():
    inner = [None, None, None, None, [["k", ["Here is the generated video."]]], None, None, None]
    inner.append(["https://example.com/generated-video.mp4"])
    raw = json.dumps([["wrb.fr", "x", json.dumps(inner), "p" * 200]]).replace("/", "\\/")

    media = extract_media_from_response(raw)

    assert any(item["kind"] == "video" and item["url"] == "https://example.com/generated-video.mp4" for item in media)


def test_extract_media_from_response_classifies_googleusercontent_without_extension():
    text = (
        '{"mimeType":"image/png","uri":"https://lh3.googleusercontent.com/generated-artifact-token"} '
        "https://lh3.googleusercontent.com/rd-ogw/avatar-token=s64-c"
    )

    images = extract_images_from_response(text)
    media = extract_media_from_response(text)

    assert [item["url"] for item in images] == ["https://lh3.googleusercontent.com/generated-artifact-token"]
    assert {item["kind"] for item in media} == {"image"}
    assert {item["url"] for item in media} == {"https://lh3.googleusercontent.com/generated-artifact-token"}


def test_extract_media_from_response_trims_gemini_nested_json_suffix():
    raw = (
        '["https://lh3.googleusercontent.com/gg-dl/AFfU-fIXPfzID5GR5PErcRmITYIQTJdgPxoVgENrTNFcDWojMCM_LXRClxmJQijzL4zhypu4KSNrKHbGwz2TOmBblOu3UvIhDQ4_sJ2scCJlMmCqXy57GLKe5Uykv41nSG_7fZdMwWT7gs_rBgHkM1K-b092TrVl-8-THeklhSQaLp0u1LWLcA\\",null,\\"$AQbORADBT3zUS3ed\\",null,null,2,[1781001976,998040770],null,\\"image/png\\"]'
    )

    media = extract_media_from_response(raw)

    assert media
    assert media[0]["kind"] == "image"
    assert media[0]["url"] == (
        "https://lh3.googleusercontent.com/gg-dl/"
        "AFfU-fIXPfzID5GR5PErcRmITYIQTJdgPxoVgENrTNFcDWojMCM_LXRClxmJQijzL4zhypu4KSNrKHbGwz2TOmBblOu3UvIhDQ4_sJ2scCJlMmCqXy57GLKe5Uykv41nSG_7fZdMwWT7gs_rBgHkM1K-b092TrVl-8-THeklhSQaLp0u1LWLcA"
    )


def test_extract_generated_image_items_from_structured_candidate():
    candidate = [
        "rcid-1",
        None,
        None,
        None,
        [["k", [""]]],
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        [None] * 13,
    ]
    candidate[12][7] = [[
        [
            None,
            None,
            None,
            [
                None,
                1,
                "generated-name.png",
                "https://lh3.googleusercontent.com/gg-dl/generated-token",
                None,
                "$AQb...",
                None,
                None,
                2,
                [1781001976, 998040770],
                "image/png",
                None,
                None,
                None,
                [1408, 768, 43965],
            ],
        ],
        ["http://googleusercontent.com/image_generation_content/0"],
    ]]
    inner = [None, ["cid-1", "rid-1"], None, None, [candidate]]
    raw = json.dumps([["wrb.fr", "x", json.dumps(inner), "p" * 200]])

    items = extract_generated_image_items(raw)
    media = extract_media_from_response(raw)

    assert items[0]["url"] == "https://lh3.googleusercontent.com/gg-dl/generated-token"
    assert items[0]["cid"] == "cid-1"
    assert items[0]["rid"] == "rid-1"
    assert items[0]["rcid"] == "rcid-1"
    assert items[0]["image_id"] == "http://googleusercontent.com/image_generation_content/0"
    assert items[0]["mime_type"] == "image/png"
    assert media[0]["type"] == "gemini_generated_image"


def test_get_full_size_image_url_parses_batchexecute_frame(monkeypatch):
    from gemini_web2api import gemini

    payload = json.dumps([["wrb.fr", "c8o8Fe", json.dumps(["https://example.com/fullsize"]), None]])
    seen = {}

    def fake_batch(rpcid, body, source_path="/app"):
        seen["rpcid"] = rpcid
        seen["body"] = json.loads(body)
        return ")]}'\n" + payload

    monkeypatch.setattr(gemini, "_batch_execute_rpc", fake_batch)

    url = get_full_size_image_url("cid", "rid", "rcid", "image-id")

    assert url == "https://example.com/fullsize"
    assert seen["rpcid"] == "c8o8Fe"
    assert seen["body"][1] == ["rid", "rcid", "cid", None, ""]


def test_extract_media_from_response_classifies_googlevideo_mime_urls():
    text = (
        '{"mimeType":"video/mp4","url":"https://rr1---sn.example.googlevideo.com/videoplayback?id=abc"} '
        '{"mimeType":"audio/mpeg","url":"https://storage.googleapis.com/generated/audio?id=def&mime=audio%2Fmpeg"}'
    )

    media = extract_media_from_response(text)

    assert any(item["kind"] == "video" and "googlevideo.com/videoplayback" in item["url"] for item in media)
    assert any(item["kind"] == "audio" and "storage.googleapis.com/generated/audio" in item["url"] for item in media)
def test_proxy_pool_fail_closed_when_no_healthy_proxy(monkeypatch):
    from gemini_web2api import gemini, proxy_builtin
    from gemini_web2api.config import CONFIG

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
        "proxy": CONFIG.get("proxy"),
        "proxy_health_policy": CONFIG.get("proxy_health_policy"),
    }
    pool = proxy_builtin.ProxyPool()
    pool.import_sources(direct_links=["http://127.0.0.1:9001"], provider="vendor-a")
    proxy_builtin._global_pool = pool
    CONFIG["proxy_pool_enabled"] = True
    CONFIG["proxy"] = "http://fallback.example.test:8080"
    CONFIG["proxy_health_policy"] = {"require_healthy": True}
    try:
        with pytest.raises(gemini.UpstreamError, match="No healthy proxy"):
            gemini._get_proxy_for_request()
    finally:
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)


def test_proxy_master_switch_bypasses_bad_proxy_pool(monkeypatch):
    from gemini_web2api import gemini, proxy_builtin
    from gemini_web2api.config import CONFIG

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_enabled": CONFIG.get("proxy_enabled"),
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
        "proxy": CONFIG.get("proxy"),
        "proxy_health_policy": CONFIG.get("proxy_health_policy"),
    }
    pool = proxy_builtin.ProxyPool()
    pool.import_sources(direct_links=["http://127.0.0.1:9001"], provider="vendor-a")
    proxy_builtin._global_pool = pool
    CONFIG["proxy_enabled"] = False
    CONFIG["proxy_pool_enabled"] = True
    CONFIG["proxy"] = "http://fallback.example.test:8080"
    CONFIG["proxy_health_policy"] = {"require_healthy": True}
    try:
        assert gemini._get_proxy_for_request() is None
        assert gemini.get_last_proxy_url() == ""
    finally:
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)


def test_account_binding_selects_bound_healthy_proxy(tmp_path):
    from gemini_web2api import gemini, proxy_builtin
    from gemini_web2api.config import CONFIG

    cookie_file = tmp_path / "account.cookie"
    cookie_file.write_text("SID=sid; SAPISID=sapisid", encoding="utf-8")

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
        "proxy_health_policy": CONFIG.get("proxy_health_policy"),
        "accounts": CONFIG.get("accounts"),
        "proxy_account_bindings": CONFIG.get("proxy_account_bindings"),
        "auth_user": CONFIG.get("auth_user"),
        "proxy": CONFIG.get("proxy"),
    }
    pool = proxy_builtin.ProxyPool()
    pool.import_sources(
        direct_links=["http://127.0.0.1:9001", "http://127.0.0.1:9002"],
        provider="vendor-a",
    )
    for node in pool.nodes:
        pool.mark_success(node, latency_ms=20)
    proxy_builtin._global_pool = pool
    bound_node = pool.nodes[1]
    CONFIG["proxy_pool_enabled"] = True
    CONFIG["proxy_health_policy"] = {"require_healthy": True}
    CONFIG["proxy"] = None
    CONFIG["auth_user"] = None
    CONFIG["accounts"] = [{
        "id": "u/1",
        "auth_user": "1",
        "cookie_file": str(cookie_file),
        "primary_proxy": bound_node.node_id,
        "enabled": True,
    }]
    CONFIG["proxy_account_bindings"] = []

    try:
        headers = gemini._build_headers()
        assert headers["X-Goog-AuthUser"] == "1"
        assert "SAPISID=sapisid" in headers["Cookie"]
        assert gemini._get_proxy_for_request() == bound_node.url
        assert pool._inflight[bound_node.node_id] == 1
    finally:
        gemini._release_proxy_for_request()
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)
        gemini._reset_request_account()
        gemini._account_cookie_cache.clear()
        gemini._account_index = 0


def test_account_binding_can_select_proxy_group(tmp_path):
    from gemini_web2api import gemini, proxy_builtin
    from gemini_web2api.config import CONFIG

    cookie_file = tmp_path / "account.cookie"
    cookie_file.write_text("SID=sid; SAPISID=sapisid", encoding="utf-8")

    old_pool = proxy_builtin._global_pool
    old_values = {
        "proxy_pool_enabled": CONFIG.get("proxy_pool_enabled"),
        "proxy_health_policy": CONFIG.get("proxy_health_policy"),
        "accounts": CONFIG.get("accounts"),
        "proxy_account_bindings": CONFIG.get("proxy_account_bindings"),
        "auth_user": CONFIG.get("auth_user"),
        "proxy": CONFIG.get("proxy"),
    }
    pool = proxy_builtin.ProxyPool()
    pool.add(proxy_builtin.ProxyNode("slow", proxy_builtin.ProxyType.HTTP, "slow.example.test", 9001, latency_ms=240))
    pool.add(proxy_builtin.ProxyNode("fast", proxy_builtin.ProxyType.HTTP, "fast.example.test", 9002, latency_ms=40))
    pool.configure_service_routing(
        groups=[{"name": "Work", "type": "url-test", "proxies": ["*"], "tolerance_ms": 20}],
        anonymous_policy={"group": "Work", "max_concurrent_per_proxy": 1},
    )
    proxy_builtin._global_pool = pool
    CONFIG["proxy_pool_enabled"] = True
    CONFIG["proxy_health_policy"] = {"require_healthy": True}
    CONFIG["proxy"] = None
    CONFIG["auth_user"] = None
    CONFIG["accounts"] = [{
        "id": "u/1",
        "auth_user": "1",
        "cookie_file": str(cookie_file),
        "primary_proxy": "Work",
        "enabled": True,
    }]
    CONFIG["proxy_account_bindings"] = []

    try:
        gemini._build_headers()
        assert gemini._get_proxy_for_request() == "http://fast.example.test:9002"
    finally:
        gemini._release_proxy_for_request()
        proxy_builtin._global_pool = old_pool
        CONFIG.update(old_values)
        gemini._reset_request_account()
        gemini._account_cookie_cache.clear()
        gemini._account_index = 0
