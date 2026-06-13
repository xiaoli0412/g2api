# Artifact Index

This folder stores handoff-safe build outputs that would otherwise be ignored under `build/`.

## Native x64 Release

Path: `handoff/artifacts/native-x64-release/`

Included:

- `Gemini2API.WinUI.exe`
- `gemini2api-supervisor.exe`
- WinUI/WebView2/WindowsAppRuntime side files needed by the current release output.
- `Assets/gemini-icon.png`

Not included:

- `.pdb` debug symbol files, because they are large and not needed for operator handoff.
- Intermediate compiler objects from `build/native/obj/`.

To rebuild from source, use the scripts under `native/scripts/`, especially `build-winui.ps1`, `build-supervisor.ps1`, and `verify-all-native.ps1`.
