"""Entry point: python -m gemini_web2api"""
import argparse
import os

from .config import CONFIG, load_config, find_config
from .models import MODELS
from .gemini import HAS_HTTPX
from .tokenizer import _get_encoder
from .server import GeminiHandler, ThreadedServer
from . import cookie_manager
from . import __version__


def main():
    parser = argparse.ArgumentParser(description="Gemini Web to OpenAI API")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--cookie-file", type=str, default=None)
    parser.add_argument("--proxy", type=str, default=None, help="HTTP proxy, e.g. http://127.0.0.1:7890")
    parser.add_argument("--auto-cookie", action="store_true", default=False, help="Auto-extract cookies from Edge browser")
    parser.add_argument("--auto-refresh", type=int, default=None, metavar="HOURS", help="Auto-refresh cookie interval in hours (e.g. 12)")
    parser.add_argument("--stream-mode", type=str, default=None, choices=["auto", "true", "fake"], help="Streaming mode: auto (detect), true (real only), fake (always fast fake)")
    parser.add_argument("--cookie-source", type=str, default=None, choices=["auto", "playwright"], help="Cookie extraction source")
    parser.add_argument("--browser-login", action="store_true", default=False, help="Open browser for manual Gemini login")
    parser.add_argument("--version", action="version", version=f"gemini-web2api {__version__}")
    args = parser.parse_args()

    config_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if config_path:
        load_config(config_path)

    if args.port:
        CONFIG["port"] = args.port
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file
    if args.proxy:
        CONFIG["proxy"] = args.proxy
    if args.stream_mode:
        CONFIG["stream_mode"] = args.stream_mode
    if args.cookie_source:
        CONFIG["cookie_source"] = args.cookie_source

    if args.browser_login:
        from . import playwright_cookie
        if playwright_cookie.is_playwright_available():
            print("  Opening browser for Gemini login...")
            result = playwright_cookie.launch_browser_login()
            if result.get("success"):
                cookie_file = CONFIG.get("cookie_file") or "cookie.txt"
                CONFIG["cookie_file"] = cookie_file
                cookie_manager.write_cookie_file(result["cookies"], result.get("sapisid", ""), cookie_file)
                print(f"  Login successful! Cookies saved to {cookie_file}")
            else:
                print(f"  Login failed: {result.get('error', 'unknown')}")
        else:
            print("  Playwright not installed. Run: pip install playwright && playwright install msedge")
        return

    if args.auto_cookie or CONFIG.get("auto_cookie"):
        cookie_file = CONFIG.get("cookie_file") or "cookie.txt"
        CONFIG["cookie_file"] = cookie_file
        cookie_str, sapisid = cookie_manager.extract_edge_cookies()
        if cookie_str:
            cookie_manager.write_cookie_file(cookie_str, sapisid, cookie_file)
            print(f"  Auto Cookie: extracted from Edge -> {cookie_file}")
        else:
            print("  Auto Cookie: FAILED - could not extract Edge cookies")

    refresh_hours = args.auto_refresh or CONFIG.get("auto_refresh_hours")
    if refresh_hours:
        cookie_manager.start_auto_refresh(int(refresh_hours))
        print(f"  Auto Refresh: every {refresh_hours}h")

    has_tiktoken = _get_encoder() is not None
    port = CONFIG["port"]
    server = ThreadedServer((CONFIG["host"], port), GeminiHandler)
    print(f"gemini-web2api v{__version__}")
    print(f"  Listening:   http://0.0.0.0:{port}")
    print(f"  Base URL:    http://localhost:{port}/v1")
    print(f"  Dashboard:   http://localhost:{port}/dashboard")
    print(f"  Models:      {', '.join(MODELS.keys())}")
    print(f"  Cookie:      {'yes' if CONFIG.get('cookie_file') else 'none (anonymous)'}")
    print(f"  Proxy:       {CONFIG.get('proxy') or 'system env'}")
    print(f"  Streaming:   {'httpx (true streaming)' if HAS_HTTPX else 'urllib (buffered)'} | mode={CONFIG.get('stream_mode', 'auto')}")
    print(f"  Tokenizer:   {'tiktoken (accurate)' if has_tiktoken else 'len//4 (estimate)'}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
