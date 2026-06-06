"""设置页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt

from ..styles import COLORS, LAYOUT


class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT['content_margin'], LAYOUT['content_margin'], 
                                  LAYOUT['content_margin'], LAYOUT['content_margin'])
        layout.setSpacing(16)
        
        title = QLabel("设置")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 应用设置卡片
        app_card = self._create_card("应用设置")
        self.tray_check = QCheckBox("关闭窗口时最小化到托盘")
        self.tray_check.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.tray_check.setChecked(True)
        app_card.layout().addWidget(self.tray_check)
        
        self.autostart_check = QCheckBox("启动应用时自动启动服务器")
        self.autostart_check.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        app_card.layout().addWidget(self.autostart_check)
        
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary_hover']}; }}
        """)
        btn_layout.addWidget(save_btn)
        
        config_btn = QPushButton("打开配置文件")
        config_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                padding: 10px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['hover_bg']};
                color: {COLORS['text_primary']};
            }}
        """)
        btn_layout.addWidget(config_btn)
        
        logs_btn = QPushButton("打开日志")
        logs_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                padding: 10px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['hover_bg']};
                color: {COLORS['text_primary']};
            }}
        """)
        btn_layout.addWidget(logs_btn)
        
        app_card.layout().addLayout(btn_layout)
        layout.addWidget(app_card)
        
        # 关于卡片
        about_card = self._create_card("关于")
        about_lines = [
            "Gemini2API v2.1.0",
            "Gemini Web -> OpenAI API",
            "Flash / Pro / Thinking / Search / Streaming",
            "MIT License"
        ]
        for line in about_lines:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            about_card.layout().addWidget(lbl)
        
        layout.addWidget(about_card)
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
