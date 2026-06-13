"""Windows-native input components."""

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QComboBox, QLineEdit, QTextEdit

from gui.styles import COLORS, RADIUS, SIZES, qss_font


INPUT_QSS = f"""
    QLineEdit, QComboBox, QTextEdit {{
        background-color: {COLORS['control_bg']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['control']}px;
        padding: 4px 8px;
        selection-background-color: {COLORS['selected_bg']};
        {qss_font('body')}
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {COLORS['border']}; }}
    QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled {{ color: {COLORS['text_disabled']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        selection-background-color: {COLORS['selected_bg']};
        outline: none;
    }}
"""


class FluentInput(QLineEdit):
    def __init__(self, text="", placeholder="", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(SIZES["button_height"])
        self.setStyleSheet(INPUT_QSS)
        palette = self.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(COLORS["text_disabled"]))
        self.setPalette(palette)


class FluentCombo(QComboBox):
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        if items:
            self.addItems(items)
        self.setFixedHeight(SIZES["button_height"])
        self.setStyleSheet(INPUT_QSS)


class FluentTextEdit(QTextEdit):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setPlainText(text)
        self.setStyleSheet(INPUT_QSS)
