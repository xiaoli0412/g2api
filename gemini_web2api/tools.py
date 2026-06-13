"""Tool calling and multimodal message parsing.

Enhanced with patterns from HelloGML (GLM-Free-API):
- Few-shot tool prompt injection for better model compliance
- 3-layer fallback tool call parsing
- Balanced bracket JSON extraction with nested object support
- Streaming tool call buffer to prevent JSON leakage
- tool_choice constraint support
"""
import json
import re
import uuid
import base64
import io
import os

MAX_IMAGE_B64_SIZE = 50000

MIME_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
    ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".csv": "text/csv", ".json": "application/json",
    ".xml": "application/xml", ".md": "text/markdown",
    ".py": "text/x-python", ".js": "text/javascript", ".html": "text/html",
}


def _mime_from_filename(filename: str, default: str = "application/octet-stream") -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return MIME_TYPES.get(ext, default)


def _decode_data_url(value: str, fallback_mime: str = "application/octet-stream"):
    header, b64data = value.split(",", 1)
    mime = fallback_mime
    if header.startswith("data:") and ";" in header:
        mime = header.split(":", 1)[1].split(";", 1)[0] or fallback_mime
    return base64.b64decode(b64data), mime


def _append_url_or_data_attachment(images, text_parts, value, *, label="File", mime=None, filename=""):
    if not value or not isinstance(value, str):
        text_parts.append(f"[{label} missing]")
        return
    try:
        if value.startswith("data:"):
            file_bytes, detected_mime = _decode_data_url(value, mime or _mime_from_filename(filename))
            images.append((file_bytes, detected_mime, filename or "upload"))
            text_parts.append(f"[{label} attached: {filename or detected_mime}]")
        elif value.startswith(("http://", "https://")):
            images.append((value, mime, filename or "upload"))
            text_parts.append(f"[{label} URL attached: {filename or value}]")
        else:
            # Responses API input_file.file_data is sometimes raw base64 without a data URL prefix.
            file_bytes = base64.b64decode(value)
            detected_mime = mime or _mime_from_filename(filename)
            images.append((file_bytes, detected_mime, filename or "upload"))
            text_parts.append(f"[{label} attached: {filename or detected_mime}]")
    except Exception:
        text_parts.append(f"[{label} data parse error]")


def _compress_b64_if_needed(b64):
    if len(b64) <= MAX_IMAGE_B64_SIZE:
        return b64
    try:
        from PIL import Image
        img_data = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_data))
        max_dim = 256
        ratio = min(max_dim / img.width, max_dim / img.height)
        if ratio < 1:
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return b64[:MAX_IMAGE_B64_SIZE]


def _build_tool_choice_instruction(tool_choice, tool_defs):
    if tool_choice == "none":
        return "\n\nIMPORTANT: Do NOT call any tools. Respond with text only."
    if tool_choice == "required":
        return "\n\nIMPORTANT: You MUST request at least one tool_call. Do not respond with text only."
    if isinstance(tool_choice, dict):
        fn_name = tool_choice.get("function", {}).get("name", "")
        if fn_name:
            return f'\n\nIMPORTANT: You MUST request the tool "{fn_name}". Do not call other tools.'
    return ""


def _build_tool_prompt_with_examples(tool_defs, constraint=""):
    tools_desc = "\n\n".join(
        f"### {td['name']}\nDescription: {td.get('description', '')}\n"
        f"Parameters: {json.dumps(td.get('parameters', {}), indent=2)}"
        for td in tool_defs
    )
    example_name = tool_defs[0]["name"] if tool_defs else "example_tool"
    example_params = "{}"
    if tool_defs and tool_defs[0].get("parameters"):
        props = tool_defs[0]["parameters"].get("properties", {})
        if props:
            first_key = next(iter(props))
            example_params = json.dumps({first_key: f"<{first_key}_value>"})

    return (
        "# Tool Use\n\n"
        "You are connected to a local tool bridge. The client can execute the listed tools "
        "on behalf of the user, including local filesystem, shell, browser, and project "
        "inspection tools when such tools are provided.\n"
        "If the user asks for local files, folders, command output, screenshots, browser "
        "state, or other external data, request a tool call instead of saying you cannot "
        "access the user's computer.\n\n"
        "TOOL CALL FORMAT:\n"
        "If a tool is needed, output ONLY one or more fenced tool_call blocks, with no "
        "explanations before or after them:\n"
        '```tool_call\n{"name": "TOOL_NAME", "arguments": {"param": "value"}}\n```\n\n'
        "Rules:\n"
        "1. Use only tools listed below.\n"
        "2. Do not use ```json or any other fence type for tool calls.\n"
        "3. If no tool is needed, answer normally in plain text.\n"
        "4. After a [Tool result ...] message, use that result to answer the user.\n\n"
        f"Available tools:\n{tools_desc}\n\n"
        "Examples:\n"
        "User: Inspect a local project directory\n"
        f'Assistant: ```tool_call\n{{"name": "{example_name}", "arguments": {example_params}}}\n```\n\n'
        "User: Hello\n"
        "Assistant: Hello! How can I help you today?"
        f"{constraint}"
    )


