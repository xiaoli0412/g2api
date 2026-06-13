"""Capability matrix for the proxy and live verification tooling."""
import time

from .models import get_all_models
from .models import SOURCE_DISCOVERED_WEB_MODELS
from .models import WEB_FEATURES


CAPABILITIES = [
    {
        "id": "openai_chat",
        "name": "OpenAI chat completions",
        "status": "supported",
        "route": "POST /v1/chat/completions",
        "verification": "live_verify openai_chat",
    },
    {
        "id": "openai_chat_stream",
        "name": "OpenAI SSE streaming",
        "status": "supported",
        "route": "POST /v1/chat/completions stream=true",
        "verification": "live_verify openai_chat_stream",
    },
    {
        "id": "responses_api",
        "name": "OpenAI Responses API",
        "status": "supported",
        "route": "POST /v1/responses",
        "verification": "live_verify responses_api",
    },
    {
        "id": "claude_messages",
        "name": "Claude Messages API",
        "status": "supported",
        "route": "POST /v1/messages",
        "verification": "live_verify claude_messages",
    },
    {
        "id": "google_generate_content",
        "name": "Google Gemini generateContent",
        "status": "supported",
        "route": "POST /v1beta/models/{model}:generateContent",
        "verification": "live_verify google_generate_content",
    },
    {
        "id": "google_stream_generate_content",
        "name": "Google Gemini streamGenerateContent",
        "status": "supported",
        "route": "POST /v1beta/models/{model}:streamGenerateContent",
        "verification": "live_verify google_stream_generate_content",
    },
    {
        "id": "tool_calling",
        "name": "Tool/function calling compatibility",
        "status": "supported",
        "route": "OpenAI tools and Google functionDeclarations",
        "verification": "live_verify openai_tool_call and google_function_call_any",
        "note": "Implemented by prompt shaping and response parsing, not by a public Google Web tool API.",
    },
    {
        "id": "web_search",
        "name": "Gemini Web search mode",
        "status": "supported",
        "route": "model suffix -search",
        "verification": "live_verify search_model",
    },
    {
        "id": "thinking",
        "name": "Thinking mode/depth",
        "status": "supported",
        "route": "thinking models and -think=N suffix",
        "verification": "live_verify thinking_model",
    },
    {
        "id": "pro_route",
        "name": "Pro model route preference",
        "status": "login_required",
        "route": "model mode category 3",
        "verification": "live_verify pro_model_cookie_route",
        "note": "A paid Gemini Advanced entitlement is required for real Pro routing; otherwise upstream may silently route to Flash.",
    },
    {
        "id": "multimodal_upload",
        "name": "Gemini Web content-push upload",
        "status": "partial",
        "route": "content-push.googleapis.com/upload",
        "verification": "live_verify multimodal_upload",
        "note": "Upload can return a /contrib_service reference, but final StreamGenerate handoff may be rejected upstream.",
    },
    {
        "id": "multimodal_prompt",
        "name": "Image/audio/video/document prompt handoff",
        "status": "limited",
        "route": "Private Gemini Web StreamGenerate payload",
        "verification": "live_verify multimodal_prompt",
        "note": "Observed upstream rejection is BardErrorInfo [1003] with the current cookie/source shape.",
    },
    {
        "id": "canvas_artifacts",
        "name": "Canvas-like artifacts",
        "status": "supported",
        "route": "response artifact extraction",
        "verification": "unit tests for code/html artifact extraction",
    },
    {
        "id": "image_generation",
        "name": "Create image",
        "status": "experimental",
        "route": "POST /v1/images/generations, /v1/images/edits, /v1/images/variations, or POST /v1beta/models/{model}:generateImages",
        "verification": "live_verify openai_image_generation_endpoint plus artifact checks",
        "note": "Only saved local /artifacts URLs are returned as usable data. Placeholder Gemini Web URLs stay in diagnostics.",
    },
    {
        "id": "video_generation",
        "name": "Create video",
        "status": "experimental",
        "route": "POST /v1/videos, /v1/videos/generations, /v1/video/generations, or POST /v1beta/models/{model}:generateVideos; GET /v1/videos/{id}; GET /v1/videos/{id}/content",
        "verification": "live_verify openai_video_generation_endpoint plus artifact checks",
        "note": "The proxy exposes a task-compatible wrapper. Real video is supported only when Gemini Web returns a downloadable artifact.",
    },
    {
        "id": "deep_research",
        "name": "Deep research",
        "status": "experimental",
        "route": "model alias gemini-deep-research or suffix -deep-research/-research",
        "verification": "live text response plus source/HAR evidence; deeper task flow still needs browser verification",
    },
    {
        "id": "music",
        "name": "Music / Lyria",
        "status": "limited",
        "route": "model alias lyria-3 or suffix -music",
        "verification": "HAR batchexecute RPC evidence only",
    },
    {
        "id": "text_to_speech",
        "name": "Speech / TTS",
        "status": "limited",
        "route": "POST /v1/audio/speech, /v1/audio/generations, or POST /v1beta/models/{model}:generateAudio/:textToSpeech",
        "verification": "live_verify openai_audio_speech_endpoint; real audio artifact still requires browser/RPC verification",
    },
    {
        "id": "photos_library_notebooks",
        "name": "Photos, Library, Notebooks",
        "status": "limited",
        "route": "model aliases gemini-photos, gemini-library, gemini-notebook or matching suffixes",
        "verification": "source/HAR feature evidence only",
    },
]


def get_capability_report(has_cookie: bool = False) -> dict:
    """Return a sanitized, user-facing capability report."""
    return {
        "generated_at": int(time.time()),
        "has_cookie": bool(has_cookie),
        "models": list(get_all_models(has_cookie).keys()),
        "capabilities": [dict(item) for item in CAPABILITIES],
        "web_features": {key: dict(value) for key, value in WEB_FEATURES.items()},
        "source_discovered_web_models": [dict(item) for item in SOURCE_DISCOVERED_WEB_MODELS],
    }


def capability_status_counts(capabilities=None) -> dict:
    counts = {}
    for item in capabilities or CAPABILITIES:
        status = item.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts
