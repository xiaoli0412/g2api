"""Entry point: python -m gemini_web2api"""
import argparse
import os

from .config import CONFIG, load_config, find_config
from .models import get_available_models
from .gemini import HAS_HTTPX
from .server import GeminiHandler, ThreadedServer
from .admin import init_admin
from . import __version__


def main():
    parser = argparse.ArgumentParser(description="Gemini Web to OpenAI API")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--cookie-file", type=str, default=None)
    parser.add_argument("--auth-user", type=str, default=None, help="Google account index path, e.g. 1 for /u/1/app")
    parser.add_argument("--proxy", type=str, default=None, help="HTTP proxy, e.g. http://127.0.0.1:7890")
    parser.add_argument("--version", action="version", version=f"gemini-web2api {__version__}")
    args = parser.parse_args()

    config_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if config_path:
        load_config(config_path)

    if args.port:
        CONFIG["port"] = args.port
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file
    if args.auth_user is not None:
        CONFIG["auth_user"] = args.auth_user
    if args.proxy:
        CONFIG["proxy"] = args.proxy
        CONFIG["proxy_enabled"] = True

    init_admin()

    port = CONFIG["port"]
    server = ThreadedServer((CONFIG["host"], port), GeminiHandler)
    print(f"gemini-web2api v{__version__}")
    print(f"  Listening: http://0.0.0.0:{port}")
    print(f"  Base URL:  http://localhost:{port}/v1")
    print(f"  Claude:    http://localhost:{port}/v1/messages")
    print(f"  Admin:     http://localhost:{port}/admin")
    exposed_models = get_available_models(
        has_cookie=bool(CONFIG.get("cookie_file")),
        expose_experimental=bool(CONFIG.get("expose_experimental_models") or CONFIG.get("expose_web_feature_models")),
    )
    print(f"  Models:    {', '.join(exposed_models.keys())}")
    print(f"  Cookie:    {'yes' if CONFIG.get('cookie_file') else 'none (anonymous)'}")
    print(f"  Proxy:     {CONFIG.get('proxy') or 'system env'}")
    print(f"  Streaming: {'httpx (true streaming)' if HAS_HTTPX else 'urllib (buffered)'}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
