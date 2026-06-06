"""流式输出配置页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QComboBox, QLineEdit
)
from PyQt5.QtCore import Qt

from ..styles import COLORS, LAYOUT


class StreamPage(QWidget):
    """流式输出配置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT['content_margin'], LAYOUT['content_margin'], 
                                  LAYOUT['content_margin'], LAYOUT['content_margin'])
        layout.setSpacing(16)
        
        title = QLabel("流式输出配置")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 流式模式卡片
        mode_card = self._create_card("流式模式")
        self.stream_mode_combo = self._add_combo(mode_card, "流式模式", ["auto", "true", "fake"])
        
        mode_desc = QLabel("auto: 有httpx真流式，否则假流式\ntrue: 真流式（需要httpx）\nfake: 假流式（快速逐字输出）")
        mode_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        mode_card.layout().addWidget(mode_desc)
        layout.addWidget(mode_card)
        
        # 假流式延迟卡片
        delay_card = self._create_card("假流式延迟")
        self.delay_input = self._add_input(delay_card, "延迟(ms)", "5")
        layout.addWidget(delay_card)
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 10px 24px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary_hover']}; }}
        """)
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn, alignment=Qt.AlignLeft)
        
        layout.addStretch()
    
    def _create_card(self, title):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: {LAYOUT['card_border_radius']}px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        
        label = QLabel(title)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: bold;")
        layout.addWidget(label)
        
        return card
    
    def _add_combo(self, parent, label, options):
        layout = parent.layout()
        row = QHBoxLayout()
        
        lbl = QLabel(label)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        row.addWidget(lbl)
        
        combo = QComboBox()
        combo.addItems(options)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['input_bg']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
        """)
        row.addWidget(combo)
        layout.addLayout(row)
        return combo
    
    def _add_input(self, parent, label, default=""):
        layout = parent.layout()
        row = QHBoxLayout()
        
        lbl = QLabel(label)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        row.addWidget(lbl)
        
        inp = QLineEdit(default)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['input_bg']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
        """)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp
    
    def _save_config(self):
        if self.main_window:
            self.main_window.status_text.setText("流式配置已保存")
