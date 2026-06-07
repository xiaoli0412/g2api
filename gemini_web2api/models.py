"""Model definitions and mapping from Gemini frontend JS source."""

# MODE_CATEGORY enum from 028-6eb337387583.js:
#   1=FAST, 2=THINKING, 3=PRO, 4=AUTO, 5=FAST_DYNAMIC_THINKING, 6=FLASH_LITE

MODELS = {
    "gemini-3.5-flash": {
        "mode": 1, "think": 4,
        "desc": "Fast general-purpose model",
    },
    "gemini-3.5-flash-thinking": {
        "mode": 2, "think": 0,
        "desc": "Deep thinking mode, longest output (~20k chars)",
    },
    "gemini-3.5-flash-thinking-lite": {
        "mode": 5, "think": 0,
        "desc": "Dynamic thinking with adaptive depth",
    },
    "gemini-3.1-pro": {
        "mode": 3, "think": 4,
        "desc": "Pro model (requires cookie for real routing)",
    },
    "gemini-3.1-pro-enhanced": {
        "mode": 3, "think": 4, "extra": {31: 2, 80: 3},
        "desc": "Pro with enhanced output (experimental)",
    },
    "gemini-auto": {
        "mode": 4, "think": 4,
        "desc": "Auto model selection",
    },
    "gemini-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Lightweight fast model",
    },
    # Search models (with web search enabled)
    "gemini-3.5-flash-search": {
        "mode": 1, "think": 4, "search": True,
        "desc": "Flash with web search",
    },
    "gemini-3.5-flash-thinking-search": {
        "mode": 2, "think": 0, "search": True,
        "desc": "Thinking with web search",
    },
    "gemini-3.1-pro-search": {
        "mode": 3, "think": 4, "search": True,
        "desc": "Pro with web search",
    },
}


def resolve_model(model_name: str, default: str = "gemini-3.5-flash"):
    """Resolve model name to (name, mode_id, think_mode, error, extra_fields).

    Supports:
    - @think=N suffix for thinking depth
    - @search suffix for web search
    - -search suffix for web search

    Unknown model names fall back to default rather than erroring,
    since upstream clients may request arbitrary model identifiers.
    """
    think_override = None
    search_mode = False

    # Parse @think=N
    if "@think=" in model_name:
        model_name, think_str = model_name.rsplit("@think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None

    # Parse @search or -search
    if "@search" in model_name:
        model_name = model_name.replace("@search", "").replace("--", "-").strip("-")
        search_mode = True
    elif model_name.endswith("-search"):
        model_name = model_name[:-7]
        search_mode = True

    cfg = MODELS.get(model_name)
    if not cfg:
        from .gemini import log
        log(f"Unknown model '{model_name}', falling back to '{default}'")
        model_name = default
        cfg = MODELS[default]

    mode_id = cfg["mode"]
    think_mode = think_override if think_override is not None else cfg["think"]

    # If search mode, use search model config if available
    if search_mode or cfg.get("search"):
        search_mode = True

    extra = dict(cfg.get("extra", {})) if cfg.get("extra") else {}

    return model_name, mode_id, think_mode, None, extra, search_mode
