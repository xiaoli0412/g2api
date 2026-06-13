"""Model definitions and mapping from Gemini frontend JS source.

MODE_CATEGORY enum from Gemini web frontend JS (028-6eb337387583.js):
  1=FAST, 2=THINKING, 3=PRO, 4=AUTO, 5=FAST_DYNAMIC_THINKING, 6=FLASH_LITE

The inner[79] field in the StreamGenerate payload controls model selection.
These are the ONLY valid values - the Gemini backend routes based on this integer.

Model names are client-side aliases for convenience. The actual routing
happens via the MODE_CATEGORY integer, not the model name string.
"""

# ─── Web UI feature aliases found in Gemini Web source/HAR ───────────────────

WEB_FEATURE_SUFFIXES = {
    "-create-image": "image_generation",
    "-image": "image_generation",
    "-images": "image_generation",
    "-create-video": "video_generation",
    "-video": "video_generation",
    "-videos": "video_generation",
    "-create-audio": "text_to_speech",
    "-text-to-speech": "text_to_speech",
    "-speech": "text_to_speech",
    "-tts": "text_to_speech",
    "-audio": "text_to_speech",
    "-deep-research": "deep_research",
    "-research": "deep_research",
    "-canvas": "canvas",
    "-music": "music",
    "-photo": "photos",
    "-photos": "photos",
    "-library": "library",
    "-notebook": "notebook",
    "-notebooks": "notebook",
}

SOURCE_DISCOVERED_WEB_MODELS = [
    {"name": "gemini-2.0-flash", "feature": "text_generation", "registered": True},
    {"name": "gemini-2.5-flash", "feature": "text_generation", "registered": True},
    {"name": "gemini-2.5-flash-preview-04-17", "feature": "text_generation", "registered": True},
    {"name": "gemini-2.5-flash-preview-05-20", "feature": "text_generation", "registered": True},
    {"name": "gemini-2.5-flash-preview-09-2025", "feature": "text_generation", "registered": True},
    {"name": "gemini-3-flash-preview", "feature": "text_generation", "registered": True},
    {"name": "gemini-advanced", "feature": "pro_route", "registered": True},
    {"name": "gemini-2.5-flash-image", "feature": "image_generation", "registered": True},
    {"name": "gemini-2.5-flash-image-preview", "feature": "image_generation", "registered": True},
    {"name": "gemini-3.1-flash-image-preview", "feature": "image_generation", "registered": True},
    {"name": "gemini-3-pro-image-preview-11-2025", "feature": "image_generation", "registered": True},
    {"name": "imagen-3.0-generate-001", "feature": "image_generation", "registered": True},
    {"name": "imagen-3.0-generate-002", "feature": "image_generation", "registered": True},
    {"name": "imagen-4.0-generate-001", "feature": "image_generation", "registered": True},
    {"name": "Nano Banana 2", "feature": "image_generation", "registered": True},
    {"name": "Nano Banana Pro", "feature": "image_generation", "registered": True},
    {"name": "Omni", "feature": "video_generation", "registered": True},
    {"name": "veo-2.0-generate-001", "feature": "video_generation", "registered": True},
    {"name": "Lyria 3", "feature": "music", "registered": True},
    {"name": "gemini-2.5-flash-preview-tts", "feature": "text_to_speech", "registered": True},
]

CORE_MODEL_IDS = (
    "gemini-3.5-flash",
    "gemini-3.5-flash-thinking",
    "gemini-3.1-pro",
    "gemini-3.1-pro-enhanced",
    "gemini-auto",
    "gemini-3.5-flash-thinking-lite",
    "gemini-flash-lite",
)

