# Core Asset Index - 2026-06-13

This file points the next AI/IDE to the exact assets that matter. There is no Vue/Vite dashboard project in this repository. The web management UI is a single native HTML/CSS/JS console.

## Web Management UI

Primary source:

```text
gemini_web2api/dashboard.html
```

Handoff copy:

```text
handoff/web/dashboard.html
```

Runtime URL:

```text
http://localhost:8081/dashboard
http://localhost:8081/
```

The root URL serves the dashboard for browser `Accept: text/html` requests and still serves JSON status for API-style `Accept: application/json` requests.

## API Server Core

```text
gemini_web2api/server.py
gemini_web2api/gemini.py
gemini_web2api/models.py
gemini_web2api/tools.py
gemini_web2api/adapters.py
gemini_web2api/sse.py
gemini_web2api/stats.py
```

Key routes:

```text
/v1/chat/completions
/v1/responses
/v1/messages
/v1/models
/v1/images/generations
/v1/videos/generations
/v1/audio/speech
/v1beta/models/{model}:generateContent
/dashboard
/api/dashboard
/api/config
/api/cookie/status
/api/proxy/status
/artifacts/{file}
```

## Upload, Artifact, Cookie, Proxy Logic

```text
gemini_web2api/multimodal.py
gemini_web2api/artifact_store.py
gemini_web2api/cookies.py
gemini_web2api/cookie_manager.py
gemini_web2api/playwright_cookie.py
gemini_web2api/proxy_builtin.py
gemini_web2api/admin.py
```

## Probe and Evidence Tools

```text
gemini_web2api/live_verify.py
gemini_web2api/source_probe.py
gemini_web2api/web_probe.py
gemini_web2api/har_analyze.py
gemini_web2api/browser_probe.py
gemini_web2api/multimodal_probe.py
```

## Desktop and EXE Assets

Native WinUI source:

```text
native/Gemini2API.WinUI/
native/supervisor-rs/
native/scripts/
```

Committed handoff binaries:

```text
handoff/artifacts/native-x64-release/Gemini2API.WinUI.exe
handoff/artifacts/native-x64-release/gemini2api-supervisor.exe
handoff/artifacts/native-x64-release/Microsoft.Web.WebView2.Core.dll
handoff/artifacts/native-x64-release/Microsoft.WindowsAppRuntime.Bootstrap.dll
```

Python/PyInstaller EXE packaging:

```text
Gemini2API-exe.spec
launcher.py
app.py
```

The PyInstaller spec now explicitly includes:

```text
gemini_web2api/dashboard.html -> gemini_web2api/dashboard.html
```

Python package builds now include the dashboard through:

```text
pyproject.toml [tool.setuptools.package-data]
```

## Launchers For Handoff

```text
handoff/launchers/start-api.cmd
handoff/launchers/open-dashboard.cmd
handoff/launchers/start-native-winui.cmd
handoff/launchers/start-docker.cmd
```

Root scripts still exist locally, but some are ignored by `.gitignore`, so the handoff launchers are the safer cross-IDE entry points.
