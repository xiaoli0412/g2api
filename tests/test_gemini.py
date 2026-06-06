"""Tests for gemini_web2api.gemini (payload building, header building, BL discovery)."""
import json
import urllib.parse
import time

import pytest

from gemini_web2api.gemini import (
    _build_payload,
    clean_text,
    extract_response_text,
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


def test_build_payload_with_extra_fields():
    body = _build_payload("hi", 3, 4, extra_fields={31: 2, 80: 3})
    parsed = urllib.parse.parse_qs(body)
    inner = json.loads(json.loads(parsed["f.req"][0])[1])
    assert inner[31] == 2
    assert inner[80] == 3


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