WEB_FEATURES = {
    "image_generation": {
        "name": "Create images",
        "ui_models": [
            "Nano Banana 2",
            "Nano Banana Pro",
            "gemini-2.5-flash-image",
            "gemini-2.5-flash-image-preview",
            "gemini-3.1-flash-image-preview",
            "gemini-3-pro-image-preview-11-2025",
            "imagen-3.0-generate-001",
            "imagen-3.0-generate-002",
            "imagen-4.0-generate-001",
        ],
        "status": "experimental",
        "note": "Gemini Web source exposes these names, but a real generated image must be verified per account.",
    },
    "video_generation": {
        "name": "Create videos",
        "ui_models": ["Omni", "veo-2.0-generate-001"],
        "status": "experimental",
        "note": "Gemini Web exposes video templates and Omni/Veo names through UI assets; generation is an async Web tool flow.",
    },
    "deep_research": {
        "name": "Deep research",
        "ui_models": ["Gemini Deep Research"],
        "status": "experimental",
        "note": "Uses Gemini Web research UI/RPC flows. The proxy can request search/research mode but must verify real output.",
    },
    "canvas": {
        "name": "Canvas",
        "ui_models": ["Gemini Canvas"],
        "status": "supported",
        "note": "Implemented as artifact extraction from generated code/HTML responses.",
    },
    "music": {
        "name": "Music",
        "ui_models": ["Lyria 3"],
        "status": "limited",
        "note": "HAR shows Music-related batchexecute RPCs; direct generation is not implemented until a normal task flow is verified.",
    },
    "text_to_speech": {
        "name": "Speech / TTS",
        "ui_models": ["gemini-2.5-flash-preview-tts"],
        "status": "limited",
        "note": "Gemini Web source exposes a TTS preview model name, but no normal audio artifact flow has been verified for this proxy.",
    },
    "photos": {
        "name": "Photos",
        "ui_models": ["Google Photos"],
        "status": "limited",
        "note": "HAR/source expose Photos integration; account/library access must not be assumed by the proxy.",
    },
    "library": {
        "name": "Library",
        "ui_models": ["Gemini Library"],
        "status": "limited",
        "note": "Library is a Web UI management surface, not a StreamGenerate text model.",
    },
    "notebook": {
        "name": "Notebooks",
        "ui_models": ["NotebookLM"],
        "status": "limited",
        "note": "Notebook creation and NotebookLM handoff are separate Web application flows.",
    },
}

MODEL_NAME_ALIASES = {
    "nano banana 2": "nano-banana-2",
    "nano_banana_2": "nano-banana-2",
    "nano banana pro": "nano-banana-pro",
    "nano_banana_pro": "nano-banana-pro",
    "lyria 3": "lyria-3",
    "gemini deep research": "gemini-deep-research",
    "deep research": "gemini-deep-research",
    "deep-research": "gemini-deep-research",
    "canvas": "gemini-canvas",
    "google photos": "gemini-photos",
    "google-photos": "gemini-photos",
    "photos": "gemini-photos",
    "library": "gemini-library",
    "gemini notebooks": "gemini-notebook",
    "gemini-notebooks": "gemini-notebook",
    "notebooks": "gemini-notebook",
    "notebooklm": "gemini-notebook",
    "notebook-lm": "gemini-notebook",
    "tts": "gemini-2.5-flash-preview-tts",
    "speech": "gemini-2.5-flash-preview-tts",
}


def _web_feature_extra(feature: str, model_name: str = None) -> dict:
    extra = {"web_feature": feature}
    if model_name:
        extra["web_model_name"] = model_name
    if feature == "image_generation":
        # Observed in a real Gemini Web StreamGenerate HAR shape for media-gen flows.
        extra.update({68: 2, 80: 1})
    elif feature == "deep_research":
        extra["search"] = True
        extra.update({30: [5]})
    return extra


# ─── Core Models (MODE_CATEGORY mapping) ──────────────────────────────────────

