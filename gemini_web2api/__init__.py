"""gemini-web2api: Gemini Web to OpenAI API proxy."""
from .config import CONFIG, DEFAULT_CONFIG, load_config, find_config
from .models import MODELS, resolve_model

__version__ = "2.1.0"

__all__ = [
    "__version__",
    "CONFIG",
    "DEFAULT_CONFIG",
    "load_config",
    "find_config",
    "MODELS",
    "resolve_model",
]
