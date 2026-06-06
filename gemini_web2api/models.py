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
    "gemini-3.5-flash-thinking-lite": {
        "mode": 5, "think": 0,
        "desc": "Dynamic thinking with adaptive depth",
    },
    "gemini-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Lightweight fast model",
    },
    "gemini-3.5-flash-search": {
        "mode": 1, "think": 4, "search": True,
        "desc": "Flash with web search enabled",
    },
    "gemini-3.5-flash-thinking-search": {
        "mode": 2, "think": 0, "search": True,
        "desc": "Thinking + web search",
    },
    "gemini-3.1-pro-search": {
        "mode": 3, "think": 4, "search": True,
        "desc": "Pro with web search enabled",
    },
}


def resolve_model(model_name: str, default: str = "gemini-3.5-flash"):
    """Resolve model name to (name, mode_id, think_mode, error, extra_fields)."""
    think_override = None
    search_enabled = False

    if "@search" in model_name:
        model_name = model_name.replace("@search", "")
        search_enabled = True

    if "@think=" in model_name:
        model_name, think_str = model_name.rsplit("@think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None

    cfg = MODELS.get(model_name)
    if not cfg:
        from .gemini import log
        log(f"Unknown model '{model_name}', falling back to '{default}'")
        model_name = default
        cfg = MODELS[default]

    if cfg.get("search") or search_enabled:
        search_enabled = True

    mode_id = cfg["mode"]
    think_mode = think_override if think_override is not None else cfg["think"]
    extra = dict(cfg.get("extra")) if cfg.get("extra") else None

    if search_enabled:
        if extra is None:
            extra = {}
        extra[35] = 1

    return model_name, mode_id, think_mode, None, extra
