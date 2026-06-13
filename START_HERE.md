# Gemini2API Entry Index

Open this file first when you enter the repository.

## Main entry points

1. API server
   `python -m gemini_web2api`

2. Windows desktop shell (native C++/WinUI 3)
   `run-gui.bat`

3. Desktop shell CLI mode
   `python app.py --cli`

4. Web dashboard
   `http://localhost:8081/dashboard`

5. Docker local run
   `docker compose -f docker-compose.local.yml up -d`

6. Native EXE build
   `python build.py`
   or double-click `build.bat`

## Root scripts

- `run-api.bat`
- `run-gui.bat`: starts the native C++/WinUI shell
- `run-gui-pyqt.bat`: emergency legacy fallback only; not the normal desktop app
- `run-docker.bat`
- `open-dashboard.bat`
- `build.bat`

## Important paths

- `gemini_web2api/`: core service
- `gemini_web2api/dashboard.html`: high-end web operations console
- `native/Gemini2API.WinUI/`: native C++/WinUI 3 desktop shell
- `app.py`: legacy customtkinter shell
- `gui_app.py`: legacy PyQt fallback source, kept for compatibility
- `extension/`: Edge extension
- `config.example.json`: config template
- `build/native/x64/Release/Gemini2API.WinUI.exe`: native WinUI EXE

## Dashboard modes

- Open `gemini_web2api/dashboard.html` directly for offline preview mode
- Open `http://localhost:8081/dashboard` for live management mode
