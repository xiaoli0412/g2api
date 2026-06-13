"""Tests for multimodal probe payload construction (no network)."""
import json
import urllib.parse

from gemini_web2api.multimodal_probe import _payload_for_variant, _variants


def test_payload_variants_are_distinct_and_parseable():
    variants = {item["name"]: item for item in _variants()}
    current = _payload_for_variant("prompt", "/contrib_service/ref", variants["current"])
    har_like = _payload_for_variant("prompt", "/contrib_service/ref", variants["current_har_fields"])

    current_inner = json.loads(json.loads(urllib.parse.parse_qs(current)["f.req"][0])[1])
    har_inner = json.loads(json.loads(urllib.parse.parse_qs(har_like)["f.req"][0])[1])

    assert current_inner[0][3] == [[None, None, "/contrib_service/ref"]]
    assert current_inner[68] == 1
    assert len(har_inner) == 81
    assert har_inner[68] == 2
    assert har_inner[80] == 1
