# gemini-web2api

<p align="center">
  <img src="logo.png" width="200" alt="gemini-web2api logo">
</p>

[中文文档](README_CN.md)

Quick index: see `START_HERE.md`

Convert Google Gemini's web interface into an OpenAI-compatible API. Zero cost, cross-platform, single file. Desktop shell and UI refresh by xiaoliACG.

## Features

- **Optional API Keys**: no auth when `api_keys` is empty, OpenAI-style Bearer auth when configured
- **OpenAI Compatible**: Drop-in replacement for `/v1/chat/completions` and `/v1/models`
- **Tool Calling**: Full function calling support (OpenAI format)
- **Multiple Models**: Flash, Flash Thinking (20k+ char output), Pro, Auto, Lite
- **Thinking Depth**: Adjustable via `-think=N` suffix (0=deepest, 4=shallowest)
- **Web Search**: Built-in internet access (Gemini's native search)
- **Cross-Platform**: Pure Python, single optional dependency (`httpx` for streaming)
- **Streaming**: SSE streaming support via `httpx`
- **Codex CLI**: Responses API (`/v1/responses`) for OpenAI Codex integration
- **Gemini CLI**: Google native API (`/v1beta/models`) for Gemini CLI compatibility

## Quick Start

```bash
pip install -r requirements.txt
python -m gemini_web2api
```

Windows desktop shell (native C++/WinUI 3):

```bash
run-gui.bat
```

The launcher builds `build/native/x64/Release/Gemini2API.WinUI.exe` when it is missing, then starts the native shell. The Python UI files remain only as legacy fallbacks; the normal app surface is WinUI.

CLI shell mode:

```bash
python app.py --cli
```

Legacy PyQt files are kept only as an emergency compatibility fallback. Use `run-gui.bat` for the Windows desktop app.

Server starts at `http://localhost:8081/v1`.
Dashboard: `http://localhost:8081/dashboard`

Root launcher scripts:

- `run-api.bat`
- `run-gui.bat` - native C++/WinUI desktop shell
- `run-gui-pyqt.bat` - emergency legacy fallback only
- `run-docker.bat`
- `open-dashboard.bat`
- `build.bat`

## Live Verification

Run a real network smoke test against Gemini Web with the validation prompt `Who are you`:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --source-probe
```

If your real Gemini Web URL uses an account prefix such as `https://gemini.google.com/u/1/app`, pass the same account index:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --auth-user 1 --source-probe
```

To include experimental Gemini Web tool aliases such as image, video, music/TTS, photos, notebooks, and deep-research models:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --auth-user 1 --skip-multimodal --include-web-tools
```

To verify the real browser UI state with the same cookie file:

```bash
python -m gemini_web2api.browser_probe --cookie-file cookie.txt --auth-user 1 --out output/browser_probe/report.json
```

The report is written under `output/` and separates `pass`, `fail`, and `limited` results. Use `--strict` to fail on hard failures, or `--strict-limited` if experimental/limited features such as multimodal handoff must also fail the run. The capability matrix is also available at:

```bash
curl http://localhost:8081/api/capabilities
```

To analyze a browser HAR as auxiliary evidence without leaking cookies or prompts:

```bash
python -m gemini_web2api.har_analyze browser.har --out output/har_analysis.json
```

To specifically probe Gemini Web file-reference payload variants in the real upstream environment:

```bash
python -m gemini_web2api.multimodal_probe --cookie-file cookie.txt --auth-user 1 --out output/multimodal_probe.json
```

To fetch the current logged-in Gemini Web page and JavaScript assets with GET-only requests and record exposed feature keywords:

```bash
python -m gemini_web2api.web_probe --cookie-file cookie.txt --auth-user 1 --out output/web_probe.json
```

## Client Configuration

### Cherry Studio / ChatBox / any OpenAI client

| Field | Value |
|-------|-------|
| Base URL | `http://localhost:8081/v1` |
| API Key | any `api_keys` value from `config.json`; anything if not configured |
| Model | `gemini-3.5-flash-thinking` |

### curl

```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"Hello!"}]}'
```

### OpenAI Python SDK

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8081/v1", api_key="sk-your-key")
resp = client.chat.completions.create(
    model="gemini-3.5-flash-thinking",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)
print(resp.choices[0].message.content)
```

### Gemini CLI

```bash
export GEMINI_API_KEY=none
export GOOGLE_GEMINI_BASE_URL=http://localhost:8081
gemini
```

Supports Google native API endpoints:
- `GET /v1beta/models` — list models
- `POST /v1beta/models/{model}:generateContent` — non-streaming
- `POST /v1beta/models/{model}:streamGenerateContent` — streaming (SSE)

## Available Models

| Model | Description | Output |
|-------|-------------|--------|
| `gemini-3.5-flash` | Fast general-purpose | ~12k chars |
| `gemini-3.5-flash-thinking` | Deep thinking, longest output | **~20k chars** |
| `gemini-3.5-flash-thinking-lite` | Adaptive thinking depth | ~15k chars |
| `gemini-3.1-pro` | Pro (needs cookie for real routing) | ~12k chars |
| `gemini-auto` | Auto model selection | varies |
| `gemini-flash-lite` | Lightweight fast | ~10k chars |
| `gemini-3.1-flash-lite` / `3.1-flash-lite` | Gemini Web UI Flash-Lite alias | ~10k chars |

### Gemini Web Tool Aliases

These aliases follow names observed in Gemini Web source/HAR. They are callable by model name or suffix, but a feature is only fully supported when live verification returns a real artifact/result.

| Feature | Model names / suffixes | Status |
|---------|------------------------|--------|
| Create images | `nano-banana-2`, `nano-banana-pro`, `gemini-2.5-flash-image`, `gemini-2.5-flash-image-preview`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview-11-2025`, `imagen-3.0-generate-001`, `imagen-3.0-generate-002`, `imagen-4.0-generate-001`, or suffix `-image` / `-images` / `-create-image` | experimental |
| Create videos | `omni`, `veo-2.0-generate-001`, or suffix `-video` / `-videos` / `-create-video` | experimental |
| Deep research | `gemini-deep-research`, or suffix `-deep-research` / `-research` | experimental |
| Canvas artifacts | `gemini-canvas`, or suffix `-canvas` | supported as code/HTML artifact extraction |
| Music / TTS | `lyria-3`, `gemini-2.5-flash-preview-tts`, or suffixes `-music`, `-tts`, `-speech`, `-audio` | limited |
| Photos / Library / Notebooks | `gemini-photos`, `google-photos`, `gemini-library`, `gemini-notebook`, `notebooklm`, or suffixes `-photo`, `-photos`, `-library`, `-notebook` | limited |

Source-discovered text/pro aliases are also registered: `gemini-2.5-flash-preview-04-17`, `gemini-2.5-flash-preview-05-20`, `gemini-2.5-flash-preview-09-2025`, `gemini-3-flash-preview`, and `gemini-advanced`.

OpenAI-style media routes are available too:

- `POST /v1/images/generations` with `{ "model": "nano-banana-2", "prompt": "..." }`
- `POST /v1/videos/generations` with `{ "model": "omni", "prompt": "..." }`
- `POST /v1/audio/speech` with `{ "model": "gemini-2.5-flash-preview-tts", "input": "..." }`

These routes return `data` only when Gemini Web returns a real media artifact. Otherwise they return the upstream text plus `web_feature.runtime_status = "limited"`.

### Thinking Depth

Append `-think=N` to any thinking/search model name:

```
gemini-3.5-flash-thinking-think=0   # deepest (default)
gemini-3.5-flash-thinking-think=2   # medium
gemini-3.5-flash-thinking-think=4   # shallowest
gemini-3.5-flash-thinking-standard  # Gemini Web UI Standard level
gemini-3.5-flash-thinking-extended  # Gemini Web UI Extended level
```

Search uses the `-search` suffix:

```
gemini-3.5-flash-search
gemini-3.5-flash-thinking-search
gemini-3.1-pro-search
```

## Optional: Cookie for Pro

Anonymous access works for all models, but `gemini-3.1-pro` routes to Flash without authentication. To get real Pro routing, you need a **Gemini Advanced (paid subscription)** account cookie:

```bash
python -m gemini_web2api --cookie-file cookie.txt
```

### How to get cookies

1. Open Chrome, go to [gemini.google.com](https://gemini.google.com) and sign in with a **Gemini Advanced** Google account
2. Open DevTools (F12) → Application → Cookies → `https://gemini.google.com`
3. Copy these cookie values: `SID`, `HSID`, `SSID`, `APISID`, `SAPISID`, `__Secure-1PSID`
4. Create `cookie.txt` in this format:

```
SID=your_sid_value; HSID=your_hsid_value; SSID=your_ssid_value; APISID=your_apisid_value; SAPISID=your_sapisid_value; __Secure-1PSID=your_1psid_value
```

Or use the JSON format:
```json
{"cookie": "SID=xxx; HSID=xxx; SSID=xxx; APISID=xxx; SAPISID=xxx; __Secure-1PSID=xxx", "sapisid": "your_sapisid_value"}
```

**Alternative (browser extension)**: You may use a single-line `Cookie` header, the JSON format above, or a browser-exported tabular cookie file. The loader keeps Gemini-relevant `google.com` / `gemini.google.com` cookies and extracts `SAPISID` automatically.

For full Gemini Web UI/tool behavior, not just backend text calls, your export should usually include `__Secure-1PSID` or `__Secure-3PSID` from the same logged-in browser session. You can check this without printing values:

```bash
python -m gemini_web2api.cookie_diag cookie.txt
```

### Authenticated account path and XSRF token

If the signed-in Gemini page URL contains an account index, such as:

```
https://gemini.google.com/u/1/app/...
```

set `auth_user` to that index. Authenticated web requests may also require the page XSRF token. In the rendered Gemini page source, this token is exposed as `SNlM0e`; pass it as `xsrf_token` in `config.json`. The server sends it as the `at` form field.

Example:

```json
{
  "cookie_file": "/app/cookie.txt",
  "auth_user": "1",
  "xsrf_token": "AOOh0P...",
  "gemini_bl": "boq_assistant-bard-web-server_YYYYMMDD.xx_p0"
}
```

If authenticated requests return HTTP 400 with an `xsrf` error, refresh Gemini Web, update `xsrf_token`, and make sure `auth_user` matches the `/u/<index>/` part of the browser URL.

Pro routing requires **Gemini Advanced** (paid subscription). A free Google account cookie will authenticate but silently fall back to Flash.

To compare Gemini Web source in anonymous vs authenticated mode:

```bash
python -m gemini_web2api.source_probe --cookie-file cookie.txt --out gemini_source_probe
```

If you are already signed in locally, you can try browser cookies:

```bash
python -m gemini_web2api.source_probe --browser-cookie --out gemini_source_probe
```

## Configuration

Create `config.json` in the same directory:

```json
{
  "port": 8081,
  "host": "0.0.0.0",
  "retry_attempts": 3,
  "retry_delay_sec": 2,
  "request_timeout_sec": 180,
  "gemini_bl": "boq_assistant-bard-web-server_20260525.09_p0",
  "auth_user": null,
  "xsrf_token": null,
  "api_keys": ["sk-your-key"],
  "cookie_file": null,
  "proxy": null,
  "log_requests": true
}
```

When `api_keys` is `[]`, authentication is disabled. When one or more keys are set, `/v1/*` endpoints require `Authorization: Bearer <key>` or `x-api-key: <key>`.

## Docker

```bash
cp config.example.json config.json
docker build -t gemini-web2api .
docker run -d --name gemini-web2api -p 8081:8081 -v ./config.json:/app/config.json gemini-web2api
```

Or use Docker Compose:

```bash
cp config.example.json config.json
docker compose up -d
```

For the local compose file in this repo:

```bash
docker compose -f docker-compose.local.yml up -d
```

To mount a cookie file:

```bash
docker run -d --name gemini-web2api -p 8081:8081 -v ./config.json:/app/config.json -v ./cookie.txt:/app/cookie.txt gemini-web2api
```

Set `"cookie_file": "/app/cookie.txt"` in `config.json`.

> **Note**: If you get empty responses (`content: null`) with Docker's default bridge network, switch to host networking: `docker run --network host ...` or add `network_mode: host` in your compose file. This is caused by Gemini's upstream rejecting requests from certain Docker NAT IP ranges.

## Proxy

If you cannot access `gemini.google.com` directly (connection timeout), configure a proxy:

**Method 1: CLI argument**
```bash
python -m gemini_web2api --proxy http://127.0.0.1:7890
```

**Method 2: config.json**
```json
{"proxy": "http://127.0.0.1:7890"}
```

**Method 3: Environment variable** (auto-detected)
```bash
export HTTPS_PROXY=http://127.0.0.1:7890
python -m gemini_web2api
```

Works with Clash, V2Ray, Shadowsocks, or any HTTP proxy.

## Tool Calling

```python
resp = client.chat.completions.create(
    model="gemini-3.5-flash",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
        }
    }]
)
```

## Limitations

- **Experimental image/multimodal input**: The server can upload small files to Gemini Web's content-push service, but the final private Web `StreamGenerate` handoff may still be rejected by Google with `BardErrorInfo [1003]` even when a cookie is present. For stable file prompting, use Google's official Gemini API Files API with an API key.
- **Gemini Web tools are account/UI dependent**: Image/video/music/photos/notebook aliases are callable model names, but they may return `limited` unless the same browser login session has full Web UI cookies such as `__Secure-1PSID` or `__Secure-3PSID` and the upstream tool flow returns a real artifact.
- **Not real Pro/Ultra**: Without a paid subscription cookie, `gemini-3.1-pro` routes to the same Flash model. The "Pro" label is a UI preference, not a backend model switch.
- **Single-turn only**: Each request is an independent conversation. Multi-turn context is simulated by including previous messages in the prompt.
- **Rate limits**: Google may throttle high-frequency requests. The server retries automatically but sustained heavy use may be blocked.

## Requirements

- Python 3.8+
- `httpx` (`pip install httpx`) — used for streaming requests
- Network access to `gemini.google.com` (proxy/VPN may be needed in some regions)

## How It Works

This tool reverse-engineers Google Gemini's web StreamGenerate protocol. It sends requests to the same endpoint that the Gemini web app uses, converting between OpenAI's API format and Gemini's internal protobuf-like format.

The model selection is controlled by field `[79]` in the request payload, mapped from Gemini's frontend JavaScript source (`MODE_CATEGORY` enum).

## Acknowledgments

- Inspired by the open-source API proxy ecosystem

## License

MIT

---

## 致谢

本项目的开发 agent 能力由 [GenericAgent](https://github.com/lsdefine/GenericAgent) 提供。

### 🚩 友情链接

[![GenericAgent](https://img.shields.io/badge/Agent_Framework-GenericAgent-orange?style=for-the-badge&logo=github)](https://github.com/lsdefine/GenericAgent)
[![LinuxDo](https://img.shields.io/badge/社区-LinuxDo-blue?style=for-the-badge)](https://linux.do/)
