"""Tests for sanitized Gemini Web asset probe helpers."""
from gemini_web2api.web_probe import _extract_model_like_names, _extract_rpc_like_ids, _keyword_hits, _script_urls


def test_script_urls_are_resolved_and_deduplicated():
    html = '<script src="/a.js"></script><script src="https://x.test/b.js"></script><script src="/a.js"></script>'
    assert _script_urls(html, "https://gemini.google.com/u/1/app") == [
        "https://gemini.google.com/a.js",
        "https://x.test/b.js",
    ]


def test_keyword_hits_detects_web_features():
    hits = _keyword_hits("Create image with Imagen, Canvas, Deep research, StreamGenerate")
    assert "Create image" in hits
    assert "Canvas" in hits
    assert "Deep research" in hits
    assert "StreamGenerate" in hits


def test_extract_rpc_like_ids_is_bounded():
    ids = _extract_rpc_like_ids('rpcids:"ESY5D"; wrb.fr","L5adhe"; "Promise",function', limit=1)
    assert len(ids) == 1
    assert "Promise" not in ids


def test_extract_model_like_names_finds_hidden_web_models():
    text = (
        "Nano Banana 2 Omni Lyria 3 gemini-2.5-flash-image "
        "imagen-4.0-generate-001 veo-2.0-generate-001 gemini-u-top-priority-bg"
    )
    names = _extract_model_like_names(text)
    assert "Nano Banana 2" in names
    assert "Omni" in names
    assert "Lyria 3" in names
    assert "gemini-2.5-flash-image" in names
    assert "imagen-4.0-generate-001" in names
    assert "veo-2.0-generate-001" in names
    assert "gemini-u-top-priority-bg" not in names
