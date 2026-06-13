"""Real browser Gemini Web UI probe using Playwright through npx.

The probe injects a normalized Cookie header into a temporary browser context,
opens Gemini Web, and records sanitized UI signals. It never prints or stores
cookie values, page text, prompts, or request payloads.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import time

from .config import CONFIG, find_config, load_config
from .cookies import diagnose_cookie_header, normalize_cookie_input
from .har_analyze import KEYWORD_PATTERNS


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

NODE_SCRIPT = r"""
const fs = require('fs');
const { chromium } = require('playwright');

async function launchBrowser(input, out) {
  const candidates = [];
  if (input.channel) candidates.push(input.channel);
  candidates.push('msedge', 'chrome', 'chromium');
  for (const channel of [...new Set(candidates)]) {
    try {
      const launchOptions = {
        headless: input.headless,
        args: ['--disable-blink-features=AutomationControlled']
      };
      if (channel !== 'chromium') launchOptions.channel = channel;
      const browser = await chromium.launch(launchOptions);
      out.channel = channel;
      return browser;
    } catch (err) {
      out.launch_errors.push(`${channel}: ${String(err.message || err).slice(0, 180)}`);
    }
  }
  throw new Error('No Playwright Chromium browser/channel could be launched');
}

(async () => {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const out = {
    ok: false,
    channel: null,
    launch_errors: [],
    status: null,
    final_url: null,
    title: null,
    cookie_names_after_navigation: [],
    body_text_length: 0,
    html_length: 0,
    sign_in_visible: false,
    has_text_entry: false,
    editable_count: 0,
    button_count: 0,
    visible_signin_control_count: 0,
    visible_signin_control_present: false,
    keyword_counts: {},
    screenshot_path: input.screenshot_path || null
  };
  const browser = await launchBrowser(input, out);
  try {
    const context = await browser.newContext({
      userAgent: input.user_agent,
      viewport: { width: 1280, height: 900 },
      locale: 'en-US'
    });
    if (input.cookies && input.cookies.length) {
      await context.addCookies(input.cookies);
    }
    const page = await context.newPage();
    const response = await page.goto(input.url, { waitUntil: 'domcontentloaded', timeout: input.timeout_ms });
    await page.waitForTimeout(input.wait_ms);

    out.status = response ? response.status() : null;
    out.final_url = page.url();
    out.title = await page.title().catch(() => '');
    const bodyText = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');
    const html = await page.content().catch(() => '');
    const combined = `${out.title}\n${out.final_url}\n${bodyText}\n${html}`;
    out.body_text_length = bodyText.length;
    out.html_length = html.length;
    out.sign_in_visible = /sign in|sign-in|登录|登入|ログイン/i.test(combined);
    out.editable_count = await page.locator('textarea, [contenteditable="true"], input[type="text"]').count().catch(() => 0);
    out.button_count = await page.locator('button').count().catch(() => 0);
    out.has_text_entry = out.editable_count > 0;
    out.visible_signin_control_count = await page.locator('a, button, [role="button"]').evaluateAll((elements) => {
      const re = /^(sign in|sign-in|登录|登入|ログイン)$/i;
      return elements.filter((el) => {
        const text = (el.textContent || '').trim();
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return re.test(text)
          && style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      }).length;
    }).catch(() => 0);
    out.visible_signin_control_present = out.visible_signin_control_count > 0;
    for (const item of input.keyword_patterns) {
      const flags = item.flags.includes('g') ? item.flags : `${item.flags}g`;
      const re = new RegExp(item.source, flags);
      out.keyword_counts[item.name] = (combined.match(re) || []).length;
    }
    const navCookies = await context.cookies(input.cookie_urls);
    out.cookie_names_after_navigation = [...new Set(navCookies.map((c) => c.name))].sort();
    if (input.screenshot_path) {
      await page.screenshot({ path: input.screenshot_path, fullPage: true }).catch((err) => {
        out.screenshot_error = String(err.message || err).slice(0, 180);
      });
    }
    out.ok = true;
    await context.close();
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})().catch((err) => {
  console.log(JSON.stringify({ ok: false, error: String(err.stack || err).slice(0, 1000) }));
  process.exit(1);
});
"""


def _account_prefix(auth_user=None) -> str:
    if auth_user is None or auth_user == "":
        auth_user = CONFIG.get("auth_user")
    if auth_user is None or auth_user == "":
        return ""
    return f"/u/{auth_user}"


def _cookie_header_to_playwright_cookies(cookie_header: str) -> list[dict]:
    cookies = []
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        item = {
            "name": name,
            "value": value,
            "secure": True,
            "sameSite": "Lax",
        }
        if name.startswith("__Host-"):
            item["url"] = "https://accounts.google.com/"
        else:
            item["domain"] = ".google.com"
            item["path"] = "/"
        cookies.append(item)
    return cookies


def _cookie_table_to_playwright_cookies(raw: str) -> list[dict]:
    cookies = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) < 4:
            continue
        name, value, domain, path = parts[:4]
        if not name or not value or not domain.startswith((".", "accounts.", "gemini.", "www.")):
            continue
        item = {
            "name": name,
            "value": value,
            "secure": True,
        }
        same_site = next((part for part in parts[4:] if part in {"Lax", "Strict", "None"}), "")
        if same_site:
            item["sameSite"] = same_site
        if name.startswith("__Host-"):
            host = domain.lstrip(".")
            item["url"] = f"https://{host}/"
        else:
            item["domain"] = domain
            item["path"] = path or "/"
        cookies.append(item)
    return cookies


def _cookie_input_to_playwright_cookies(raw: str, cookie_header: str) -> list[dict]:
    table_cookies = _cookie_table_to_playwright_cookies(raw)
    if table_cookies:
        return table_cookies
    return _cookie_header_to_playwright_cookies(cookie_header)


def _keyword_pattern_specs() -> list[dict]:
    return [
        {"name": name, "source": pattern.pattern, "flags": "i"}
        for name, pattern in KEYWORD_PATTERNS.items()
    ]


def _is_google_signin_url(url: str) -> bool:
    lower = (url or "").lower()
    return (
        "accounts.google.com" in lower
        and (
            "/signin" in lower
            or "servicelogin" in lower
            or "/accountchooser" in lower
        )
    )


def _assess_web_ui_login(browser: dict, diagnostics: dict) -> bool:
    """Assess visible Gemini Web UI login from sanitized browser and cookie signals."""
    return (
        browser.get("status") == 200
        and bool(browser.get("has_text_entry"))
        and not _is_google_signin_url(browser.get("final_url", ""))
        and not bool(browser.get("visible_signin_control_present"))
        and bool(diagnostics.get("web_ui_likely_complete"))
    )


def _effective_cookie_file(cli_cookie_file=None) -> str:
    """Return the cookie file that browser probing should inject."""
    return cli_cookie_file or CONFIG.get("cookie_file") or ""


def _run_node_probe(input_payload: dict) -> dict:
    env = os.environ.copy()
    bundled_root = os.path.join(
        os.path.expanduser("~"),
        ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node",
    )
    bundled_node = os.path.join(bundled_root, "bin", "node.exe")
    bundled_modules = os.path.join(bundled_root, "node_modules")
    if os.path.exists(bundled_node) and os.path.isdir(os.path.join(bundled_modules, "playwright")):
        command = [bundled_node, "-e", NODE_SCRIPT]
        pnpm_modules = glob.glob(os.path.join(bundled_modules, ".pnpm", "*", "node_modules"))
        env["NODE_PATH"] = os.pathsep.join(
            [bundled_modules, *pnpm_modules, env.get("NODE_PATH", "")]
        ).strip(os.pathsep)
    else:
        npx = shutil.which("npx.cmd") or shutil.which("npx")
        if not npx:
            raise RuntimeError("npx is required for real browser probing. Install Node.js/npm first.")
        command = [npx, "--yes", "--package", "playwright", "node", "-e", NODE_SCRIPT]
    try:
        proc = subprocess.run(
            command,
            input=json.dumps(input_payload, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=(input_payload.get("timeout_ms", 45000) / 1000) + 90,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("npx is required for real browser probing. Install Node.js/npm first.") from exc
    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"browser probe produced no JSON output: {stderr[:500]}")
    try:
        result = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"browser probe returned non-JSON output: {stdout[:500]}") from exc
    if proc.returncode != 0 and not result.get("error"):
        result["error"] = (proc.stderr or stdout)[:1000]
    return result


def probe_browser(cookie_file=None, auth_user=None, out_dir="output/browser_probe", headless=True,
                  channel=None, wait_ms=7000, timeout_ms=45000) -> dict:
    cookie_header = ""
    sapisid = ""
    if cookie_file:
        with open(cookie_file, "r", encoding="utf-8-sig", errors="replace") as handle:
            raw_cookie_input = handle.read()
            cookie_header, sapisid = normalize_cookie_input(raw_cookie_input)
    else:
        raw_cookie_input = ""

    os.makedirs(out_dir, exist_ok=True)
    account_prefix = _account_prefix(auth_user)
    url = f"https://gemini.google.com{account_prefix}/app"
    screenshot_path = os.path.abspath(os.path.join(out_dir, f"gemini_browser_{time.time_ns()}.png"))
    input_payload = {
        "url": url,
        "cookies": _cookie_input_to_playwright_cookies(raw_cookie_input, cookie_header),
        "cookie_urls": ["https://gemini.google.com", "https://accounts.google.com", "https://www.google.com"],
        "keyword_patterns": _keyword_pattern_specs(),
        "screenshot_path": screenshot_path,
        "headless": headless,
        "channel": channel,
        "wait_ms": wait_ms,
        "timeout_ms": timeout_ms,
        "user_agent": UA,
    }
    browser = _run_node_probe(input_payload)
    diagnostics = diagnose_cookie_header(cookie_header)
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "cookie_file_used": bool(cookie_file),
        "cookie_diagnostics": diagnostics,
        "has_sapisid": bool(sapisid),
        "browser": browser,
        "assessment": {
            "http_ok": browser.get("status") == 200,
            "web_ui_likely_logged_in": _assess_web_ui_login(browser, diagnostics),
            "accounts_signin_url": _is_google_signin_url(browser.get("final_url", "")),
            "web_tool_keywords_visible": {
                name: count
                for name, count in (browser.get("keyword_counts") or {}).items()
                if count
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run a sanitized real browser Gemini Web UI probe.")
    parser.add_argument("--config")
    parser.add_argument("--cookie-file")
    parser.add_argument("--auth-user")
    parser.add_argument("--proxy", help="Reserved for parity with other probes; browser proxy is not applied yet.")
    parser.add_argument("--out", default=os.path.join("output", "browser_probe", "report.json"))
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--channel", default=None, help="Playwright browser channel, e.g. msedge or chrome")
    parser.add_argument("--wait-ms", type=int, default=7000)
    parser.add_argument("--timeout-ms", type=int, default=45000)
    args = parser.parse_args()

    cfg_path = args.config or os.environ.get("GEMINI_WEB2API_CONFIG") or find_config()
    if cfg_path:
        load_config(cfg_path)
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file
    cookie_file = _effective_cookie_file(args.cookie_file)
    if args.auth_user is not None:
        CONFIG["auth_user"] = args.auth_user
    if args.proxy:
        CONFIG["proxy"] = args.proxy

    out_path = os.path.abspath(args.out)
    report = probe_browser(
        cookie_file=cookie_file,
        auth_user=args.auth_user,
        out_dir=os.path.dirname(out_path),
        headless=not args.headed,
        channel=args.channel,
        wait_ms=args.wait_ms,
        timeout_ms=args.timeout_ms,
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps({
        "report_path": out_path,
        "status": report["browser"].get("status"),
        "title": report["browser"].get("title"),
        "web_ui_likely_logged_in": report["assessment"]["web_ui_likely_logged_in"],
        "keyword_counts": report["assessment"]["web_tool_keywords_visible"],
        "screenshot_path": report["browser"].get("screenshot_path"),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
