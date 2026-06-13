# Backend Contract

The native shell supervises the existing Python backend. It should not import Python modules directly; it should launch the backend process and communicate through local HTTP.

## Process

Default launch command:

```powershell
python -m gemini_web2api --config <absolute-config-path> --port <port>
```

The supervisor should:

- allocate or accept a local port,
- set a config path,
- start the process without a visible console window in release builds,
- read stdout/stderr into the native log view,
- terminate the process on user request,
- verify shutdown and avoid orphaned processes.

## Readiness

Poll `GET /` until it returns status 200 with JSON.

Expected fields include:

- `status`
- `version`
- `models`
- `has_cookie`

## Endpoints Used by the Native Shell

### Status

- `GET /`
- `GET /v1/models`
- `GET /admin`
- `GET /admin/stats`

### Configuration

- `GET /api/config`
- `POST /api/config`

### Cookies

- `GET /api/cookie/status`
- `POST /api/cookie/refresh`
- `POST /api/cookie/push`
- `POST /api/cookie/start`
- `POST /api/cookie/stop`
- `GET /admin/cookie`
- `POST /admin/cookie`
- `DELETE /admin/cookie`

## Error Handling

The native shell should show:

- backend executable not found,
- port unavailable,
- readiness timeout,
- invalid config JSON,
- backend exited unexpectedly,
- HTTP endpoint returned non-200.

Errors should be surfaced through Windows-style `InfoBar` UI, not modal dialogs except for destructive actions.

## Rust Supervisor Prototype

The Rust prototype intentionally stays small and JSON-first:

```powershell
gemini2api-supervisor probe <port> [path]
gemini2api-supervisor status <port>
gemini2api-supervisor start <python> <config> <port> [timeout-seconds]
gemini2api-supervisor run <python> <config> <port> [timeout-seconds]
```

`status` probes `/`, `/v1/models`, `/admin`, and `/admin/stats`. `start` is currently smoke-test mode: it starts the backend, waits for readiness, prints a JSON report, then terminates the child process so test runs do not leave orphaned services. `run` keeps the backend process alive after readiness and prints an exit report when the child process exits.

The supervisor intentionally avoids third-party Rust crates for its local HTTP health checks. This keeps the helper small and lets `cargo check` run before a full MSVC linker setup is available.

Rust validation can run without changing the system PATH:

```powershell
native\scripts\check-supervisor.ps1 -BootstrapRust
```
