# Gemini2API Native Windows Shell Migration

## Goal

Replace the Python GUI shell with a Windows-native management application that matches Windows 11 system apps as closely as possible while preserving the existing Python API backend until it is safe to move specific management responsibilities into native code.

The first native shell must feel closer to Windows Settings, Task Manager, Microsoft Store, and notification flyouts than to a themed cross-platform toolkit. The default language is English, the layout uses Windows 11 sentence case, and the visual system is Mica-first with Acrylic reserved for transient surfaces and optional frosted background layers.

Official design sources used for this direction:

- Microsoft Mica guidance: https://learn.microsoft.com/en-us/windows/apps/design/style/mica
- Microsoft Acrylic guidance: https://learn.microsoft.com/en-us/windows/apps/design/style/acrylic
- Microsoft NavigationView guidance: https://learn.microsoft.com/en-us/windows/apps/design/controls/navigationview
- Microsoft command bar guidance: https://learn.microsoft.com/en-us/windows/apps/design/controls/command-bar
- Microsoft custom title bar guidance: https://learn.microsoft.com/en-us/windows/apps/develop/title-bar?tabs=winui3
- Microsoft typography guidance: https://learn.microsoft.com/en-us/windows/apps/design/style/typography
- Microsoft iconography guidance: https://learn.microsoft.com/en-us/windows/apps/design/style/icons

## Non-goals

- Do not rewrite the Gemini API request pipeline in the first phase.
- Do not remove the existing Python CLI or web dashboard.
- Do not rely on a webview as the primary UI if the goal is strict Windows 11 native fidelity.
- Do not create a native build that cannot honestly be verified on the current machine.

## Current Boundaries

The repository already has a working Python backend exposed through `python -m gemini_web2api`.

Important backend surfaces:

- `GET /` for status and available models.
- `GET /v1/models` for OpenAI-compatible model listing.
- `GET /admin` for admin endpoint discovery.
- `GET /admin/stats` for summary runtime state.
- `GET /admin/cookie`, `POST /admin/cookie`, `DELETE /admin/cookie` for cookie pool management.
- `POST /api/config` for config updates.
- `POST /api/cookie/refresh` for manual cookie refresh.

The native shell should treat the backend as a supervised local service at first. It starts the process, waits until the port is available, reads state through HTTP, writes configuration through existing endpoints or the JSON file, and terminates the process cleanly.

## Recommended Architecture

### Phase 1: C++/WinUI 3 Shell With Python Backend

Use C++/WinRT and Windows App SDK / WinUI 3 for the shell.

Responsibilities:

- Render the Windows-native UI:
  - `NavigationView` style left pane.
  - `CommandBar` for page commands.
  - Settings-style cards and rows.
  - `ToggleSwitch`, `ComboBox`, `NumberBox`, `InfoBar`, `ListView`.
  - Mica main window material and Acrylic transient surfaces.
- Start and stop the Python backend as a child process.
- Poll backend status and show health in the title area and Home page.
- Read and write configuration using `config.json` and existing HTTP endpoints.
- Open dashboard and extension folders.

This is the safest path because the high-risk Gemini compatibility layer remains untouched.

Current implementation entry point:

- `native/Gemini2API.WinUI/Gemini2API.WinUI.sln`
- `native/Gemini2API.WinUI/Gemini2API.WinUI.vcxproj`
- NuGet packages: `Microsoft.WindowsAppSDK` `2.1.3`, `Microsoft.Windows.CppWinRT` `3.0.260520.1`

### Phase 2: Rust Supervisor

Add a small Rust supervisor when the Rust toolchain is available.

Responsibilities:

- Port discovery and health checks.
- Process lifecycle management.
- Log streaming and retention.
- Config file validation.
- Optional Windows service integration later.

The C++/WinUI app can either call the Rust supervisor as a helper executable or use the same protocol contract directly.

### Phase 3: Selective Native Migration

Only after Phase 1 is stable:

- Move local-only management features into Rust.
- Keep network compatibility logic in Python unless there is a clear test-backed reason to port it.

## Native UI Shape

### Window

- Frameless or custom title bar matching Windows 11 caption button behavior.
- Main surface uses Mica.
- Optional Acrylic mode in settings for users who explicitly want a more translucent shell.
- 8 px window corner preference.
- Segoe UI Variable and Segoe Fluent Icons.

### Navigation

- Windows Settings-like left navigation that can collapse to a compact icon rail.
- Identity block at the top.
- Text navigation rows with icon + label.
- Active indicator uses the system accent color.

### Pages

Home:

- Runtime health card.
- Backend endpoint card.
- Quick actions command area.
- Recent logs or admin summary.

Server:

- Settings cards for network, API, proxy, and proxy pool.
- Numeric fields use native number input semantics.
- Save command stays in a command bar.

Cookies:

- Cookie source and auto refresh settings.
- Cookie pool list.
- Refresh and browser login commands.

Streaming:

- Streaming mode settings card.
- Fake stream delay card.

Models:

- Model aliases, token accounting, and copyable test command rows without a search box.

Settings:

- App behavior.
- Window material.
- Background image / dynamic layer.
- About section.

The optional background image layer is disabled by default. It keeps the useful StarlightGUI idea of user-selected visual personalization, but avoids gradients, watermarks, oversized decorative typography, and non-Windows visual effects.

## Testing Strategy

Tests must happen in layers.

1. Existing Python tests continue to run.
2. Native toolchain detection script must clearly report missing C++/Rust dependencies.
3. Backend smoke test starts `python -m gemini_web2api` on a temporary port, waits for readiness, calls `/`, `/v1/models`, `/admin`, and `/admin/stats`, then terminates the process.
4. Native build tests only run when Visual Studio Build Tools / Windows App SDK or Rust are installed.
5. GUI smoke tests should verify that the native shell starts, launches the backend, detects health, and shuts down without orphaning processes.

## Acceptance Criteria

- Existing Python API tests pass.
- Backend smoke script passes on a random local port.
- Native source layout is isolated under `native/` and does not break existing Python startup.
- If native toolchains are missing, verification reports that cleanly instead of failing ambiguously.
- The first compiled native shell, once toolchains are installed, can launch and stop the Python backend without changing the backend implementation.
