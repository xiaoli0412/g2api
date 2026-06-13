"""Streaming configuration page."""

from gui.components import FluentButton
from .page_utils import Page


class StreamPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent, "stream")
        self._create_ui()

    def _create_ui(self):
        cfg = self.main_window.config
        self.title("stream")
        mode = self.card("stream_mode")
        self.mode_combo = self.combo_row(mode, "stream_mode", ["auto", "true", "fake"], cfg.get("stream_mode", "auto"))
        self.helper(self.t("stream_auto"), mode.layout)
        self.helper(self.t("stream_true"), mode.layout)
        self.helper(self.t("stream_fake"), mode.layout)

        delay = self.card("fake_delay")
        self.delay_input = self.input_row(delay, "fake_delay", cfg.get("fake_stream_delay_ms", 5))
        btn = FluentButton(self.t("save"))
        btn.clicked.connect(self._save_config)
        delay.layout.addWidget(btn)
        self.root.addStretch()

    def _save_config(self):
        self.main_window.config["stream_mode"] = self.mode_combo.currentText()
        self.main_window.config["fake_stream_delay_ms"] = int(self.delay_input.text() or 5)
        self.main_window.save_config()
        self.main_window.toast(self.t("saved"))