def messages_to_prompt(messages, tools=None, tool_choice=None):
    instruction_parts = []
    conversation_parts = []
    images = []
    tool_prompt = ""

    if tools and tool_choice != "none":
        tool_defs = []
        for tool in tools:
            fn = tool.get("function", tool) if tool.get("type") == "function" else tool
            tool_defs.append({
                "name": fn.get("name", tool.get("name", "")),
                "description": fn.get("description", tool.get("description", "")),
                "parameters": fn.get("parameters", tool.get("parameters", {})),
            })
        if tool_defs:
            constraint = _build_tool_choice_instruction(tool_choice, tool_defs)
            tool_prompt = _build_tool_prompt_with_examples(tool_defs, constraint)
    elif tools and tool_choice == "none":
        tool_prompt = _build_tool_choice_instruction("none", [])

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            text_parts = []
            for c in content:
                if c.get("type") in ("text", "input_text"):
                    text_parts.append(c.get("text", ""))
                elif c.get("type") in ("image_url", "input_image"):
                    url_data = c.get("image_url", {})
                    if not url_data:
                        url_data = c.get("url", "")
                    url = url_data.get("url", "") if isinstance(url_data, dict) else str(url_data)
                    _append_url_or_data_attachment(
                        images, text_parts, url, label="Image",
                        mime=(url_data.get("mime_type") if isinstance(url_data, dict) else None) or c.get("mime_type"),
                        filename=c.get("filename", "image"),
                    )
                elif c.get("type") == "image":
                    if c.get("source"):
                        src = c["source"]
                        if src.get("type") == "base64":
                            try:
                                img_bytes = base64.b64decode(src["data"])
                                mime = src.get("media_type", "image/png")
                                images.append((img_bytes, mime, c.get("filename", "image")))
                                text_parts.append("[Image attached]")
                            except Exception:
                                text_parts.append("[Image data parse error]")
                    elif c.get("image_url"):
                        _append_url_or_data_attachment(
                            images, text_parts, c["image_url"], label="Image",
                            filename=c.get("filename", "image"),
                        )
                elif c.get("type") in ("file_url", "video_url", "audio_url"):
                    url_data = c.get("url", c.get(f"{c['type'].replace('_url', '')}_url", ""))
                    if isinstance(url_data, dict):
                        url_data = url_data.get("url", "")
                    if url_data and isinstance(url_data, str):
                        kind = c["type"].replace("_url", "").title()
                        _append_url_or_data_attachment(
                            images, text_parts, url_data, label=kind,
                            mime=c.get("mime_type"), filename=c.get("filename", kind.lower()),
                        )
                elif c.get("type") in ("input_file", "file"):
                    file_obj = c.get("file", {}) if isinstance(c.get("file"), dict) else {}
                    filename = c.get("filename") or file_obj.get("filename") or c.get("name") or "file"
                    mime = c.get("mime_type") or file_obj.get("mime_type") or _mime_from_filename(filename)
                    value = (
                        c.get("file_data")
                        or c.get("data")
                        or c.get("url")
                        or c.get("file_url")
                        or file_obj.get("file_data")
                        or file_obj.get("data")
                        or file_obj.get("url")
                    )
                    if value:
                        _append_url_or_data_attachment(
                            images, text_parts, value, label="File", mime=mime, filename=filename,
                        )
                    elif c.get("file_id") or file_obj.get("file_id"):
                        text_parts.append(f"[File reference not fetchable by this proxy: {filename}]")
                    else:
                        text_parts.append("[File data missing]")
                elif c.get("type") == "input_audio":
                    audio = c.get("audio", {})
                    if audio.get("data"):
                        try:
                            fmt = audio.get("format", "wav")
                            mime = f"audio/{fmt}"
                            audio_bytes = base64.b64decode(audio["data"])
                            images.append((audio_bytes, mime, c.get("filename", f"audio.{fmt}")))
                            text_parts.append("[Audio attached]")
                        except Exception:
                            text_parts.append("[Audio data parse error]")
            content = " ".join(text_parts)

        if role == "system":
            instruction_parts.append(f"[System instruction]: {content}")
        elif role == "developer":
            instruction_parts.append(f"[Developer instruction]: {content}")
        elif role == "assistant":
            if msg.get("tool_calls"):
                tc_strs = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    tc_strs.append(
                        f'```tool_call\n{{"name": "{fn.get("name")}", '
                        f'"arguments": {fn.get("arguments", "{}")}}}\n```'
                    )
                conversation_parts.append(f"[Assistant]: {content or ''}\n" + "\n".join(tc_strs))
            else:
                conversation_parts.append(f"[Assistant]: {content}")
        elif role == "tool":
            conversation_parts.append(
                f"[Tool result for {msg.get('name', '')} (callID: {msg.get('tool_call_id', '')})]: {content}"
            )
        else:
            conversation_parts.append(content if content else "")

    parts = []
    parts.extend(instruction_parts)
    if tool_prompt:
        parts.append(tool_prompt)
    parts.extend(conversation_parts)
    prompt = "\n\n".join(p for p in parts if p)
    return prompt, images


