# Gemini2API.WinUI

C++/WinUI 3 native Windows shell for Gemini2API.

This directory contains the active Windows 11 shell implementation: a C++/WinRT entry point, runtime WinUI controls, native pages, a backend process wrapper, and a WinHTTP client. The current Windows workspace builds `x64|Release` through the scripted MSBuild entry point for normal use.

## Target Stack

- C++/WinRT
- Windows App SDK / WinUI 3
- Mica main window material
- Acrylic for transient surfaces
- Windows 11 `NavigationView`, `CommandBar`, `InfoBar`, `ToggleSwitch`, `ComboBox`, segmented controls, and list/table layouts
- Runtime C++/WinRT control construction for the active shell; XAML files are kept as visual source references, not compiled markup.

## Pages

- Home
- Server
- Cookies
- Streaming
- Models
- Logs
- Settings

## Backend Integration

The shell calls a `BackendProcess` service that launches:

```powershell
python -m gemini_web2api --config <config> --port <port>
```

Then a `BackendClient` uses local HTTP endpoints defined in `../contracts/backend-api.md`.

## Build Prerequisites

- Visual Studio 2022 Build Tools or Visual Studio 2022
- Windows 11 SDK
- Windows App SDK
- C++/WinRT tooling
- NuGet package restore for `Microsoft.WindowsAppSDK`, `Microsoft.Web.WebView2`, and `Microsoft.Windows.CppWinRT`

The current pinned packages are:

- `Microsoft.WindowsAppSDK` `2.1.3`
- Windows App SDK transitive packages pinned to the versions declared by `Microsoft.WindowsAppSDK` `2.1.3`
- `Microsoft.Web.WebView2` `1.0.3967.48`
- `Microsoft.Windows.CppWinRT` `3.0.260520.1`

## Local Verification

Fast source and package checks:

```powershell
..\scripts\verify-all-native.ps1
..\scripts\verify-native-layout.ps1
..\scripts\verify-winui-markup.ps1
..\scripts\verify-winui-project.ps1
..\scripts\verify-native-source.ps1
..\scripts\verify-rust-source.ps1
..\scripts\verify-nuget-packages.ps1
..\scripts\smoke-backend.ps1
```

Build and real-window verification:

```powershell
..\scripts\restore-winui-packages.ps1 -BootstrapNuGet
..\scripts\bootstrap-msvc-buildtools.ps1
..\scripts\build-winui.ps1
..\scripts\verify-winui-runtime.ps1
..\scripts\verify-all-native.ps1 -RunVisual
```

`verify-winui-runtime.ps1` starts the real executable from `build\native\x64\Release`, waits for a visible WinUI top-level window, captures a PNG to `output\native-visual`, writes a JSON metrics sidecar, and asserts that the capture has a dark Windows 11 surface, visible system blue accent pixels, foreground text/icon pixels, and enough color variation to reject blank or broken renders.

Use `..\scripts\build-winui.ps1 -Configuration Debug` only when attaching a debugger. The default Release path is the performance baseline for real UI testing.

The project remains unpackaged so it can stay lightweight for a local management tool. If runtime launch fails while build succeeds, check the Windows App SDK runtime deployment on the target machine.
