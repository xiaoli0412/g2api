"""服务器配置页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QComboBox
)
from PyQt5.QtCore import Qt

from ..styles import COLORS, LAYOUT


class ServerPage(QWidget):
    """服务器配置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT['content_margin'], LAYOUT['content_margin'], 
                                  LAYOUT['content_margin'], LAYOUT['content_margin'])
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("服务器配置")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 网络配置卡片
        network_card = self._create_card("网络配置")
        self.port_input = self._add_input(network_card, "端口", "8081")
        self.host_input = self._add_input(network_card, "主机", "0.0.0.0")
        layout.addWidget(network_card)
        
        # 代理配置卡片
        proxy_card = self._create_card("代理配置")
        self.proxy_type_combo = self._add_combo(proxy_card, "代理类型", ["无代理", "HTTP代理", "SOCKS5代理"])
        self.proxy_input = self._add_input(proxy_card, "代理地址", "", "例: http://127.0.0.1:7890")
        layout.addWidget(proxy_card)
        
        # API配置卡片
        api_card = self._create_card("API配置")
        self.api_keys_input = self._add_input(api_card, "API密钥", "", "多个用逗号分隔，留空免密钥")
        self.default_model_combo = self._add_combo(api_card, "默认模型", [
            "gemini-3.5-flash", "gemini-3.5-flash-thinking", 
            "gemini-3.1-pro", "gemini-auto", "gemini-flash-lite"
        ])
        layout.addWidget(api_card)
        
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
    
    def _add_input(self, parent, label, default="", hint=""):
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
        if hint:
            inp.setPlaceholderText(hint)
        row.addWidget(inp)
        
        layout.addLayout(row)
        return inp
    
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
    
    def _save_config(self):
        if self.main_window:
            self.main_window.status_text.setText("配置已保存")
