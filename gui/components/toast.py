"""Small transient Starlight notification."""

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.styles import COLORS, RADIUS, qss_font


class Toast(QWidget):
    def __init__(self, parent, message):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(340, 40)
        self.setStyleSheet(f"""
            QWidget {{ background-color: {COLORS['control_bg']}; border: 1px solid {COLORS['border']}; border-radius: {RADIUS['control']}px; }}
            QLabel {{ color: {COLORS['text_primary']}; {qss_font('body')} }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        label = QLabel(message)
        layout.addWidget(label)
        parent_rect = parent.geometry()
        self.move(parent_rect.x() + (parent_rect.width() - self.width()) // 2, parent_rect.y() + parent_rect.height() - 64)
        self.show()
        QTimer.singleShot(2500, self.close)
