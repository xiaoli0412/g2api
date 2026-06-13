"""Starlight switch control."""

from PyQt5.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget

from gui.styles import COLORS, TRANSITION_MS


class FluentToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._offset = 20 if checked else 0
        self.setFixedSize(40, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(TRANSITION_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(20 if checked else 0)
        self._anim.start()
        self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def getOffset(self):
        return self._offset

    def setOffset(self, offset):
        self._offset = offset
        self.update()

    offset = pyqtProperty(int, getOffset, setOffset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["accent"] if self._checked else COLORS["text_disabled"]))
        painter.drawRoundedRect(QRect(0, 0, 40, 20), 10, 10)
        painter.setBrush(QColor(COLORS["text_primary"]))
        painter.drawEllipse(QPoint(10 + self._offset, 10), 8, 8)
