"""Application settings page."""

import os

from PyQt5.QtWidgets import QFileDialog, QHBoxLayout, QLabel

from gui.components import FluentButton, FluentToggle
from gui.styles import COLORS, SPACING, qss_font
from .page_utils import Page


class SettingsPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent, "settings")
        self._create_ui()

    def _create_ui(self):
        cfg = self.main_window.config
        self.title("settings")

        appearance = self.card("appearance")
        self.material_combo = self.combo_row(
            appearance,
            "window_material",
            ["Mica", "Acrylic", "Solid"],
            str(cfg.get("window_material", "mica")).replace("_", " ").title(),
        )
        self.background_input = self.input_row(
            appearance,
            "background_image",
            cfg.get("background_image", ""),
            self.t("background_hint"),
        )
        bg_actions = QHBoxLayout()
        bg_actions.setSpacing(SPACING["sm"])
        browse_btn = FluentButton(self.t("browse"))
        clear_btn = FluentButton(self.t("clear"))
        browse_btn.clicked.connect(self._browse_background)
        clear_btn.clicked.connect(self._clear_background)
        bg_actions.addWidget(browse_btn)
        bg_actions.addWidget(clear_btn)
        bg_actions.addStretch()
        appearance.layout.addLayout(bg_actions)
        self.dynamic_toggle = FluentToggle(cfg.get("dynamic_background", False))
        row = self.row(appearance, "dynamic_background")
        row.addWidget(self.dynamic_toggle)
        row.addStretch()

        app = self.card("app_settings")
        self.tray_toggle = FluentToggle(cfg.get("minimize_to_tray", True))
        row = self.row(app, "minimize_tray")
        row.addWidget(self.tray_toggle)
        row.addStretch()
        self.autostart_toggle = FluentToggle(cfg.get("auto_start_server", False))
        row = self.row(app, "auto_start")
        row.addWidget(self.autostart_toggle)
        row.addStretch()
        for text, handler, variant in [
            ("save", self._save_config, "default"),
            ("language_toggle", self.main_window._toggle_language, "default"),
            ("open_config", self.main_window._open_config, "default"),
            ("open_logs", self.main_window._open_dashboard, "default"),
        ]:
            btn = FluentButton(self.t(text), variant)
            btn.clicked.connect(handler)
            app.layout.addWidget(btn)

        about = self.card("about")
        for line in [
            "Gemini2API v2.1.0",
            "Author: xiaoliACG",
            "Gemini Web -> OpenAI API",
            "Flash / Pro / Thinking / Streaming",
            "Windows native desktop shell",
            "MIT License",
            "CLI: python app.py --cli",
            "EXE: build\\native\\x64\\Release\\Gemini2API.WinUI.exe",
        ]:
            label = QLabel(line)
            label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('body')}")
            about.layout.addWidget(label)
        self.root.addStretch()

    def _save_config(self):
        self.main_window.config["minimize_to_tray"] = self.tray_toggle.isChecked()
        self.main_window.config["auto_start_server"] = self.autostart_toggle.isChecked()
        self.main_window.config["window_material"] = self.material_combo.currentText().strip().lower().replace(" ", "_")
        self.main_window.config["background_image"] = self.background_input.text().strip()
        self.main_window.config["dynamic_background"] = self.dynamic_toggle.isChecked()
        self.main_window.save_config()
        self.main_window.update_window_material()
        self.main_window.update_background()
        self.main_window.toast(self.t("saved"))

    def _browse_background(self):
        start_dir = os.path.dirname(self.background_input.text().strip()) or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.t("background_image"),
            start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.background_input.setText(path)
            self._save_config()

    def _clear_background(self):
        self.background_input.clear()
        self._save_config()
