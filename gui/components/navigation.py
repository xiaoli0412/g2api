"""Windows 11 Settings-style navigation pane."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from gui.styles import COLORS, RADIUS, SIZES, SPACING, qss_font, qss_icon_font


class NavButton(QPushButton):
    clicked_key = pyqtSignal(str)

    def __init__(self, key, icon, text, parent=None):
        super().__init__(parent)
        self.key = key
        self.icon = icon
        self.label = text
        self.active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text)
        self.setFixedHeight(SIZES["nav_item_height"])
        self.setMinimumWidth(SIZES["nav_width"] - SPACING["xl"] * 2)
        self._build()
        self.setStyleSheet(self._qss())
        self.clicked.connect(lambda: self.clicked_key.emit(self.key))

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], 0, SPACING["md"], 0)
        layout.setSpacing(SPACING["md"])
        self.icon_label = QLabel(self.icon)
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_icon_font(18)}")
        self.text_label = QLabel(self.label)
        self.text_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.text_label.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('body')}")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)

    def set_text(self, icon, text):
        self.icon = icon
        self.label = text
        self.icon_label.setText(icon)
        self.text_label.setText(text)
        self.setToolTip(text)

    def set_active(self, active):
        self.active = active
        self.setStyleSheet(self._qss())
        self.update()

    def _qss(self):
        bg = COLORS["selected_bg"] if self.active else "transparent"
        color = COLORS["text_primary"] if self.active else COLORS["text_secondary"]
        if hasattr(self, "icon_label"):
            self.icon_label.setStyleSheet(f"color: {color}; {qss_icon_font(18)}")
            self.text_label.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('body')}")
        return f"""
            QPushButton {{
                background-color: {bg};
                border: none;
                border-radius: {RADIUS['card']}px;
                padding: 0;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: {COLORS['hover_bg']}; color: {COLORS['text_primary']}; }}
            QPushButton:pressed {{ background-color: {COLORS['pressed_bg']}; }}
        """

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.active:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(COLORS["accent"]))
            y = (self.height() - 20) // 2
            painter.drawRoundedRect(0, y, 4, 20, 2, 2)


class Sidebar(QFrame):
    page_changed = pyqtSignal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.buttons = {}
        self.setFixedWidth(SIZES["nav_width"])
        self.setObjectName("Sidebar")
        self.setStyleSheet(f"QFrame#Sidebar {{ background-color: rgba(27, 30, 33, 205); border-right: 1px solid {COLORS['border']}; }}")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        self.layout.setSpacing(SPACING["xs"])
        self._add_identity()
        for key, icon, text in items:
            btn = NavButton(key, icon, text)
            btn.clicked_key.connect(self.page_changed.emit)
            self.layout.addWidget(btn)
            self.buttons[key] = btn
        self.layout.addStretch()

    def _add_identity(self):
        box = QFrame()
        box.setObjectName("NavIdentity")
        box.setFixedHeight(92)
        box.setStyleSheet("QFrame#NavIdentity { background: transparent; border: none; }")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["md"])
        avatar = QLabel("G")
        avatar.setFixedSize(52, 52)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: {COLORS['selected_bg']}; color: {COLORS['text_primary']}; "
            f"border-radius: 26px; {qss_font('section_title')}"
        )
        names = QVBoxLayout()
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(2)
        title = QLabel("Gemini2API")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('section_title')}")
        subtitle = QLabel("OpenAI-compatible API proxy")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('helper')}")
        names.addStretch()
        names.addWidget(title)
        names.addWidget(subtitle)
        names.addStretch()
        layout.addWidget(avatar)
        layout.addLayout(names, 1)
        self.layout.addWidget(box)

    def set_active(self, key):
        for name, btn in self.buttons.items():
            btn.set_active(name == key)

    def update_texts(self, items):
        for key, icon, text in items:
            if key in self.buttons:
                self.buttons[key].set_text(icon, text)
