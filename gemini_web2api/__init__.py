"""gemini-web2api: Gemini Web to OpenAI API proxy."""
__version__ = "1.2.0"

from .config import CONFIG, DEFAULT_CONFIG, load_config, find_config
from .models import MODELS, resolve_model, get_available_models
from .gemini import extract_images_from_response, extract_artifacts_from_response
from .tools import parse_tool_calls, messages_to_prompt, StreamToolCallBuffer
from .adapters import convert_claude_messages_to_openai, convert_openai_response_to_claude
from .admin import init_admin, handle_admin_request
from .capabilities import CAPABILITIES, get_capability_report

__all__ = [
    "__version__", "CONFIG", "DEFAULT_CONFIG", "load_config", "find_config",
    "MODELS", "resolve_model", "get_available_models",
    "extract_images_from_response", "extract_artifacts_from_response",
    "parse_tool_calls", "messages_to_prompt", "StreamToolCallBuffer",
    "convert_claude_messages_to_openai", "convert_openai_response_to_claude",
    "init_admin", "handle_admin_request",
    "CAPABILITIES", "get_capability_report",
]