def _scan_balanced_json(text, target_key=None):
    results = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        start = i
        j = i
        closed = False
        while j < len(text):
            c = text[j]
            if in_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        raw = text[start:j + 1]
                        if target_key is None or f'"{target_key}"' in raw:
                            results.append((start, j + 1, raw))
                        i = j + 1
                        closed = True
                        break
            j += 1
        if not closed:
            break
    return results


def _extract_json_object_at_key(text, key):
    idx = text.find(f'"{key}"')
    if idx == -1:
        return None
    start = idx
    while start > 0 and text[start] != "{":
        start -= 1
    if text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _coerce_tool_call(obj):
    if not isinstance(obj, dict):
        return None
    name = obj.get("name") or obj.get("tool") or obj.get("function")
    if not name or not isinstance(name, str):
        return None
    if "arguments" not in obj and "args" not in obj and "parameters" not in obj:
        return None
    raw_args = obj.get("arguments") or obj.get("args") or obj.get("parameters") or {}
    args_str = json.dumps(raw_args, ensure_ascii=False) if isinstance(raw_args, dict) else str(raw_args)
    call_id = obj.get("id") or f"call_{uuid.uuid4().hex[:8]}"
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args_str},
    }


def _try_fix_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fixed = text
    fixed = re.sub(r"'([^']*)'", r'"\1"', fixed)
    fixed = re.sub(r"(?<=[{,\s])(\w+)\s*:", r'"\1":', fixed)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


