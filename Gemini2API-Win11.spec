# Legacy PyInstaller spec guard.
#
# Win11 native WinUI builds are produced by the C++/WinUI project, not PyInstaller:
#   python build.py
#   native\scripts\build-winui.ps1

raise SystemExit(
    "Gemini2API-Win11.spec would build the legacy PyQt shell, not the native WinUI app. "
    "Use 'python build.py' for the C++/WinUI build."
)
