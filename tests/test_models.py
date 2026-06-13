"""Tests for gemini_web2api.models."""
from gemini_web2api.models import (
    CORE_MODEL_IDS,
    MODELS,
    SOURCE_DISCOVERED_WEB_MODELS,
    WEB_FEATURES,
    get_available_models,
    get_all_models,
    resolve_model,
)


def test_resolve_known_model():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash")
    assert err is None
    assert mode == 1
    assert think == 4
    assert search is False


def test_default_available_models_match_upstream_core_list():
    available = get_available_models(has_cookie=True)
    assert list(available) == list(CORE_MODEL_IDS)
    assert list(CORE_MODEL_IDS) == [
        "gemini-3.5-flash",
        "gemini-3.5-flash-thinking",
        "gemini-3.1-pro",
        "gemini-3.1-pro-enhanced",
        "gemini-auto",
        "gemini-3.5-flash-thinking-lite",
        "gemini-flash-lite",
    ]


def test_experimental_models_are_hidden_from_default_list_but_resolvable():
    default_available = get_available_models(has_cookie=True)
    all_available = get_all_models(has_cookie=True)

    assert "nano-banana-2" not in default_available
    assert "nano-banana-2" in all_available
    name, mode, think, err, extra, search = resolve_model("nano-banana-2")
    assert err is None
    assert name == "nano-banana-2"
    assert extra["web_feature"] == "image_generation"


def test_experimental_model_list_can_be_explicitly_exposed():
    available = get_available_models(has_cookie=True, expose_experimental=True)
    assert "nano-banana-2" in available
    assert "gemini-3.5-flash" in available


def test_resolve_google_model_name_prefix():
    name, mode, think, err, extra, search = resolve_model("models/gemini-3.5-flash")
    assert err is None
    assert name == "gemini-3.5-flash"
    assert mode == 1


def test_resolve_thinking_default():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-thinking")
    assert mode == 2
    assert think == 0  # deepest


def test_resolve_think_override():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-thinking-think=2")
    assert err is None
    assert mode == 2
    assert think == 2


def test_resolve_ui_thinking_level_suffixes():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-thinking-standard")
    assert err is None
    assert name == "gemini-3.5-flash"
    assert think == 4

    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-thinking-extended")
    assert err is None
    assert name == "gemini-3.5-flash"
    assert think == 0


def test_resolve_unknown_falls_back_silently():
    """Unknown models should fall back to default, not error (per code design)."""
    name, mode, think, err, extra, search = resolve_model("not-a-real-model")
    assert err is None
    assert name == "gemini-3.5-flash"


def test_resolve_invalid_think_errors():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-think=abc")
    assert err is not None
    assert "Invalid think level" in err


def test_pro_enhanced_has_extra_fields():
    """gemini-3.1-pro-enhanced has extra_fields dict."""
    name, mode, think, err, extra, search = resolve_model("gemini-3.1-pro-enhanced")
    assert err is None
    assert extra is not None
    assert isinstance(extra, dict)


def test_resolve_search_model():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-search")
    assert err is None
    assert search is True


def test_resolve_web_feature_model_aliases():
    name, mode, think, err, extra, search = resolve_model("nano-banana-2")
    assert err is None
    assert extra["web_feature"] == "image_generation"
    assert extra["web_model_name"] == "Nano Banana 2"
    assert extra[68] == 2
    assert extra[80] == 1

    name, mode, think, err, extra, search = resolve_model("omni")
    assert err is None
    assert extra["web_feature"] == "video_generation"

    name, mode, think, err, extra, search = resolve_model("lyria 3")
    assert err is None
    assert name == "lyria-3"
    assert extra["web_feature"] == "music"

    name, mode, think, err, extra, search = resolve_model("gemini-2.5-flash-preview-tts")
    assert err is None
    assert extra["web_feature"] == "text_to_speech"

    name, mode, think, err, extra, search = resolve_model("gemini-2.5-flash-image")
    assert err is None
    assert name == "gemini-2.5-flash-image"
    assert extra["web_model_name"] == "gemini-2.5-flash-image"


def test_resolve_web_feature_suffixes():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-image")
    assert err is None
    assert name == "gemini-3.5-flash"
    assert extra["web_feature"] == "image_generation"

    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-deep-research")
    assert err is None
    assert extra["web_feature"] == "deep_research"
    assert search is True

    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-tts")
    assert err is None
    assert name == "gemini-3.5-flash"
    assert extra["web_feature"] == "text_to_speech"

    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-photo")
    assert err is None
    assert extra["web_feature"] == "photos"


def test_resolve_web_feature_friendly_aliases():
    name, mode, think, err, extra, search = resolve_model("notebooklm")
    assert err is None
    assert name == "gemini-notebook"
    assert extra["web_feature"] == "notebook"

    name, mode, think, err, extra, search = resolve_model("google photos")
    assert err is None
    assert name == "gemini-photos"
    assert extra["web_feature"] == "photos"

    name, mode, think, err, extra, search = resolve_model("gemini-advanced")
    assert err is None
    assert mode == 3


def test_resolve_legacy_aliases_still_work():
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash-thinking@think=2")
    assert err is None
    assert think == 2
    name, mode, think, err, extra, search = resolve_model("gemini-3.5-flash@search")
    assert err is None
    assert search is True


def test_all_registered_models_resolvable():
    for model_name in MODELS:
        name, mode, think, err, extra, search = resolve_model(model_name)
        assert err is None, f"Failed to resolve {model_name}: {err}"
        assert mode in {1, 2, 3, 4, 5, 6}


def test_web_features_expose_hidden_ui_models():
    assert "Nano Banana 2" in WEB_FEATURES["image_generation"]["ui_models"]
    assert "Omni" in WEB_FEATURES["video_generation"]["ui_models"]
    assert "Lyria 3" in WEB_FEATURES["music"]["ui_models"]
    assert "gemini-2.5-flash-preview-tts" in WEB_FEATURES["text_to_speech"]["ui_models"]


def test_source_discovered_models_are_registered():
    registered = {name.lower() for name in MODELS}
    for item in SOURCE_DISCOVERED_WEB_MODELS:
        if item["registered"] and item["name"].startswith(("gemini-", "imagen-", "veo-")):
            assert item["name"].lower() in registered
