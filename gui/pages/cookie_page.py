"""Cookie management page."""

import threading

from gui.components import FluentButton, FluentToggle
from .page_utils import Page


class CookiePage(Page):
    def __init__(self, parent=None):
        super().__init__(parent, "cookie")
        self._create_ui()

    def _create_ui(self):
        cfg = self.main_window.config
        self.title("cookie")
        source = self.card("cookie_source")
        self.source_combo = self.combo_row(source, "cookie_source", ["auto", "playwright"], cfg.get("cookie_source", "auto"))
        self.auto_toggle = FluentToggle(cfg.get("auto_cookie", False))
        row = self.row(source, "auto_extract")
        row.addWidget(self.auto_toggle)
        row.addStretch()

        refresh = self.card("auto_refresh")
        self.interval_input = self.input_row(refresh, "interval", cfg.get("auto_refresh_hours") or "")

        ext = self.card("edge_ext")
        self.helper(self.t("edge_ext_desc"), ext.layout)
        open_btn = FluentButton(self.t("open_ext"))
        open_btn.clicked.connect(self.main_window._open_extension)
        ext.layout.addWidget(open_btn)

        actions = self.card("actions")
        refresh_btn = FluentButton(self.t("refresh_now"))
        login_btn = FluentButton(self.t("browser_login"))
        save_btn = FluentButton(self.t("save"))
        refresh_btn.clicked.connect(self._refresh_cookie)
        login_btn.clicked.connect(self._browser_login)
        save_btn.clicked.connect(self._save_config)
        actions.layout.addWidget(refresh_btn)
        actions.layout.addWidget(login_btn)
        actions.layout.addWidget(save_btn)
        self.status = self.helper("", actions.layout)
        self.root.addStretch()

    def _save_config(self):
        cfg = self.main_window.config
        cfg["cookie_source"] = self.source_combo.currentText()
        cfg["auto_cookie"] = self.auto_toggle.isChecked()
        value = self.interval_input.text().strip()
        cfg["auto_refresh_hours"] = int(value) if value else None
        self.main_window.save_config()
        self.main_window.toast(self.t("saved"))

    def _refresh_cookie(self):
        self.status.setText(self.t("refreshing"))
        def run():
            try:
                from gemini_web2api.cookie_manager import manual_refresh
                result = manual_refresh()
                text = f"{'OK' if result.get('success') else 'FAIL'}: {result.get('status', '')}"
            except Exception as exc:
                text = str(exc)
            self.main_window.post_ui(lambda: self.status.setText(text))
        threading.Thread(target=run, daemon=True).start()

    def _browser_login(self):
        def run():
            try:
                from gemini_web2api import playwright_cookie
                from gemini_web2api.cookie_manager import write_cookie_file
                if not playwright_cookie.is_playwright_available():
                    self.main_window.post_ui(lambda: self.main_window.toast(self.t("playwright_missing")))
                    return
                self.main_window.post_ui(lambda: self.main_window.toast(self.t("opening_browser")))
                result = playwright_cookie.launch_browser_login()
                if result.get("success"):
                    write_cookie_file(result["cookies"], result.get("sapisid", ""), "cookie.txt")
                    self.main_window.post_ui(lambda: self.main_window.toast(self.t("login_ok")))
                else:
                    self.main_window.post_ui(lambda: self.main_window.toast(self.t("login_fail")))
            except Exception as exc:
                msg = str(exc)
                self.main_window.post_ui(lambda msg=msg: self.main_window.toast(msg))
        threading.Thread(target=run, daemon=True).start()
