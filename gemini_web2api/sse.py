"""Lightweight SSE Parser (HelloGML sse.ts pattern).

Zero-dependency SSE parser for streaming responses.
Handles: data, event, id, retry, comments.
"""


class SSEEvent:
    __slots__ = ("type", "data")

    def __init__(self, event_type="message", data=""):
        self.type = event_type
        self.data = data


class SSEParser:
    def __init__(self, on_event=None):
        self._on_event = on_event
        self._buffer = ""
        self._event_type = ""
        self._event_data = ""

    def feed(self, chunk):
        self._buffer += chunk
        lines = self._buffer.split("\n")
        self._buffer = lines.pop() or ""

        for line in lines:
            trimmed = line.rstrip("\r")

            if trimmed == "":
                self._dispatch()
            elif trimmed.startswith("data: "):
                self._event_data += (("\n" if self._event_data else "") + trimmed[6:])
            elif trimmed.startswith("event: "):
                self._event_type = trimmed[7:]
            elif trimmed.startswith("id: "):
                pass
            elif trimmed.startswith("retry: "):
                pass
            elif trimmed.startswith(":"):
                pass

    def _dispatch(self):
        if self._event_data or self._event_type:
            event = SSEEvent(self._event_type or "message", self._event_data)
            if self._on_event:
                self._on_event(event)
            self._event_type = ""
            self._event_data = ""

    def reset(self):
        self._buffer = ""
        self._event_type = ""
        self._event_data = ""


def parse_sse_stream(readable_stream, on_event):
    parser = SSEParser(on_event)
    decoder_error = "replace"

    try:
        for chunk in readable_stream.iter_text():
            parser.feed(chunk)
    except AttributeError:
        try:
            for chunk in readable_stream:
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors=decoder_error)
                parser.feed(chunk)
        except TypeError:
            pass


def create_sse_event(data, event_type=None, event_id=None):
    lines = []
    if event_type:
        lines.append(f"event: {event_type}")
    if event_id:
        lines.append(f"id: {event_id}")
    if isinstance(data, dict):
        import json
        data = json.dumps(data, ensure_ascii=False)
    lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)
