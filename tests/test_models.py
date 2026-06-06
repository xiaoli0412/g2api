"""Tests for gemini_web2api.models."""
from gemini_web2api.models import resolve_model, MODELS


def test_resolve_known_model():
    name, mode, think, err, extra = resolve_model("gemini-3.5-flash")
    assert err is None
    assert mode == 1
    assert think == 4


def test_resolve_thinking_default():
    name, mode, think, err, extra = resolve_model("gemini-3.5-flash-thinking")
    assert mode == 2
    assert think == 0  # deepest


def test_resolve_think_override():
    name, mode, think, err, extra = resolve_model("gemini-3.5-flash-thinking@think=2")
    assert err is None
    assert mode == 2
    assert think == 2


def test_resolve_unknown_falls_back_silently():
    """Unknown models should fall back to default, not error (per code design)."""
    name, mode, think, err, extra = resolve_model("not-a-real-model")
    assert err is None
    assert name == "gemini-3.5-flash"


def test_resolve_invalid_think_errors():
    name, mode, think, err, extra = resolve_model("gemini-3.5-flash@think=abc")
    assert err is not None
    assert "Invalid think level" in err


def test_pro_enhanced_has_extra_fields():
    """gemini-3.1-pro-enhanced has extra_fields dict."""
    name, mode, think, err, extra = resolve_model("gemini-3.1-pro-enhanced")
    assert err is None
    assert extra is not None
    assert isinstance(extra, dict)


def test_all_registered_models_resolvable():
    for model_name in MODELS:
        name, mode, think, err, extra = resolve_model(model_name)
        assert err is None, f"Failed to resolve {model_name}: {err}"
        assert mode in {1, 2, 3, 4, 5, 6}
