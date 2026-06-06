"""Tests for gemini_web2api.tools (message/prompt conversion and tool-call parsing)."""
import json
import base64

import pytest

from gemini_web2api.tools import (
    messages_to_prompt,
    parse_tool_calls,
    google_contents_to_prompt,
    parse_google_function_calls,
    build_tool_prompt,
)


def test_messages_to_prompt_basic():
    prompt, images = messages_to_prompt([{"role": "user", "content": "hello"}])
    assert images == []
    assert "hello" in prompt


def test_messages_to_prompt_no_tools():
    """No tools => no tool block in prompt."""
    prompt, _ = messages_to_prompt([{"role": "user", "content": "hi"}])
    assert "Available tools" not in prompt
    assert "tool_call" not in prompt


def test_messages_to_prompt_tool_choice_none_emits_warning():
    """Bug regression: tool_choice='none' must emit a no-tools instruction."""
    prompt, _ = messages_to_prompt(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "f", "description": "d", "parameters": {}}}],
        tool_choice="none",
    )
    assert "Do NOT" in prompt
    assert "tool_call" in prompt or "tools" in prompt.lower()


def test_messages_to_prompt_tool_choice_required():
    prompt, _ = messages_to_prompt(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "f", "description": "", "parameters": {}}}],
        tool_choice="required",
    )
    assert "MUST call at least one tool" in prompt


def test_messages_to_prompt_tool_choice_specific_function():
    prompt, _ = messages_to_prompt(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "foo", "description": "", "parameters": {}}}],
        tool_choice={"type": "function", "function": {"name": "foo"}},
    )
    assert "MUST call the tool" in prompt
    assert "foo" in prompt


def test_messages_to_prompt_image_replaced_with_notice():
    """images are explicitly NOT supported in OpenAI-style messages."""
    prompt, _ = messages_to_prompt([
        {"role": "user", "content": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ]}
    ])
    assert "describe" in prompt
    assert "Image input not supported" in prompt


def test_parse_tool_calls_basic():
    text, tcs = parse_tool_calls('Hello\n```tool_call\n{"name":"f","arguments":{"x":1}}\n```\nbye')
    assert tcs and tcs[0]["function"]["name"] == "f"
    # json.dumps with default separators adds a space after `:`. Accept either form.
    args = tcs[0]["function"]["arguments"]
    assert args in ('{"x":1}', '{"x": 1}')
    assert "Hello" in text and "bye" in text
    assert "```tool_call" not in text


def test_parse_tool_calls_multiple():
    text, tcs = parse_tool_calls(
        'a```tool_call\n{"name":"f1","arguments":{}}\n```b```tool_call\n{"name":"f2","arguments":{"k":2}}\n```c'
    )
    assert len(tcs) == 2
    assert {tc["function"]["name"] for tc in tcs} == {"f1", "f2"}


def test_parse_tool_calls_malformed_is_skipped():
    """Malformed tool_call blocks are silently dropped, not crashed."""
    text, tcs = parse_tool_calls('```tool_call\nINVALID JSON\n```after')
    assert tcs == []
    assert "after" in text


def test_google_contents_basic():
    req = {
        "contents": [
            {"role": "user", "parts": [{"text": "hi"}]},
            {"role": "model", "parts": [{"text": "hello"}]},
        ],
        "systemInstruction": {"parts": [{"text": "be nice"}]},
    }
    prompt, imgs = google_contents_to_prompt(req)
    assert "be nice" in prompt
    assert "[Assistant]:" in prompt
    assert "hi" in prompt
    assert imgs == []


def test_google_contents_inline_image_extracted():
    req = {
        "contents": [
            {"role": "user", "parts": [
                {"text": "what is this?"},
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"fake").decode()}},
            ]},
        ]
    }
    prompt, imgs = google_contents_to_prompt(req)
    assert imgs and imgs[0][0] == b"fake"
    assert imgs[0][1] == "image/png"


def test_google_contents_function_call_round_trip():
    req = {
        "contents": [
            {"role": "user", "parts": [{"text": "call a tool"}]},
            {"role": "model", "parts": [
                {"functionCall": {"name": "f", "args": {"x": 1}}}
            ]},
            {"role": "user", "parts": [
                {"functionResponse": {"name": "f", "response": {"ok": True}}}
            ]},
        ]
    }
    prompt, imgs = google_contents_to_prompt(req)
    assert imgs == []
    assert "function_call" in prompt
    assert "Tool result for f" in prompt


def test_parse_google_function_calls_standard():
    text, fcs = parse_google_function_calls('text\n```function_call\n{"name":"f","args":{"a":1}}\n```\n')
    assert fcs and fcs[0]["name"] == "f"
    assert fcs[0]["args"] == {"a": 1}


def test_parse_google_function_calls_raw_json():
    text, fcs = parse_google_function_calls('{"name":"f","args":{"a":1}}')
    assert fcs and fcs[0]["name"] == "f"


def test_build_tool_prompt_includes_definitions():
    tool_defs = [{"name": "f", "description": "d", "parameters": {}}]
    p = build_tool_prompt(tool_defs)
    assert "Available tools" in p
    assert '"name": "f"' in p
