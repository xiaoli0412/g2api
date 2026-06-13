# AI Handoff - Gemini2API

Date: 2026-06-13
Workspace: `D:\workspaces\2api\gemini2api`
Branch at handoff start: `main`
Upstream reference: `Sophomoresty/gemini-web2api`

## User Intent

The user wants this repository to remain a practical Gemini Web reverse-proxy/API compatibility project, not a minimal upstream clone. Preserve the expanded functionality already implemented here:

- OpenAI-compatible `/v1/chat/completions`, `/v1/models`, images/videos/audio helper endpoints.
- OpenAI Responses API `/v1/responses`.
- Anthropic/Claude Messages compatibility `/v1/messages`.
- Google Gemini-compatible `/v1beta/models/{model}:generateContent`.
- Web dashboard at `/dashboard` with config, request logs, proxy/cookie controls, token usage visibility, and diagnostics.
- Native Windows/WinUI shell and release artifacts.
- Cookie parsing, diagnostics, browser probing, source/HAR probing, proxy pool, request/response logging, artifact materialization.

Do not replace this repository with upstream. Upstream is useful as a baseline, but this repo is intentionally much larger.

## Current Verification

Latest local unit/static suite:

```text
python -m pytest
200 passed in 20.56s
```

Latest real API evidence copied into `handoff/evidence/`:

- `live_retest_after_restart.sanitized.json`: real `/v1/models`, chat, stream, Responses, Claude Messages, and Google generateContent checks.
- `real_model_port_matrix_8081.sanitized.json`: real model matrix for `Who are you` and `1+1=?` on port 8081.
- `original_10009_core_probe_20260609.sanitized.json`: upstream-original comparison service evidence.
- `ide_protocol_real_verify_after_tool_fix_20260609.sanitized.json`: IDE/LAN style protocol checks.
- `ide_stream_tool_live_20260609.sanitized.json`: stream/tool bridge evidence.
- `multimodal_real_verify_after_restart.sanitized.json`: upload/data-url fallback checks.
- `media_endpoints_live_20260609.sanitized.json`: image/video/audio endpoint checks.
- `artifact_media_real_checks_8081.sanitized.json`: artifact and media materialization checks.
- `lan_responses_upload_verify_8081.sanitized.json`: LAN Responses/upload probe.

Representative real responses already captured:

- `gemini-3.5-flash` + `Who are you` returned a Gemini identity answer.
- `gemini-3.5-flash` + `1+1=?` returned `1 + 1 = 2`.
- `gemini-3.5-flash-search` returned normal assistant text without leaking `<websearch>` control blocks.
- `/v1/responses`, `/v1/messages`, and `/v1beta/...:generateContent` returned client-compatible responses.
- Streaming emitted SSE chunks plus usage metadata.

## Current Runtime Policy

The user prefers restarting port `8081` before fresh verification, then opening any extra test ports separately. If a PID file disagrees with the actual listener, trust the actual listening process.

Known base URLs:

- Current enhanced service: `http://127.0.0.1:8081`
- Upstream reference service when used: `http://127.0.0.1:10009`

The user previously used API key `sk-100412`; do not publish it in external logs or new docs. Handoff evidence uses redacted keys.

## Architecture Map

- Core API server: `gemini_web2api/server.py`
- Gemini Web transport and parsing: `gemini_web2api/gemini.py`
- Model aliases/web feature registry: `gemini_web2api/models.py`
- OpenAI/Claude/Google request adapters: `gemini_web2api/adapters.py`, `gemini_web2api/tools.py`
- File upload and multimodal helpers: `gemini_web2api/multimodal.py`
- Generated file/artifact materialization: `gemini_web2api/artifact_store.py`
- Web dashboard: `gemini_web2api/dashboard.html`
- Admin/cookie/proxy operations: `gemini_web2api/admin.py`, `gemini_web2api/cookie_manager.py`, `gemini_web2api/proxy_builtin.py`
- Live probes and HAR/source analysis: `gemini_web2api/live_verify.py`, `gemini_web2api/har_analyze.py`, `gemini_web2api/source_probe.py`, `gemini_web2api/web_probe.py`
- Native Windows shell: `native/Gemini2API.WinUI/`
- Native supervisor: `native/supervisor-rs/`
- Python fallback GUI: `gui/`, `gui_app.py`

