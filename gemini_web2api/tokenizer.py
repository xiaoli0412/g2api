"""Accurate token counting using tiktoken with fallback."""
import threading

_encoder = None
_lock = threading.Lock()
_initialized = False


def _get_encoder():
    global _encoder, _initialized
    if _initialized:
        return _encoder
    with _lock:
        if _initialized:
            return _encoder
        try:
            import tiktoken
            _encoder = tiktoken.get_encoding("o200k_base")
        except Exception:
            _encoder = None
        _initialized = True
        return _encoder


def count_tokens(text: str) -> int:
    if not text:
        return 0
    enc = _get_encoder()
    if enc:
        return len(enc.encode(text))
    return len(text) // 4


def count_messages_tokens(messages: list) -> int:
    if not messages:
        return 0
    enc = _get_encoder()
    total = 0
    for msg in messages:
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            if enc:
                total += len(enc.encode(content))
            else:
                total += len(content) // 4
        elif isinstance(content, list):
            for part in content:
                text = part.get("text", "") if isinstance(part, dict) else str(part)
                if enc:
                    total += len(enc.encode(text))
                else:
                    total += len(text) // 4
        if msg.get("name"):
            if enc:
                total += len(enc.encode(msg["name"]))
            else:
                total += len(msg["name"]) // 4
    return total
