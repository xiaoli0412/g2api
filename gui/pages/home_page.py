"""首页页面"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal

from ..styles import COLORS, FONTS, LAYOUT


class HomePage(QWidget):
    """首页页面"""
    
    # 信号定义
    start_server = pyqtSignal()
    stop_server = pyqtSignal()
    open_dashboard = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_ui()
        self._connect_signals()
    
    def _create_ui(self):
        """创建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LAYOUT['content_margin'],
            LAYOUT['content_margin'],
            LAYOUT['content_margin'],
            LAYOUT['content_margin']
        )
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("欢迎使用 Gemini2API")
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 24px;
                font-weight: bold;
                padding: 8px 0;
            }}
        """)
        layout.addWidget(title)
        
        # 副标题
        subtitle = QLabel("Gemini 网页端转 OpenAI 兼容 API 代理")
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 14px;
                padding-bottom: 16px;
            }}
        """)
        layout.addWidget(subtitle)
        
        # 状态卡片
        status_card = self._create_status_card()
        layout.addWidget(status_card)
        
        # 快速开始卡片
        quick_start_card = self._create_quick_start_card()
        layout.addWidget(quick_start_card)
        
        # Edge扩展卡片
        edge_ext_card = self._create_edge_extension_card()
        layout.addWidget(edge_ext_card)
        
        # 添加弹性空间
        layout.addStretch()
    
    def _create_status_card(self):
        """创建状态卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: {LAYOUT['card_border_radius']}px;
                padding: 18px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        
        # 状态文本
        self.status_label = QLabel("● 状态: 已停止")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['error']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.status_label)
        
        # 按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 启动按钮
        start_btn = QPushButton("启动服务")
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #6DB88A;
            }}
        """)
        start_btn.clicked.connect(self._on_start_clicked)
        button_layout.addWidget(start_btn)
        
        # 停止按钮
        stop_btn = QPushButton("停止服务")
        stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['error']};
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E05555;
            }}
        """)
        stop_btn.clicked.connect(self._on_stop_clicked)
        button_layout.addWidget(stop_btn)
        
        # 打开面板按钮
        dashboard_btn = QPushButton("打开面板")
        dashboard_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        dashboard_btn.clicked.connect(self._on_dashboard_clicked)
        button_layout.addWidget(dashboard_btn)
        
        layout.addLayout(button_layout)
        
        return card
    
    def _create_quick_start_card(self):
        """创建快速开始卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: {LAYOUT['card_border_radius']}px;
                padding: 18px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("快速开始")
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(title)
        
        # 步骤说明
        steps = [
            "1. 在侧边栏配置服务器、Cookie、流式模式",
            "2. 点击「启动服务」运行 API 服务器",
            "3. 用任何 OpenAI 兼容客户端连接",
            "4. 关闭窗口会最小化到托盘（服务继续运行）",
            "5. 访问 http://localhost:8081/dashboard 查看面板"
        ]
        
        for step in steps:
            step_label = QLabel(step)
            step_label.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['text_secondary']};
                    font-size: 12px;
                    padding: 2px 0;
                }}
            """)
            layout.addWidget(step_label)
        
        return card
    
    def _create_edge_extension_card(self):
        """创建Edge扩展卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: {LAYOUT['card_border_radius']}px;
                padding: 18px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("Edge 扩展")
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(title)
        
        # 描述
        desc = QLabel("安装 Edge 扩展实现自动推送 Cookie")
        desc.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 12px;
            }}
        """)
        layout.addWidget(desc)
        
        # 打开扩展目录按钮
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
        open_ext_btn.clicked.connect(self._open_extension_folder)
        layout.addWidget(open_ext_btn, alignment=Qt.AlignLeft)
        
        return card
    
    def _connect_signals(self):
        """连接信号"""
        if self.main_window:
            self.start_server.connect(self.main_window._start_server)
            self.stop_server.connect(self.main_window._stop_server)
            self.open_dashboard.connect(self.main_window._open_dashboard)
            
            # 连接语言变化信号
            self.main_window.language_changed.connect(self._update_texts)
    
    def _on_start_clicked(self):
        """启动按钮点击"""
        self.start_server.emit()
    
    def _on_stop_clicked(self):
        """停止按钮点击"""
        self.stop_server.emit()
    
    def _on_dashboard_clicked(self):
        """打开面板按钮点击"""
        self.open_dashboard.emit()
    
    def _open_extension_folder(self):
        """打开扩展目录"""
        import os
        import sys
        
        # 获取扩展目录路径
        if hasattr(sys, '_MEIPASS'):
            ext_path = os.path.join(sys._MEIPASS, 'extension')
        else:
            ext_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'extension')
        
        if os.path.exists(ext_path):
            os.startfile(ext_path)
        else:
            # 显示错误信息
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", "扩展目录未找到")
    
    def _update_texts(self, lang):
        """更新文本"""
        # 这里可以更新页面文本
        pass
    
    def update_status(self, running):
        """更新状态"""
        if running:
            self.status_label.setText("● 状态: 运行中")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['success']};
                    font-size: 16px;
                    font-weight: bold;
                }}
            """)
        else:
            self.status_label.setText("● 状态: 已停止")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['error']};
                    font-size: 16px;
                    font-weight: bold;
                }}
            """)