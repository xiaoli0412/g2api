"""Multi-Protocol Adapters (Claude/Gemini format conversion).

Inspired by HelloGML adapters.ts pattern:
- Claude /v1/messages protocol support
- Bidirectional message/tool format conversion
- Stream adapter for Claude SSE events
"""
import json
import uuid


def convert_claude_messages_to_openai(messages, system=None):
    openai_msgs = []
    if system:
        if isinstance(system, list):
            sys_text = " ".join(item.get("text", "") for item in system if item.get("type") == "text")
        else:
            sys_text = str(system)
        if sys_text:
            openai_msgs.append({"role": "system", "content": sys_text})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            texts = []
            image_items = []
            for item in content:
                if item.get("type") == "text":
                    texts.append({"type": "text", "text": item.get("text", "")})
                elif item.get("type") == "tool_result":
                    tool_content = item.get("content", "")
                    if not isinstance(tool_content, str):
                        tool_content = json.dumps(tool_content, ensure_ascii=False)
                    texts.append({"type": "text", "text": f"Tool result (ID: {item.get('tool_use_id', '')}):\n{tool_content}"})
                elif item.get("type") == "tool_use":
                    texts.append({"type": "text", "text":
                        f'```tool_call\n{{"name": "{item.get("name", "")}", '
                        f'"arguments": {json.dumps(item.get("input", {}), ensure_ascii=False)}}}\n```'})
                elif item.get("type") == "image":
                    src = item.get("source", {})
                    if src.get("type") == "base64":
                        mime = src.get("media_type", "image/png")
                        b64data = src.get("data", "")
                        image_items.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64data}"},
                        })
                    elif src.get("type") == "url":
                        image_items.append({
                            "type": "image_url",
                            "image_url": {"url": src.get("url", "")},
                        })
            # Keep as list if images present, otherwise flatten to string
            if image_items:
                content = image_items + texts
            else:
                content = " ".join(t.get("text", "") for t in texts)

        if role == "assistant":
            openai_msg = {"role": "assistant", "content": content or None}
            if msg.get("tool_calls"):
                openai_msg["tool_calls"] = msg["tool_calls"]
            openai_msgs.append(openai_msg)
        elif role == "user":
            openai_msgs.append({"role": "user", "content": content})
        else:
            openai_msgs.append({"role": role, "content": content})

    return openai_msgs


def convert_claude_tools_to_openai(tools):
    if not tools:
        return None
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", tool.get("parameters", {})),
            }
        })
    return openai_tools


def convert_openai_response_to_claude(openai_resp):
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = []

    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})

    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": fn.get("name", ""),
                "input": args,
            })

    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = "end_turn"
    if finish_reason == "tool_calls":
        stop_reason = "tool_use"
    elif finish_reason == "length":
        stop_reason = "max_tokens"

    usage = openai_resp.get("usage", {})

    return {
        "id": openai_resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": openai_resp.get("model", "gemini"),
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


def create_claude_stream_events(openai_stream_chunks):
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    content_block_index = 0
    text_started = False
    tool_blocks = []
    total_input = 0
    total_output = 0

    yield {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": "gemini",
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": total_input, "output_tokens": total_output},
        },
    }

    for chunk in openai_stream_chunks:
        if not isinstance(chunk, dict):
            continue

        choice = chunk.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        if delta.get("content"):
            if not text_started:
                text_started = True
                yield {
                    "type": "content_block_start",
                    "index": content_block_index,
                    "content_block": {"type": "text", "text": ""},
                }

            yield {
                "type": "content_block_delta",
                "index": content_block_index,
                "delta": {"type": "text_delta", "text": delta["content"]},
            }

        if delta.get("tool_calls"):
            for tc in delta["tool_calls"]:
                fn = tc.get("function", {})
                tool_idx = content_block_index + (1 if text_started else 0)
                tool_blocks.append(tool_idx)

                yield {
                    "type": "content_block_start",
                    "index": tool_idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                        "name": fn.get("name", ""),
                        "input": {},
                    },
                }

                args = fn.get("arguments", "")
                if args:
                    yield {
                        "type": "content_block_delta",
                        "index": tool_idx,
                        "delta": {"type": "input_json_delta", "partial_json": args},
                    }

                yield {
                    "type": "content_block_stop",
                    "index": tool_idx,
                }

        if finish_reason:
            if text_started:
                yield {"type": "content_block_stop", "index": content_block_index}

            stop_reason = "end_turn"
            if finish_reason == "tool_calls":
                stop_reason = "tool_use"
            elif finish_reason == "length":
                stop_reason = "max_tokens"

            usage = chunk.get("usage", {})
            total_input = usage.get("prompt_tokens", total_input)
            total_output = usage.get("completion_tokens", total_output)

            yield {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": total_output},
            }
            yield {"type": "message_stop"}
            return

    if text_started:
        yield {"type": "content_block_stop", "index": content_block_index}

    yield {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": total_output},
    }
    yield {"type": "message_stop"}


def parse_claude_request(body):
    model = body.get("model", "gemini-3.5-flash")
    messages = body.get("messages", [])
    system = body.get("system")
    stream = body.get("stream", False)
    max_tokens = body.get("max_tokens", 4096)
    tools = body.get("tools")
    tool_choice = body.get("tool_choice", "auto")
    temperature = body.get("temperature")
    top_p = body.get("top_p")

    openai_messages = convert_claude_messages_to_openai(messages, system)
    openai_tools = convert_claude_tools_to_openai(tools)

    openai_body = {
        "model": model,
        "messages": openai_messages,
        "stream": stream,
        "max_tokens": max_tokens,
    }
    if openai_tools:
        openai_body["tools"] = openai_tools
        openai_body["tool_choice"] = tool_choice
    if temperature is not None:
        openai_body["temperature"] = temperature
    if top_p is not None:
        openai_body["top_p"] = top_p

    return openai_body
