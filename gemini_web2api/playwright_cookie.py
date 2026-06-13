"""Playwright-based cookie extraction with embedded browser."""
import glob
import json
import os
import shutil
import subprocess
import time
import threading

from .cookies import diagnose_cookie_header

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

_PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".gemini-web2api", "browser-profile")
_REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID", "__Secure-3PSID"]
_browser_lock = threading.Lock()
_login_state = {
    "running": False,
    "status": "idle",
    "started_at": 0,
    "finished_at": 0,
    "error": "",
    "cookie_length": 0,
    "profile_dir": _PROFILE_DIR,
    "backend": "",
    "diagnostics": None,
}


NODE_COOKIE_SCRIPT = r"""
const fs = require('fs');
const { chromium } = require('playwright');

function googleCookieDomain(domain, targetDomain) {
  domain = String(domain || '').toLowerCase();
  targetDomain = String(targetDomain || 'gemini.google.com').toLowerCase();
  return domain === 'google.com' ||
    domain === targetDomain ||
    domain === `.${targetDomain}` ||
    domain.endsWith('.google.com') ||
    targetDomain.includes(domain.replace(/^\./, ''));
}

function cookieHeader(cookies, targetDomain) {
  const map = {};
  for (const cookie of cookies || []) {
    if (!googleCookieDomain(cookie.domain, targetDomain)) continue;
    if (!cookie.name || !cookie.value) continue;
    map[cookie.name] = cookie.value;
  }
  const names = Object.keys(map).sort();
  return {
    cookie_header: names.map((name) => `${name}=${map[name]}`).join('; '),
    sapisid: map.SAPISID || '',
    cookie_names: names
  };
}

function hasBackendMarkers(names) {
  names = new Set(names || []);
  const hasSession = names.has('SID') || names.has('__Secure-1PSID') || names.has('__Secure-3PSID');
  const hasSapisid = names.has('SAPISID') || names.has('APISID');
  return hasSession && hasSapisid;
}

async function launchPersistent(input, out) {
  const candidates = [];
  if (input.channel) candidates.push(input.channel);
  candidates.push('msedge', 'chrome', 'chromium');
  for (const channel of [...new Set(candidates)]) {
    try {
      const launchOptions = {
        headless: input.headless,
        args: ['--disable-blink-features=AutomationControlled'],
        userAgent: input.user_agent
      };
      if (channel !== 'chromium') launchOptions.channel = channel;
      const context = await chromium.launchPersistentContext(input.profile_dir, launchOptions);
      out.channel = channel;
      return context;
    } catch (err) {
      out.launch_errors.push(`${channel}: ${String(err.message || err).slice(0, 220)}`);
    }
  }
  throw new Error('No Playwright Chromium browser/channel could be launched');
}

(async () => {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  fs.mkdirSync(input.profile_dir, { recursive: true });
  const out = {
    ok: false,
    backend: 'node',
    channel: null,
    launch_errors: [],
    final_url: '',
    title: '',
    cookie_header: '',
    sapisid: '',
    cookie_names: [],
    waited_ms: 0
  };
  const context = await launchPersistent(input, out);
  try {
    const page = context.pages()[0] || await context.newPage();
    await page.goto(input.url, { waitUntil: 'domcontentloaded', timeout: input.timeout_ms });
    const start = Date.now();
    const maxWait = Number(input.max_wait_ms || 0);
    let extracted = { cookie_header: '', sapisid: '', cookie_names: [] };
    while (true) {
      const cookies = await context.cookies(input.cookie_urls);
      extracted = cookieHeader(cookies, input.target_domain);
      if (hasBackendMarkers(extracted.cookie_names)) break;
      if (Date.now() - start >= maxWait) break;
      await page.waitForTimeout(2000);
    }
    out.waited_ms = Date.now() - start;
    out.final_url = page.url();
    out.title = await page.title().catch(() => '');
    out.cookie_header = extracted.cookie_header;
    out.sapisid = extracted.sapisid;
    out.cookie_names = extracted.cookie_names;
    out.ok = hasBackendMarkers(extracted.cookie_names);
    await context.close();
  } finally {
    try { await context.close(); } catch (_) {}
  }
  console.log(JSON.stringify(out));
})().catch((err) => {
  console.log(JSON.stringify({ ok: false, backend: 'node', error: String(err.stack || err).slice(0, 1200) }));
  process.exit(1);
});
"""


