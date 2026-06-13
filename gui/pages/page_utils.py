"""Shared Windows-native page helpers."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.components import FluentCard, FluentCombo, FluentInput, FluentTextEdit
from gui.styles import COLORS, SIZES, SPACING, qss_font


class Page(QWidget):
    def __init__(self, main_window, title_key):
        super().__init__(main_window)
        self.main_window = main_window
        self.title_key = title_key
        self.setObjectName("Page")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        self.root.setSpacing(SPACING["sm"])

    def t(self, key):
        return self.main_window.t(key)

    def title(self, key=None, detail=""):
        header = QFrame()
        header.setObjectName("PageHeader")
        header.setFixedHeight(SIZES["toolbar_height"])
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        label = QLabel(self.t(key or self.title_key))
        label.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('section_title')}")
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(label)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('helper')}")
            detail_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            layout.addWidget(detail_label)
        layout.addStretch()
        self.root.addWidget(header)
        return label

    def helper(self, text, parent_layout=None):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('helper')}")
        (parent_layout or self.root).addWidget(label)
        return label

    def card(self, title_key):
        card = FluentCard(self.t(title_key))
        self.root.addWidget(card)
        return card

    def row(self, parent, label_key):
        frame = QFrame()
        frame.setObjectName("ListRow")
        frame.setProperty("active", False)
        frame.setAttribute(Qt.WA_Hover, True)
        frame.setMinimumHeight(SIZES["row_height"])
        row = QHBoxLayout()
        frame.setLayout(row)
        row.setContentsMargins(SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["xs"])
        row.setSpacing(SPACING["sm"])
        label = QLabel(self.t(label_key))
        label.setFixedWidth(160)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; {qss_font('body')}")
        row.addWidget(label)
        parent.layout.addWidget(frame)
        return row

    def input_row(self, parent, label_key, value="", placeholder=""):
        row = self.row(parent, label_key)
        inp = FluentInput(str(value) if value is not None else "", placeholder)
        row.addWidget(inp, 1)
        return inp

    def combo_row(self, parent, label_key, items, value=None):
        row = self.row(parent, label_key)
        combo = FluentCombo(items)
        if value in items:
            combo.setCurrentText(value)
        row.addWidget(combo, 1)
        return combo

    def text_row(self, parent, label_key, value=""):
        row = self.row(parent, label_key)
        editor = FluentTextEdit(value)
        editor.setFixedHeight(80)
        row.addWidget(editor, 1)
        return editor

    def info_row(self, parent, label_key, value="", numeric=False):
        row = self.row(parent, label_key)
        label = QLabel(str(value))
        label.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('body')}")
        label.setAlignment(Qt.AlignVCenter | (Qt.AlignRight if numeric else Qt.AlignLeft))
        row.addWidget(label, 1)
        return label
