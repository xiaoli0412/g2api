"""Windows-native button components."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QPushButton, QSizePolicy

from gui.styles import COLORS, ICON_FONT_FAMILY, RADIUS, SIZES, qss_icon_font, qss_font


class FluentButton(QPushButton):
    def __init__(self, text="", variant="default", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(SIZES["button_height"])
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet(self._qss())

    def _qss(self):
        if self.variant == "danger":
            bg = COLORS["control_bg"]
            border = COLORS["border"]
            hover = COLORS["danger"]
            pressed = COLORS["pressed_bg"]
        else:
            bg = COLORS["control_bg"]
            border = COLORS["border"]
            hover = COLORS["selected_bg"]
            pressed = COLORS["pressed_bg"]
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {COLORS['text_primary']};
                border: 1px solid {border};
                border-radius: {RADIUS['control']}px;
                padding: 6px 12px;
                text-align: center;
                {qss_font('button')}
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {pressed}; }}
            QPushButton:disabled {{
                color: {COLORS['text_disabled']};
                background-color: {COLORS['control_bg']};
                border-color: {COLORS['border']};
            }}
        """


class IconButton(QPushButton):
    def __init__(self, text="", parent=None, danger=False, size=None, tooltip=""):
        super().__init__(text, parent)
        self.danger = danger
        self.setCursor(Qt.PointingHandCursor)
        side = size or SIZES["icon_button"]
        self.setFixedSize(side, side)
        if tooltip:
            self.setToolTip(tooltip)
        icon_font = QFont(ICON_FONT_FAMILY, 10)
        self.setFont(icon_font)
        self.setStyleSheet(self._qss())

    def _qss(self):
        hover = COLORS["danger"] if self.danger else COLORS["hover_bg"]
        return f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: {RADIUS['control']}px;
                padding: 0;
                {qss_icon_font(10)}
            }}
            QPushButton:hover {{ background-color: {hover}; color: {COLORS['text_primary']}; }}
            QPushButton:pressed {{ background-color: {COLORS['pressed_bg']}; }}
        """


class CaptionButton(QPushButton):
    def __init__(self, text="", parent=None, danger=False, tooltip=""):
        super().__init__(text, parent)
        self.danger = danger
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, SIZES["titlebar_height"])
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if tooltip:
            self.setToolTip(tooltip)
        self.setFont(QFont(ICON_FONT_FAMILY, 10))
        self.setStyleSheet(self._qss())

    def _qss(self):
        hover = COLORS["danger"] if self.danger else COLORS["hover_bg"]
        pressed = COLORS["pressed_bg"] if not self.danger else "#C50F1F"
        return f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: 0;
                padding: 0;
                {qss_icon_font(10)}
            }}
            QPushButton:hover {{
                background-color: {hover};
                color: {COLORS['text_primary']};
            }}
            QPushButton:pressed {{ background-color: {pressed}; }}
        """
