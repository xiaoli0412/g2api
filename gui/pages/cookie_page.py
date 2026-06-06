"""Cookie管理页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt

from ..styles import COLORS, LAYOUT


class CookiePage(QWidget):
    """Cookie管理页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT['content_margin'], LAYOUT['content_margin'], 
                                  LAYOUT['content_margin'], LAYOUT['content_margin'])
        layout.setSpacing(16)
        
        title = QLabel("Cookie管理")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # Cookie来源卡片
        source_card = self._create_card("Cookie来源")
        self.auto_cookie_check = QCheckBox("启动时自动提取Cookie")
        self.auto_cookie_check.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        source_card.layout().addWidget(self.auto_cookie_check)
        layout.addWidget(source_card)
        
        # 自动刷新卡片
        refresh_card = self._create_card("自动刷新")
        row = QHBoxLayout()
        lbl = QLabel("刷新间隔(小时)")
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        row.addWidget(lbl)
        self.refresh_input = QLineEdit("12")
        self.refresh_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['input_bg']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
        """)
        row.addWidget(self.refresh_input)
        refresh_card.layout().addLayout(row)
        layout.addWidget(refresh_card)
        
        # Edge扩展卡片
        ext_card = self._create_card("Edge扩展")
        desc = QLabel("安装Edge扩展实现自动推送Cookie")
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        ext_card.layout().addWidget(desc)
        
        open_ext_btn = QPushButton("打开扩展目录")
        open_ext_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['hover_bg']};
                color: {COLORS['text_primary']};
            }}
        """)
        ext_card.layout().addWidget(open_ext_btn, alignment=Qt.AlignLeft)
        layout.addWidget(ext_card)
        
        # 操作按钮卡片
        action_card = self._create_card("操作")
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("立即刷新")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary_hover']}; }}
        """)
        btn_layout.addWidget(refresh_btn)
        
        login_btn = QPushButton("浏览器登录")
        login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #7C3AED;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #6D28D9; }}
        """)
        btn_layout.addWidget(login_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #6DB88A; }}
        """)
        btn_layout.addWidget(save_btn)
        
        action_card.layout().addLayout(btn_layout)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        action_card.layout().addWidget(self.status_label)
        
        layout.addWidget(action_card)
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
