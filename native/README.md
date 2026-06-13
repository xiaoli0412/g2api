# Gemini2API Native Windows Shell

This directory contains the staged native Windows migration.

The migration is intentionally split so the existing Python backend remains stable while the GUI moves toward a real Windows 11 native shell.

## Layout

- `Gemini2API.WinUI/` - C++/WinUI 3 shell source and project skeleton.
- `supervisor-rs/` - Rust supervisor prototype for process and health management.
- `contracts/` - Backend API and process lifecycle contract.
- `scripts/` - Toolchain and smoke-test scripts that can run before native build tools are installed.

## Recommended Path

1. Keep `python -m gemini_web2api` as the backend.
2. Build the Windows shell in C++/WinUI 3.
3. Use the native shell to start, stop, and monitor the Python backend.
4. Add the Rust supervisor when the Rust toolchain is available.
5. Move only low-risk local management features into Rust after the shell is stable.

The Rust supervisor already defines `probe`, `status`, `start` smoke mode, and `run` long-running mode. The WinUI shell can either call the C++ process wrapper directly or delegate lifecycle control to the Rust helper once it is built.

## Why Not Tauri First?

Tauri is lightweight, but the UI is still rendered in a WebView. The target for this project is strict Windows 11 native fidelity, so WinUI 3 is the primary shell technology.

## Current Environment Note

This workspace now has a working native path on Windows: the C++/WinUI 3 shell builds as `x64|Release` for normal use, the Rust supervisor builds and tests, and the Python backend smoke tests still run through the existing backend. Re-run the toolchain check when moving to another machine:

```powershell
.\native\scripts\check-toolchain.ps1
```

The Python backend smoke test remains the API compatibility guardrail:

```powershell
.\native\scripts\smoke-backend.ps1
```

The source, package, native build, and optional real-window visual checks are:

```powershell
.\native\scripts\verify-all-native.ps1
.\native\scripts\verify-all-native.ps1 -BuildWhenPossible
.\native\scripts\verify-all-native.ps1 -RunVisual
.\native\scripts\verify-native-layout.ps1
.\native\scripts\verify-winui-markup.ps1
.\native\scripts\verify-winui-project.ps1
.\native\scripts\verify-native-source.ps1
.\native\scripts\verify-rust-source.ps1
.\native\scripts\verify-nuget-packages.ps1
.\native\scripts\verify-winui-runtime.ps1
```

`verify-winui-runtime.ps1` launches the real WinUI executable, waits for a visible top-level window, captures a PNG under `output\native-visual`, and fails if the capture is blank, not dark enough for a Windows 11 shell, missing the system blue accent, or missing foreground text/icon pixels.

## Native UI Direction

The shell is intentionally Windows-native rather than a themed Python or WebView UI:

- C++/WinRT + WinUI 3 for the app surface.
- `MicaBackdrop` for the main window.
- `DesktopAcrylicBackdrop` fallback and Acrylic-style transient surfaces.
- Windows 11 `NavigationView`, `CommandBar`, `InfoBar`, `ToggleSwitch`, `NumberBox`, `ListView`, segmented controls, and `MenuFlyout`.
- English, sentence-case UI copy following Windows system app tone.
- Optional personal background image layer, disabled by default, for the Starlight-style custom-photo idea without gradients or decorative overlays.

## Build Entry Point

Open or build:

```powershell
native\Gemini2API.WinUI\Gemini2API.WinUI.sln
```

NuGet packages are pinned in `native\Gemini2API.WinUI\packages.config` and restored into the solution-level `packages` folder.

Build entry points:

```powershell
.\native\scripts\restore-winui-packages.ps1 -BootstrapNuGet
.\native\scripts\check-supervisor.ps1 -BootstrapRust
.\native\scripts\bootstrap-msvc-buildtools.ps1
.\native\scripts\build-winui.ps1
.\native\scripts\build-supervisor.ps1
```

Use `.\native\scripts\build-winui.ps1 -Configuration Debug` only for debugger sessions. Real UI testing and day-to-day use should run the Release build.