def _node_playwright_command():
    env = os.environ.copy()
    bundled_root = os.path.join(
        os.path.expanduser("~"),
        ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node",
    )
    bundled_node = os.path.join(bundled_root, "bin", "node.exe")
    bundled_modules = os.path.join(bundled_root, "node_modules")
    if os.path.exists(bundled_node) and os.path.isdir(os.path.join(bundled_modules, "playwright")):
        pnpm_modules = glob.glob(os.path.join(bundled_modules, ".pnpm", "*", "node_modules"))
        env["NODE_PATH"] = os.pathsep.join(
            [bundled_modules, *pnpm_modules, env.get("NODE_PATH", "")]
        ).strip(os.pathsep)
        return [bundled_node, "-e", NODE_COOKIE_SCRIPT], env, "bundled-node"

    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        return None, env, ""
    return [npx, "--yes", "--package", "playwright", "node", "-e", NODE_COOKIE_SCRIPT], env, "npx"


def is_node_playwright_available() -> bool:
    command, _, _ = _node_playwright_command()
    return bool(command)


def available_playwright_backends() -> list[str]:
    backends = []
    if HAS_PLAYWRIGHT:
        backends.append("python")
    if is_node_playwright_available():
        backends.append("node")
    return backends


def is_playwright_available() -> bool:
    return bool(available_playwright_backends())


def get_browser_login_status() -> dict:
    state = dict(_login_state)
    state["available_backends"] = available_playwright_backends()
    return state


def _cookie_urls(domain: str = "gemini.google.com") -> list[str]:
    return [
        f"https://{domain}",
        "https://gemini.google.com",
        "https://accounts.google.com",
        "https://www.google.com",
    ]


def _extract_cookie_header_from_cookie_list(cookies: list[dict], domain: str = "gemini.google.com") -> tuple:
    cookie_map = {}
    for c in cookies or []:
        cookie_domain = (c.get("domain") or "").lower()
        if domain in cookie_domain or cookie_domain.endswith(".google.com") or cookie_domain == "google.com":
            name = c.get("name")
            value = c.get("value")
            if name and value:
                cookie_map[name] = value

    if not (("SID" in cookie_map or "__Secure-1PSID" in cookie_map or "__Secure-3PSID" in cookie_map)
            and ("SAPISID" in cookie_map or "APISID" in cookie_map)):
        cookie_str = "; ".join(f"{k}={v}" for k, v in sorted(cookie_map.items()) if v)
        return None, None, diagnose_cookie_header(cookie_str)

    cookie_str = "; ".join(
        f"{k}={v}" for k, v in sorted(cookie_map.items())
        if v
    )
    sapisid = cookie_map.get("SAPISID", "")
    return cookie_str, sapisid, diagnose_cookie_header(cookie_str)


def _extract_cookies_from_context(context, domain: str = "gemini.google.com") -> tuple:
    cookies = context.cookies(list(dict.fromkeys(_cookie_urls(domain))))
    cookie_str, sapisid, _ = _extract_cookie_header_from_cookie_list(cookies, domain)
    return cookie_str, sapisid


def _launch_browser_login_python(headless: bool, max_wait: int, channel: str = "msedge") -> dict:
    if not HAS_PLAYWRIGHT:
        return {"success": False, "error": "python playwright not installed"}

    os.makedirs(_PROFILE_DIR, exist_ok=True)

    context = None
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                _PROFILE_DIR,
                channel=channel,
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                ),
            )
            page = context.new_page()
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")

            start = time.time()
            while time.time() - start < max_wait:
                cookie_str, sapisid = _extract_cookies_from_context(context)
                if cookie_str:
                    diagnostics = diagnose_cookie_header(cookie_str)
                    context.close()
                    return {
                        "success": True,
                        "cookies": cookie_str,
                        "sapisid": sapisid,
                        "backend": "python",
                        "diagnostics": diagnostics,
                    }
                time.sleep(2)

            cookie_str, sapisid = _extract_cookies_from_context(context)
            diagnostics = diagnose_cookie_header(cookie_str or "")
            context.close()
            if cookie_str:
                return {
                    "success": True,
                    "cookies": cookie_str,
                    "sapisid": sapisid,
                    "backend": "python",
                    "diagnostics": diagnostics,
                }
            return {
                "success": False,
                "error": "Login timeout or no valid cookies found",
                "backend": "python",
                "diagnostics": diagnostics,
            }

    except Exception as e:
        return {"success": False, "error": str(e), "backend": "python"}
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass


