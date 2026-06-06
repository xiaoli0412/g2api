"""Tests for gemini_web2api.config and __init__ re-exports."""
from gemini_web2api import __version__, CONFIG, MODELS, resolve_model, load_config, DEFAULT_CONFIG


def test_version_is_string():
    assert isinstance(__version__, str)
    parts = __version__.split(".")
    assert len(parts) >= 2
    for p in parts:
        assert p.isdigit()


def test_config_has_required_keys():
    for key in ("port", "host", "retry_attempts", "gemini_bl", "api_keys", "cookie_file"):
        assert key in CONFIG


def test_default_config_values():
    assert DEFAULT_CONFIG["port"] == 8081
    assert DEFAULT_CONFIG["host"] == "0.0.0.0"
    assert isinstance(DEFAULT_CONFIG["api_keys"], list)


def test_models_exported_from_package():
    """Bug regression: MODELS must be importable from the package root."""
    assert isinstance(MODELS, dict)
    assert "gemini-3.5-flash" in MODELS


def test_resolve_model_exported_from_package():
    assert callable(resolve_model)
    name, mode, think, err, extra = resolve_model("gemini-3.5-flash")
    assert err is None
    assert mode == 1
