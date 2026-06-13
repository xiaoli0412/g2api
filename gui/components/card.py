"""Flat system section primitives."""

from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui.styles import COLORS, SPACING, qss_font


class FluentCard(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("SystemSection")
        self.setStyleSheet(f"""
            QFrame#SystemSection {{
                background: transparent;
                border: none;
            }}
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(SPACING["xs"])
        if title:
            label = QLabel(title)
            label.setObjectName("SectionLabel")
            label.setFixedHeight(24)
            label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('column')}")
            self.layout.addWidget(label)