MODELS = {
    # ─── MODE_CATEGORY=1 (FAST) ────────────────────────────────────────────────
    "gemini-3.5-flash": {
        "mode": 1, "think": 4,
        "desc": "Fast general-purpose model (全方位帮助)",
        "anon": True,
    },
    "3.5-flash": {
        "mode": 1, "think": 4,
        "desc": "Gemini Web UI alias: 3.5 Flash",
        "anon": True,
    },
    "flash": {
        "mode": 1, "think": 4,
        "desc": "Gemini Web UI alias: Flash",
        "anon": True,
    },
    "gemini-3.1-flash": {
        "mode": 1, "think": 4,
        "desc": "Gemini Web UI alias: 3.1 Flash",
        "anon": True,
    },
    "gemini-3.0-flash": {
        "mode": 1, "think": 4,
        "desc": "Previous generation flash model",
        "anon": True,
    },
    "gemini-2.5-flash": {
        "mode": 1, "think": 4,
        "desc": "2.5 Flash stable release",
        "anon": True,
    },
    "gemini-2.5-flash-preview-04-17": {
        "mode": 1, "think": 4,
        "desc": "Source-discovered Gemini Web 2.5 Flash preview alias",
        "anon": True,
    },
    "gemini-2.5-flash-preview-05-20": {
        "mode": 1, "think": 4,
        "desc": "Source-discovered Gemini Web 2.5 Flash preview alias",
        "anon": True,
    },
    "gemini-2.5-flash-preview-09-2025": {
        "mode": 1, "think": 4,
        "desc": "Source-discovered Gemini Web 2.5 Flash preview alias",
        "anon": True,
    },
    "gemini-3-flash-preview": {
        "mode": 1, "think": 4,
        "desc": "Source-discovered Gemini Web 3 Flash preview alias",
        "anon": True,
    },
    "gemini-2.0-flash": {
        "mode": 1, "think": 4,
        "desc": "2.0 Flash stable release",
        "anon": True,
    },

    # ─── MODE_CATEGORY=2 (THINKING) ────────────────────────────────────────────
    "gemini-3.5-flash-thinking": {
        "mode": 2, "think": 0,
        "desc": "Deep thinking mode (解决复杂问题)",
        "anon": True,
    },

    # ─── MODE_CATEGORY=3 (PRO) ─────────────────────────────────────────────────
    "gemini-3.1-pro": {
        "mode": 3, "think": 4,
        "desc": "Pro model for math/code (高等数学与代码)",
        "anon": False,  # Requires login
    },
    "3.1-pro": {
        "mode": 3, "think": 4,
        "desc": "Gemini Web UI alias: 3.1 Pro",
        "anon": False,
    },
    "gemini-3.1-pro-enhanced": {
        "mode": 3, "think": 4, "extra": {31: 2, 80: 3},
        "desc": "Pro with enhanced output (experimental)",
        "anon": False,
    },
    "gemini-advanced": {
        "mode": 3, "think": 4,
        "desc": "Gemini Web Advanced tier alias; real routing depends on account entitlement",
        "anon": False,
    },
    "gemini-2.5-pro": {
        "mode": 3, "think": 4,
        "desc": "2.5 Pro stable release",
        "anon": False,
    },
    "gemini-3.0-pro": {
        "mode": 3, "think": 4,
        "desc": "Previous generation pro model",
        "anon": False,
    },

    # ─── MODE_CATEGORY=4 (AUTO) ────────────────────────────────────────────────
    "gemini-auto": {
        "mode": 4, "think": 4,
        "desc": "Auto model selection",
        "anon": True,
    },

    # ─── MODE_CATEGORY=5 (FAST_DYNAMIC_THINKING) ───────────────────────────────
    "gemini-3.5-flash-thinking-lite": {
        "mode": 5, "think": 0,
        "desc": "Dynamic thinking with adaptive depth",
        "anon": True,
    },

    # ─── MODE_CATEGORY=6 (FLASH_LITE) ──────────────────────────────────────────
    "gemini-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Lightweight fast model",
        "anon": True,
    },
    "gemini-3.1-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Gemini Web UI alias: 3.1 Flash-Lite",
        "anon": True,
    },
    "3.1-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Gemini Web UI alias: 3.1 Flash-Lite",
        "anon": True,
    },
    "gemini-2.5-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "2.5 Flash Lite - cost-efficient",
        "anon": True,
    },

    # ─── Search Models (web search enabled) ────────────────────────────────────
    "gemini-3.5-flash-search": {
        "mode": 1, "think": 4, "search": True,
        "desc": "Flash with web search",
        "anon": True,
    },
    "gemini-3.5-flash-thinking-search": {
        "mode": 2, "think": 0, "search": True,
        "desc": "Thinking with web search",
        "anon": True,
    },
    "gemini-3.1-pro-search": {
        "mode": 3, "think": 4, "search": True,
        "desc": "Pro with web search",
        "anon": False,
    },
    "gemini-2.5-pro-search": {
        "mode": 3, "think": 4, "search": True,
        "desc": "2.5 Pro with web search",
        "anon": False,
    },
    "gemini-2.5-flash-search": {
        "mode": 1, "think": 4, "search": True,
        "desc": "2.5 Flash with web search",
        "anon": True,
    },

    # ─── Gemini Web tool aliases observed in page source/HAR ─────────────────
    "nano-banana-2": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "Nano Banana 2"),
        "desc": "Gemini Web Create images alias: Nano Banana 2",
        "anon": False,
    },
    "nano-banana-pro": {
        "mode": 3, "think": 0, "extra": _web_feature_extra("image_generation", "Nano Banana Pro"),
        "desc": "Gemini Web Create images alias: Nano Banana Pro",
        "anon": False,
    },
    "gemini-2.5-flash-image": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "gemini-2.5-flash-image"),
        "desc": "Hidden Gemini Web image model alias",
        "anon": False,
    },
    "gemini-2.5-flash-image-preview": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "gemini-2.5-flash-image-preview"),
        "desc": "Hidden Gemini Web image preview model alias",
        "anon": False,
    },
    "gemini-3.1-flash-image-preview": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "gemini-3.1-flash-image-preview"),
        "desc": "Hidden Gemini Web image preview model alias",
        "anon": False,
    },
    "gemini-3-pro-image-preview-11-2025": {
        "mode": 3, "think": 0, "extra": _web_feature_extra("image_generation", "gemini-3-pro-image-preview-11-2025"),
        "desc": "Hidden Gemini Web Pro image preview alias",
        "anon": False,
    },
    "imagen-3.0-generate-001": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "imagen-3.0-generate-001"),
        "desc": "Imagen generation model name observed in Gemini Web source",
        "anon": False,
    },
    "imagen-3.0-generate-002": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "imagen-3.0-generate-002"),
        "desc": "Imagen generation model name observed in Gemini Web source",
        "anon": False,
    },
    "imagen-4.0-generate-001": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("image_generation", "imagen-4.0-generate-001"),
        "desc": "Imagen generation model name observed in Gemini Web source",
        "anon": False,
    },
    "omni": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("video_generation", "Omni"),
        "desc": "Gemini Web Create videos alias: Omni",
        "anon": False,
    },
    "veo-2.0-generate-001": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("video_generation", "veo-2.0-generate-001"),
        "desc": "Veo generation model name observed in Gemini Web source",
        "anon": False,
    },
    "lyria-3": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("music", "Lyria 3"),
        "desc": "Gemini Web Music alias: Lyria 3",
        "anon": False,
    },
    "gemini-2.5-flash-preview-tts": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("text_to_speech", "gemini-2.5-flash-preview-tts"),
        "desc": "Gemini Web source-discovered TTS preview alias",
        "anon": False,
    },
    "gemini-deep-research": {
        "mode": 2, "think": 0, "search": True, "extra": _web_feature_extra("deep_research", "Gemini Deep Research"),
        "desc": "Gemini Web Deep research alias",
        "anon": False,
    },
    "gemini-canvas": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("canvas", "Gemini Canvas"),
        "desc": "Canvas-like artifact extraction alias",
        "anon": True,
    },
    "gemini-photos": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("photos", "Google Photos"),
        "desc": "Gemini Web Photos integration alias",
        "anon": False,
    },
    "gemini-library": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("library", "Gemini Library"),
        "desc": "Gemini Web Library surface alias",
        "anon": False,
    },
    "gemini-notebook": {
        "mode": 1, "think": 4, "extra": _web_feature_extra("notebook", "NotebookLM"),
        "desc": "Gemini Web Notebooks/NotebookLM handoff alias",
        "anon": False,
    },
}


