# Legacy PyInstaller spec guard.
#
# The normal Windows desktop app is the native WinUI / C++ shell:
#   python build.py
#   run-gui.bat
#
# To build the old PyQt fallback intentionally, use:
#   python build.py --legacy-pyqt

raise SystemExit(
    "Gemini2API.spec is no longer the default Windows build path. "
    "Use 'python build.py' for the native WinUI / C++ shell, or "
    "'python build.py --legacy-pyqt' for the legacy PyQt fallback."
)