## Key Implemented Behaviors

- Model aliasing includes `gemini-3.5-flash`, thinking/search variants, 2.5 aliases, Pro aliases, image/video/audio/TTS/deep-research/canvas/library/notebook feature aliases.
- The default visible model list can expose experimental web-feature models via config.
- Tool bridge can coerce local-file refusal into compatible tool calls for IDE clients that expect tool use.
- Claude route is protocol compatibility, not a list of Claude models. Do not delete `/v1/messages`.
- Search control fallback strips internal-only routing text and retries without leaking control blocks.
- `BardErrorInfo [1003]` and `[1155]` are treated as non-retryable/file-handshake style failures to avoid long empty retry loops.
- Request logging splits request/response bodies, masks sensitive fields, and supports detailed traces for admin dashboard review.
- Artifact store can save data URLs/code artifacts and rewrite saved media URLs to local `/artifacts/...` download links.
- Proxy master switch exists; when proxy pool is unhealthy, keep a clear path to disable it.

## Native/EXE Handoff

Build output is normally ignored under `build/`, so the current release artifacts were copied into Git-tracked handoff storage:

- `handoff/artifacts/native-x64-release/Gemini2API.WinUI.exe`
- `handoff/artifacts/native-x64-release/gemini2api-supervisor.exe`
- Required WinUI/WebView2/WindowsAppRuntime side files in the same folder.
- App icon: `handoff/artifacts/native-x64-release/Assets/gemini-icon.png`

Debug symbols/PDBs were not copied because they are large and not required for operator handoff.

## Startup Helpers

Copies of ignored root scripts are committed in `handoff/scripts/`:

- `run-api.bat`: starts `python -m gemini_web2api`
- `run-gui.bat`: starts the native WinUI shell via `native/scripts/run-winui.ps1`
- `run-gui-pyqt.bat`: legacy Python UI fallback
- `run-docker.bat`: local Docker compose helper

Root-level originals remain available locally but are ignored by `.gitignore`.

## Known Risks / Next Work

- Media generation endpoints currently exist and return OpenAI-like shapes, but real image/video/audio generation is mostly `limited` in live evidence because upstream did not return downloadable artifacts. This must not be represented as fully solved.
- Some upload/multimodal tests show text-only fallback behavior such as `NOT_INSPECTED`; this means upload plumbing did not always hand the actual content to Gemini Web.
- LAN `/v1/responses` upload checks recorded failures when proxy pool had no healthy proxy. If proxy is enabled, healthy proxy routing must be verified before blaming model logic.
- Historical latency probe captured a long timeout for one `gemini-3.5-flash` math request, while later retests passed. Continue investigating request-level stalls, buffering, proxy pool state, and upstream Gemini Web throttling.
- `config.json` and `cookie.txt` are local operational files. Avoid propagating live secrets to external repos or public reports.
- Several generated `__pycache__` files are already tracked in history. They are not architecturally important; do not spend handoff time on them unless doing repository hygiene.

## Suggested Next AI Order

1. Re-run `python -m pytest`.
2. Restart port `8081`, then run real checks with `Who are you` and `1+1=?`.
3. Verify IDE clients against `/v1/chat/completions`, `/v1/responses`, and `/v1/messages` with streaming and tools enabled.
4. Focus on actual upload handoff: inspect whether Gemini Web receives file references or only text fallback.
5. Deep-dive media RPCs with browser/HAR evidence and make artifact download truly saved under `/artifacts/...`.
6. Only after core/IDE/upload stability, expand hidden web-feature models further.