def get_available_models(has_cookie: bool = False, expose_experimental: bool = False) -> dict:
    """Get models exposed to generic clients.
    
    Args:
        has_cookie: Whether user has valid cookie
        expose_experimental: Expose all extended aliases in /v1/models-style lists.
    
    Returns:
        dict of available models
    """
    if expose_experimental:
        if has_cookie:
            return MODELS
        return {k: v for k, v in MODELS.items() if v.get("anon", False)}
    core = {name: MODELS[name] for name in CORE_MODEL_IDS if name in MODELS}
    return core


def get_all_models(has_cookie: bool = False) -> dict:
    """Return every registered alias for capability/debug tooling."""
    if has_cookie:
        return MODELS
    return {k: v for k, v in MODELS.items() if v.get("anon", False)}


def resolve_model(model_name: str, default: str = "gemini-3.5-flash"):
    """Resolve model name to (name, mode_id, think_mode, error, extra_fields, search_mode).

    Supports:
    - -think=N suffix for thinking depth (0=deepest, 4=none)
    - -thinking-standard / -thinking-extended suffixes from Gemini Web UI
    - -search suffix for web search
    - Web UI tool suffixes such as -image, -video, -deep-research, -canvas
    - @think=N and @search as legacy aliases

    Unknown model names fall back to default rather than erroring,
    since upstream clients may request arbitrary model identifiers.
    
    Examples:
      gemini-3.5-flash              -> mode=1, think=4
      gemini-3.5-flash-think=2      -> mode=1, think=2
      gemini-3.5-flash-search       -> mode=1, think=4, search=True
      gemini-3.1-pro-think=0-search -> mode=3, think=0, search=True
    """
    model_name = (model_name or default).strip().lower()
    if model_name.startswith("models/"):
        model_name = model_name.split("/", 1)[1]
    think_override = None
    search_mode = False
    requested_feature = None

    # Parse -think=N (legacy @think=N also accepted)
    if "@think=" in model_name:
        model_name, think_str = model_name.rsplit("@think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None, False
    elif "-think=" in model_name:
        model_name, think_str = model_name.rsplit("-think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None, False

    # Parse @search or -search
    if "@search" in model_name:
        model_name = model_name.replace("@search", "").replace("--", "-").strip("-")
        search_mode = True
    elif model_name.endswith("-search"):
        model_name = model_name[:-7]
        search_mode = True

    # Parse Gemini Web UI thinking level names.
    if model_name.endswith("-thinking-standard"):
        model_name = model_name[:-18].strip("-") or default
        think_override = 4
    elif model_name.endswith("-thinking-extended"):
        model_name = model_name[:-18].strip("-") or default
        think_override = 0

    # Parse UI feature suffixes, longest first so -create-image wins before -image.
    # Exact hidden model names such as gemini-2.5-flash-image take priority.
    if model_name not in MODELS:
        for suffix, feature in sorted(WEB_FEATURE_SUFFIXES.items(), key=lambda item: len(item[0]), reverse=True):
            if model_name.endswith(suffix):
                model_name = model_name[:-len(suffix)].strip("-") or default
                requested_feature = feature
                break

    model_name = MODEL_NAME_ALIASES.get(model_name, model_name)

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
    if requested_feature:
        extra.update(_web_feature_extra(requested_feature))
        if requested_feature == "deep_research":
            search_mode = True

    return model_name, mode_id, think_mode, None, extra, search_mode
