"""Tests for capability matrix metadata."""
from gemini_web2api.capabilities import CAPABILITIES, capability_status_counts, get_capability_report


def test_capability_report_has_expected_core_features():
    report = get_capability_report(has_cookie=True)
    ids = {item["id"] for item in report["capabilities"]}
    assert "openai_chat" in ids
    assert "google_generate_content" in ids
    assert "multimodal_prompt" in ids
    assert "image_generation" in ids
    assert report["has_cookie"] is True
    assert "gemini-3.1-pro" in report["models"]
    assert "web_features" in report
    assert "Nano Banana 2" in report["web_features"]["image_generation"]["ui_models"]
    assert "Omni" in report["web_features"]["video_generation"]["ui_models"]
    assert "source_discovered_web_models" in report
    discovered = {item["name"] for item in report["source_discovered_web_models"]}
    assert "gemini-2.5-flash-preview-tts" in discovered


def test_capability_status_counts():
    counts = capability_status_counts(CAPABILITIES)
    assert counts["supported"] >= 1
    assert counts["limited"] >= 1
    assert counts["experimental"] >= 1