def _run_node_cookie_browser(headless: bool, max_wait: int, timeout_ms: int = 45000, channel: str = None) -> dict:
    command, env, command_backend = _node_playwright_command()
    if not command:
        return {"success": False, "error": "Node.js/npm npx is not available", "backend": "node"}
    payload = {
        "profile_dir": _PROFILE_DIR,
        "url": "https://gemini.google.com/app",
        "cookie_urls": _cookie_urls(),
        "target_domain": "gemini.google.com",
        "headless": headless,
        "channel": channel,
        "max_wait_ms": int(max_wait * 1000),
        "timeout_ms": timeout_ms,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    try:
        proc = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=max_wait + (timeout_ms / 1000) + 120,
            check=False,
            env=env,
        )
    except Exception as exc:
        return {"success": False, "error": str(exc), "backend": "node", "command_backend": command_backend}
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {
            "success": False,
            "error": (proc.stderr or "node playwright produced no output")[:1000],
            "backend": "node",
            "command_backend": command_backend,
        }
    try:
        result = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": f"node playwright returned non-JSON output: {stdout[:500]}",
            "backend": "node",
            "command_backend": command_backend,
        }
    cookie_str = result.get("cookie_header") or ""
    sapisid = result.get("sapisid") or ""
    diagnostics = diagnose_cookie_header(cookie_str)
    if proc.returncode != 0 or not result.get("ok"):
        return {
            "success": False,
            "error": result.get("error") or (proc.stderr or "no valid cookies found")[:1000],
            "backend": "node",
            "command_backend": command_backend,
            "diagnostics": diagnostics,
            "cookie_names": result.get("cookie_names", []),
            "launch_errors": result.get("launch_errors", []),
        }
    return {
        "success": True,
        "cookies": cookie_str,
        "sapisid": sapisid,
        "backend": "node",
        "command_backend": command_backend,
        "diagnostics": diagnostics,
        "cookie_names": result.get("cookie_names", []),
        "channel": result.get("channel"),
    }


def launch_browser_login(port: int = 8081) -> dict:
    del port
    if not is_playwright_available():
        return {
            "success": False,
            "error": "Playwright is not available. Install python playwright or Node.js/npm npx.",
            "available_backends": [],
        }

    os.makedirs(_PROFILE_DIR, exist_ok=True)

    with _browser_lock:
        errors = []
        if HAS_PLAYWRIGHT:
            result = _launch_browser_login_python(headless=False, max_wait=300)
            if result.get("success"):
                return result
            errors.append(f"python: {result.get('error', 'unknown error')}")

        result = _run_node_cookie_browser(headless=False, max_wait=300, timeout_ms=60000)
        if result.get("success"):
            return result
        errors.append(f"node: {result.get('error', 'unknown error')}")
        return {
            "success": False,
            "error": "; ".join(errors) or "Login timeout or no valid cookies found",
            "available_backends": available_playwright_backends(),
            "diagnostics": result.get("diagnostics"),
        }


def refresh_cookie_via_playwright() -> tuple:
    if not is_playwright_available():
        return None, None

    os.makedirs(_PROFILE_DIR, exist_ok=True)

    with _browser_lock:
        if HAS_PLAYWRIGHT:
            result = _launch_browser_login_python(headless=True, max_wait=7)
            if result.get("success"):
                return result.get("cookies"), result.get("sapisid")

        result = _run_node_cookie_browser(headless=True, max_wait=7, timeout_ms=45000)
        if result.get("success"):
            return result.get("cookies"), result.get("sapisid")
        return None, None


def start_browser_login_async(cookie_file: str = None, port: int = 8081) -> dict:
    """Launch the isolated browser login flow in a background thread."""
    if not is_playwright_available():
        return {
            "success": False,
            "error": "Playwright is not available. Install python playwright or Node.js/npm npx.",
            "status": get_browser_login_status(),
        }
    if _login_state.get("running"):
        return {"success": True, "message": "browser login already running", "status": get_browser_login_status()}

    def worker():
        _login_state.update({
            "running": True,
            "status": "opening_browser",
            "started_at": time.time(),
            "finished_at": 0,
            "error": "",
            "cookie_length": 0,
        })
        try:
            result = launch_browser_login(port)
            if result.get("success"):
                cookies = result.get("cookies", "")
                sapisid = result.get("sapisid", "")
                from . import cookie_manager
                target = cookie_file or cookie_manager.CONFIG.get("cookie_file") or "cookie.txt"
                accepted = cookie_manager.accept_cookie_source(
                    cookies,
                    sapisid,
                    source="internal-browser",
                    target=target,
                )
                _login_state.update({
                    "status": "saved" if accepted.get("success") else "failed",
                    "cookie_length": len(cookies),
                    "error": "" if accepted.get("success") else accepted.get("message", "failed to save cookies"),
                    "backend": result.get("backend", ""),
                    "diagnostics": accepted.get("diagnostics") or result.get("diagnostics"),
                })
            else:
                _login_state.update({
                    "status": "failed",
                    "error": result.get("error", "unknown error"),
                    "diagnostics": result.get("diagnostics"),
                })
        except Exception as exc:
            _login_state.update({
                "status": "failed",
                "error": str(exc),
            })
        finally:
            _login_state.update({
                "running": False,
                "finished_at": time.time(),
                "profile_dir": _PROFILE_DIR,
            })

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {"success": True, "message": "browser login started", "status": get_browser_login_status()}
