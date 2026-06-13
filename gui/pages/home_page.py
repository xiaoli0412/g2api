"""Home page."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout

from gui.components import FluentButton
from gui.styles import COLORS, SPACING, qss_font
from .page_utils import Page


class HomePage(Page):
    start_server = pyqtSignal()
    stop_server = pyqtSignal()
    open_dashboard = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, "home")
        self._create_ui()
        self.start_server.connect(parent._start_server)
        self.stop_server.connect(parent._stop_server)
        self.open_dashboard.connect(parent._open_dashboard)

    def _create_ui(self):
        self.title("welcome")

        status = self.card("runtime")
        self.status_label = self.info_row(status, "service", self.t("status_stop"))
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('body')}")
        self.info_row(status, "port", self.main_window.config.get("port", 8081), numeric=True)
        self.info_row(status, "endpoint", f"http://localhost:{self.main_window.config.get('port', 8081)}/v1")
        self.info_row(status, "default_model", self.main_window.config.get("default_model", "gemini-3.5-flash"))

        tools = self.card("tools")
        actions = QHBoxLayout()
        actions.setSpacing(SPACING["sm"])
        actions.addWidget(FluentButton(self.t("start")))
        actions.itemAt(0).widget().clicked.connect(self.start_server.emit)
        actions.addWidget(FluentButton(self.t("stop"), "danger"))
        actions.itemAt(1).widget().clicked.connect(self.stop_server.emit)
        actions.addWidget(FluentButton(self.t("dashboard")))
        actions.itemAt(2).widget().clicked.connect(self.open_dashboard.emit)
        actions.addStretch()
        tools.layout.addLayout(actions)
        btn = FluentButton(self.t("open_ext"))
        btn.clicked.connect(self.main_window._open_extension)
        tools.layout.addWidget(btn)
        self.root.addStretch()

    def update_status(self, running):
        self.status_label.setText(self.t("status_run") if running else self.t("status_stop"))
        self.status_label.setStyleSheet(
            f"color: {COLORS['text_primary'] if running else COLORS['text_secondary']}; {qss_font('body')}"
        )