def parse_tool_calls(text):
    if not text:
        return "", []

    tool_calls = []
    collected = []

    pattern1 = r"```tool_call\s*\n(.*?)\n```"
    for m in re.finditer(pattern1, text, re.DOTALL):
        raw = m.group(1).strip()
        data = _try_fix_json(raw)
        if data:
            calls = []
            items = data if isinstance(data, list) else [data]
            for item in items:
                tc = _coerce_tool_call(item)
                if tc:
                    calls.append(tc)
            if calls:
                collected.append((m.start(), m.end(), calls))

    if not collected:
        pattern2 = r'```(?:json|function_call)?\s*\n(\{[\s\S]*?"name"[\s\S]*?"(?:arguments|args)"[\s\S]*?\})\s*```'
        for m in re.finditer(pattern2, text, re.DOTALL):
            raw = m.group(1).strip()
            data = _try_fix_json(raw)
            if data:
                calls = []
                items = data if isinstance(data, list) else [data]
                for item in items:
                    tc = _coerce_tool_call(item)
                    if tc:
                        calls.append(tc)
                if calls:
                    collected.append((m.start(), m.end(), calls))

    if not collected:
        tool_calls_obj = _extract_json_object_at_key(text, "tool_calls")
        if tool_calls_obj:
            data = _try_fix_json(tool_calls_obj)
            if data and isinstance(data, dict) and "tool_calls" in data:
                calls = []
                items = data["tool_calls"] if isinstance(data["tool_calls"], list) else []
                for item in items:
                    tc = _coerce_tool_call(item)
                    if tc:
                        calls.append(tc)
                if calls:
                    start = text.find(tool_calls_obj)
                    collected.append((start, start + len(tool_calls_obj), calls))

    if not collected:
        for start, end, raw in _scan_balanced_json(text, "name"):
            data = _try_fix_json(raw)
            if data:
                calls = []
                items = data if isinstance(data, list) else [data]
                for item in items:
                    tc = _coerce_tool_call(item)
                    if tc:
                        calls.append(tc)
                if calls:
                    collected.append((start, end, calls))

    if not collected:
        return text, []

    collected.sort(key=lambda x: x[0])
    for _, _, calls in collected:
        tool_calls.extend(calls)

    for i, tc in enumerate(tool_calls):
        tc["index"] = i

    residual = []
    prev = 0
    for start, end, _ in collected:
        residual.append(text[prev:start])
        prev = end
    residual.append(text[prev:])
    clean = "".join(residual).strip()

    return clean, tool_calls


class StreamToolCallBuffer:
    def __init__(self, threshold=30):
        self.threshold = threshold
        self.buffer = ""
        self.is_tool_call_mode = False
        self.might_be_tool_call = False

    def feed(self, chunk):
        if self.is_tool_call_mode:
            self.buffer += chunk
            return "", None

        if not self.might_be_tool_call:
            combined = self.buffer + chunk
            stripped = combined.lstrip()
            if stripped.startswith("{") or stripped.startswith("```tool_call"):
                self.might_be_tool_call = True
                self.buffer = combined
                if len(stripped) >= self.threshold:
                    return self._decide()
                return "", None
            else:
                self.buffer = ""
                return chunk, None
        else:
            self.buffer += chunk
            stripped = self.buffer.lstrip()
            if len(stripped) >= self.threshold:
                return self._decide()
            return "", None

    def _decide(self):
        stripped = self.buffer.lstrip()
        is_tc = (
            '"tool_calls"' in stripped
            or "'tool_calls'" in stripped
            or "tool_calls" in stripped
            or '"tool_call"' in stripped
            or "```tool_call" in stripped
        )
        if is_tc:
            self.is_tool_call_mode = True
            self.buffer = ""
            return "", None
        else:
            self.might_be_tool_call = False
            content = self.buffer
            self.buffer = ""
            return content, None

    def finalize(self, full_content, tools=None):
        if tools and self.is_tool_call_mode:
            return parse_tool_calls(full_content)
        if tools and not self.is_tool_call_mode:
            clean, tc = parse_tool_calls(full_content)
            if tc:
                return clean, tc
        return full_content, None

    def reset(self):
        self.buffer = ""
        self.is_tool_call_mode = False
        self.might_be_tool_call = False


def build_tool_prompt(tool_defs):
    tool_spec = json.dumps(tool_defs, indent=2, ensure_ascii=False)
    return (
        "# Tool Use\n\n"
        "You are connected to a local tool bridge. The following tools can execute on "
        "behalf of the user. When local files, shell output, browser state, or external "
        "data are needed, request a tool call instead of saying you cannot access them.\n\n"
        "Call format (use this exact format):\n"
        "```function_call\n"
        '{"name": "<tool_name>", "args": {<arguments>}}\n'
        "```\n\n"
        "When calling tools:\n"
        "- Output ONLY the function_call block(s), nothing else\n"
        "- You may call multiple tools with multiple blocks\n"
        "- After receiving a [Tool result for ...], use that data to answer the user\n\n"
        f"Available tools:\n{tool_spec}"
    )


def _google_tool_choice_instruction(req):
    tool_config = req.get("toolConfig", {})
    fc_config = tool_config.get("functionCallingConfig", {})
    mode = fc_config.get("mode", "AUTO")
    allowed = fc_config.get("allowedFunctionNames", [])
    if mode == "NONE":
        return "\n\nIMPORTANT: Do NOT call any tools. Respond with text only."
    if mode == "ANY":
        if allowed:
            names = ", ".join(f'"{n}"' for n in allowed)
            return f"\n\nIMPORTANT: You MUST call one of these tools: {names}. Do not respond with text only."
        return "\n\nIMPORTANT: You MUST call at least one tool. Do not respond with text only."
    return ""


