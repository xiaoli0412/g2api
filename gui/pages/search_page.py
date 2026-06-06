"""联网搜索页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QPushButton
)
from PyQt5.QtCore import Qt

from ..styles import COLORS, LAYOUT


class SearchPage(QWidget):
    """联网搜索页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT['content_margin'], LAYOUT['content_margin'], 
                                  LAYOUT['content_margin'], LAYOUT['content_margin'])
        layout.setSpacing(16)
        
        title = QLabel("联网搜索")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 搜索说明卡片
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: {LAYOUT['card_border_radius']}px;
                padding: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        
        card_title = QLabel("联网搜索")
        card_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: bold;")
        card_layout.addWidget(card_title)
        
        desc = QLabel("使用 @search 后缀或搜索专用模型名")
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        card_layout.addWidget(desc)
        
        examples = [
            "  gemini-3.5-flash-search",
            "  gemini-3.5-flash-thinking-search",
            "  gemini-3.1-pro-search",
            "  gemini-3.5-flash@search",
            "  gemini-3.5-flash-thinking@search@think=2",
        ]
        
        for ex in examples:
            ex_label = QLabel(ex)
            ex_label.setStyleSheet(f"color: {COLORS['text_accent']}; font-size: 12px; font-family: Consolas;")
            card_layout.addWidget(ex_label)
        
        copy_btn = QPushButton("复制测试命令")
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary_hover']}; }}
        """)
        copy_btn.clicked.connect(self._copy_cmd)
        card_layout.addWidget(copy_btn, alignment=Qt.AlignLeft)
        
        layout.addWidget(card)
        layout.addStretch()
    
    def _copy_cmd(self):
        from PyQt5.QtWidgets import QApplication
        cmd = 'curl http://localhost:8081/v1/chat/completions -H "Content-Type: application/json" -d \'{"model":"gemini-3.5-flash@search","messages":[{"role":"user","content":"today news"}]}\''
        QApplication.clipboard().setText(cmd)
        if self.main_window:
            self.main_window.status_text.setText("命令已复制到剪贴板")
