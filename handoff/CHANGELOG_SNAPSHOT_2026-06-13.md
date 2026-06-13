# Change Snapshot - 2026-06-13

This snapshot summarizes the repository state for handoff. It is not a release changelog; it is an operator/AI transfer note.

## Repository State

- Branch: `main`
- Current upstream/origin reference: `https://github.com/Sophomoresty/gemini-web2api.git`
- User fork remote: `xiaoli` -> `https://github.com/xiaoli0412/g2api.git`
- Tracked files at snapshot time: 241 before adding this handoff package.
- Main expanded code areas: `gemini_web2api/`, `gui/`, `native/`, `extension/`, `tests/`, docs.

## Major Capability Areas Added Over Upstream Baseline

- Multi-protocol API compatibility:
  - OpenAI chat completions
  - OpenAI Responses API
  - Anthropic Messages compatibility
  - Google Gemini generateContent compatibility
- Web dashboard and admin APIs:
  - request/response detail logging
  - config update controls
  - cookie diagnostics and import
  - proxy import, health, groups, account binding
  - token and model visibility
- Gemini Web reverse-engineering support:
  - BL/XSRF discovery
  - source probe
  - HAR analyzer
  - browser cookie extraction/probing
  - multimodal probe variants
- Model and web-feature registry:
  - core Gemini aliases
  - thinking/search suffixes
  - image/video/music/TTS/deep-research/canvas/photos/library/notebook aliases
- Artifact and media handling:
  - code/data-url materialization
  - `/artifacts/...` download serving
  - generated media URL detection and rewrite hooks
- Desktop and packaging:
  - native C++/WinUI shell
  - Rust supervisor
  - PyQt fallback
  - installer/build scripts and specs
- Test coverage:
  - static UI tests
  - server/API tests
  - cookie/proxy tests
  - request-detail tests
  - native source/layout tests
  - artifact/media tests

## Latest Verification

```text
python -m pytest
200 passed in 20.56s
```

Real-network evidence is under `handoff/evidence/` and was sanitized before being committed.

## Handoff Artifacts Added

Native release binary folder:

```text
handoff/artifacts/native-x64-release/Gemini2API.WinUI.exe
handoff/artifacts/native-x64-release/gemini2api-supervisor.exe
handoff/artifacts/native-x64-release/Microsoft.Web.WebView2.Core.dll
handoff/artifacts/native-x64-release/Microsoft.WindowsAppRuntime.Bootstrap.dll
handoff/artifacts/native-x64-release/Assets/gemini-icon.png
```

Launch script copies:

```text
handoff/scripts/run-api.bat
handoff/scripts/run-gui.bat
handoff/scripts/run-gui-pyqt.bat
handoff/scripts/run-docker.bat
```

Sanitized evidence:

```text
handoff/evidence/live_retest_after_restart.sanitized.json
handoff/evidence/real_latency_probe_20260609.sanitized.json
handoff/evidence/original_10009_core_probe_20260609.sanitized.json
handoff/evidence/ide_protocol_real_verify_after_tool_fix_20260609.sanitized.json
handoff/evidence/ide_stream_tool_live_20260609.sanitized.json
handoff/evidence/media_endpoints_live_20260609.sanitized.json
handoff/evidence/multimodal_real_verify_after_restart.sanitized.json
handoff/evidence/lan_responses_upload_verify_8081.sanitized.json
handoff/evidence/artifact_media_real_checks_8081.sanitized.json
handoff/evidence/real_model_port_matrix_8081.sanitized.json
handoff/evidence/manifest.json
```

## Important Interpretation

Passing HTTP status is not enough for this project. The user explicitly wants semantic real checks:

- For text models, verify the answer content for `Who are you` and `1+1=?`.
- For streaming, verify SSE chunks and final usage.
- For tool/IDE use, verify tool calls are actually emitted when expected.
- For uploads, verify whether Gemini really saw the uploaded content, not only a fallback note.
- For media, verify whether a real downloadable image/video/audio file was returned and saved locally.

## Current Red Lines

- Do not remove the expanded local features just because upstream lacks them.
- Do not call image/video/audio endpoints fully working unless evidence includes saved artifacts.
- Do not delete `/v1/messages`; it is Anthropic protocol compatibility for IDE/client use.
- Do not publish cookies, proxy subscription secrets, or live API keys.
- Keep `8081` as the main local test port and keep `10009` available for upstream comparison when needed.