def google_contents_to_prompt(req):
    parts = []
    images = []
    tool_config = req.get("toolConfig", {})
    fc_mode = tool_config.get("functionCallingConfig", {}).get("mode", "AUTO")
    tools = req.get("tools")
    tool_defs = []
    if tools and fc_mode != "NONE":
        for tool_group in tools:
            for fn in tool_group.get("functionDeclarations", []):
                td = {"name": fn.get("name", ""), "description": fn.get("description", "")}
                params = fn.get("parameters") or fn.get("parametersJsonSchema")
                if params:
                    td["parameters"] = params
                tool_defs.append(td)

    sys_inst = req.get("systemInstruction")
    if sys_inst:
        sys_parts = sys_inst.get("parts", [])
        sys_text = " ".join(p.get("text", "") for p in sys_parts if p.get("text"))
        if sys_text:
            if tool_defs:
                constraint = _google_tool_choice_instruction(req)
                parts.append(sys_text + "\n\n" + build_tool_prompt(tool_defs) + constraint)
            else:
                parts.append(sys_text)
    elif tool_defs:
        constraint = _google_tool_choice_instruction(req)
        parts.append(build_tool_prompt(tool_defs) + constraint)

    for content in req.get("contents", []):
        role = content.get("role", "user")
        msg_parts = []
        for p in content.get("parts", []):
            if p.get("text"):
                msg_parts.append(p["text"])
            elif p.get("inlineData"):
                data = p["inlineData"]
                mime = data.get("mimeType", "image/png")
                images.append((base64.b64decode(data["data"]), mime))
            elif p.get("functionCall"):
                fc = p["functionCall"]
                msg_parts.append(
                    f'```function_call\n{json.dumps({"name": fc["name"], "args": fc.get("args", {})}, ensure_ascii=False)}\n```'
                )
            elif p.get("functionResponse"):
                fr = p["functionResponse"]
                msg_parts.append(
                    f'[Tool result for {fr.get("name", "")}]: {json.dumps(fr.get("response", {}), ensure_ascii=False)}'
                )
        text = "\n".join(msg_parts)
        if role == "model":
            parts.append(f"[Assistant]: {text}")
        else:
            parts.append(text)

    return "\n\n".join(p for p in parts if p), images


def parse_google_function_calls(text):
    if not text:
        return "", []

    function_calls = []
    collected = []

    pattern1 = r"```function_call\s*\n(.*?)\n```"
    for m in re.finditer(pattern1, text, re.DOTALL):
        raw = m.group(1).strip()
        data = _try_fix_json(raw)
        if data and "name" in data:
            collected.append((m.start(), m.end(), [{
                "name": data["name"],
                "args": data.get("args", data.get("arguments", {})),
            }]))

    if not collected:
        pattern2 = r'(?:```(?:json)?\s*\n|(?<=\n))(\{[\s\S]*?"name"[\s\S]*?"args"[\s\S]*?\})\s*(?:```|$)'
        for m in re.finditer(pattern2, text, re.DOTALL):
            raw = m.group(1).strip()
            data = _try_fix_json(raw)
            if data and "name" in data:
                collected.append((m.start(), m.end(), [{
                    "name": data["name"],
                    "args": data.get("args", data.get("arguments", {})),
                }]))

    if not collected:
        for start, end, raw in _scan_balanced_json(text, "name"):
            data = _try_fix_json(raw)
            if data and isinstance(data, dict) and "name" in data and ("args" in data or "arguments" in data):
                collected.append((start, end, [{
                    "name": data["name"],
                    "args": data.get("args", data.get("arguments", {})),
                }]))

    if not collected:
        return text, []

    collected.sort(key=lambda x: x[0])
    for _, _, calls in collected:
        function_calls.extend(calls)

    residual = []
    prev = 0
    for start, end, _ in collected:
        residual.append(text[prev:start])
        prev = end
    residual.append(text[prev:])
    clean = "".join(residual).strip()

    return clean, function_calls
