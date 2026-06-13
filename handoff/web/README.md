# Web Management UI

There is no Vue/Vite project in this repository. The management console is the single file:

```text
gemini_web2api/dashboard.html
```

This directory contains a committed handoff copy:

```text
handoff/web/dashboard.html
```

Use the source file for development. Use this copy only as transfer evidence or for quick comparison if another environment loses the UI.

Expected runtime URLs:

```text
http://localhost:8081/dashboard
http://localhost:8081/
```

If a server shows only plain JSON/text, check:

1. The browser is visiting `/dashboard` or `/`.
2. `gemini_web2api/dashboard.html` exists on the server.
3. The installed Python package includes `dashboard.html`.
4. The PyInstaller build includes `gemini_web2api/dashboard.html`.
