"""主窗口 - PyQt5实现，支持Windows 11 Mica/Acrylic效果"""
import sys
import ctypes
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QLabel, QPushButton, QFrame,
    QApplication, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPalette

from .styles import COLORS, FONTS
from .pages.home_page import HomePage
from .pages.server_page import ServerPage
from .pages.cookie_page import CookiePage
from .pages.stream_page import StreamPage
from .pages.search_page import SearchPage
from .pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    """主窗口类"""
    
    # 信号定义
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    language_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_lang = "zh"
        self.translations = self._load_translations()
        self.server_running = False
        
        # 设置窗口属性
        self.setWindowTitle("Gemini2API v2.1.0")
        self.setGeometry(100, 100, 960, 660)
        self.setMinimumSize(860, 600)
        
        # 启用Mica效果
        self._enable_mica_effect()
        
        # 设置样式
        self._setup_styles()
        
        # 创建UI
        self._create_ui()
        
        # 创建系统托盘
        self._create_system_tray()
        
        # 连接信号
        self._connect_signals()
    
    def _enable_mica_effect(self):
        """启用Windows 11 Mica效果"""
        try:
            # 获取窗口句柄
            hwnd = int(self.winId())
            
            # DWMWA_SYSTEMBACKDROP_TYPE = 38
            # DWMSBT_MAINWINDOW = 2 (Mica)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 38, ctypes.byref(ctypes.c_int(2)), 4
            )
            
            # 设置窗口背景透明
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setWindowFlags(Qt.FramelessWindowHint)
            
        except Exception as e:
            print(f"Mica效果启用失败: {e}")
            # 回退到普通样式
            self.setStyleSheet(f"background-color: {COLORS['mica_bg']};")
    
    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['mica_bg']};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
            }}
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary_pressed']};
            }}
        """)
    
    def _create_ui(self):
        """创建UI布局"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建侧边栏
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        # 创建内容区域
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background-color: {COLORS['surface']};")
        main_layout.addWidget(self.content_stack)
        
        # 创建各个页面
        self._create_pages()
        
        # 创建状态栏
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)
    
    def _create_sidebar(self):
        """创建侧边栏"""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['sidebar_bg']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)
        
        # Logo和标题
        logo_label = QLabel("Gemini2API")
        logo_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_accent']};
                font-size: 20px;
                font-weight: bold;
                padding: 8px 0;
            }}
        """)
        layout.addWidget(logo_label)
        
        version_label = QLabel("v2.1.0")
        version_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 11px;
                padding-bottom: 16px;
            }}
        """)
        layout.addWidget(version_label)
        
        # 导航按钮
        self.nav_buttons = {}
        nav_items = [
            ("home", "首页"),
            ("server", "服务器"),
            ("cookie", "Cookie"),
            ("stream", "流式输出"),
            ("search", "联网搜索"),
            ("settings", "设置")
        ]
        
        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_secondary']};
                    text-align: left;
                    padding: 10px 12px;
                    border-radius: 8px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['hover_bg']};
                    color: {COLORS['text_primary']};
                }}
            """)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn
        
        # 添加弹性空间
        layout.addStretch()
        
        # 状态指示器
        self.status_label = QLabel("● 状态: 已停止")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['error']};
                font-size: 12px;
                padding: 8px 0;
            }}
        """)
        layout.addWidget(self.status_label)
        
        # 语言切换按钮
        lang_btn = QPushButton("中文 / EN")
        lang_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_secondary']};
                font-size: 11px;
                padding: 6px 12px;
            }}
        """)
        lang_btn.clicked.connect(self._toggle_language)
        layout.addWidget(lang_btn)
        
        return sidebar
    
    def _create_pages(self):
        """创建各个页面"""
        # 首页
        self.home_page = HomePage(self)
        self.content_stack.addWidget(self.home_page)
        
        # 服务器页面
        self.server_page = ServerPage(self)
        self.content_stack.addWidget(self.server_page)
        
        # Cookie页面
        self.cookie_page = CookiePage(self)
        self.content_stack.addWidget(self.cookie_page)
        
        # 流式输出页面
        self.stream_page = StreamPage(self)
        self.content_stack.addWidget(self.stream_page)
        
        # 联网搜索页面
        self.search_page = SearchPage(self)
        self.content_stack.addWidget(self.search_page)
        
        # 设置页面
        self.settings_page = SettingsPage(self)
        self.content_stack.addWidget(self.settings_page)
        
        # 默认显示首页
        self._switch_page("home")
    
    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QFrame()
        status_bar.setFixedHeight(30)
        status_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['status_bar_bg']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # 状态文本
        self.status_text = QLabel("就绪")
        self.status_text.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.status_text)
        
        # 版本信息
        version_text = QLabel("Gemini2API v2.1.0")
        version_text.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 11px;
            }}
        """)
        layout.addStretch()
        layout.addWidget(version_text)
        
        return status_bar
    
    def _create_system_tray(self):
        """创建系统托盘"""
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        
        # 创建图标（这里使用简单的颜色块作为图标）
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(COLORS['primary']))
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        dashboard_action = QAction("打开面板", self)
        dashboard_action.triggered.connect(self._open_dashboard)
        tray_menu.addAction(dashboard_action)
        
        tray_menu.addSeparator()
        
        start_action = QAction("启动服务", self)
        start_action.triggered.connect(self._start_server)
        tray_menu.addAction(start_action)
        
        stop_action = QAction("停止服务", self)
        stop_action.triggered.connect(self._stop_server)
        tray_menu.addAction(stop_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
    
    def _connect_signals(self):
        """连接信号"""
        # 这里可以连接各个页面的信号
        pass
    
    def _switch_page(self, page_name):
        """切换页面"""
        page_map = {
            "home": 0,
            "server": 1,
            "cookie": 2,
            "stream": 3,
            "search": 4,
            "settings": 5
        }
        
        if page_name in page_map:
            self.content_stack.setCurrentIndex(page_map[page_name])
            
            # 更新导航按钮样式
            for key, btn in self.nav_buttons.items():
                if key == page_name:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLORS['primary']};
                            color: {COLORS['on_primary']};
                            text-align: left;
                            padding: 10px 12px;
                            border-radius: 8px;
                            font-size: 13px;
                            font-weight: bold;
                        }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: transparent;
                            color: {COLORS['text_secondary']};
                            text-align: left;
                            padding: 10px 12px;
                            border-radius: 8px;
                            font-size: 13px;
                        }}
                        QPushButton:hover {{
                            background-color: {COLORS['hover_bg']};
                            color: {COLORS['text_primary']};
                        }}
                    """)
    
    def _toggle_language(self):
        """切换语言"""
        self.current_lang = "en" if self.current_lang == "zh" else "zh"
        self.translations = self._load_translations()
        self.language_changed.emit(self.current_lang)
        self._update_ui_texts()
    
    def _load_translations(self):
        """加载翻译"""
        # 这里可以加载语言包，暂时使用简单的字典
        if self.current_lang == "zh":
            return {
                "home": "首页",
                "server": "服务器",
                "cookie": "Cookie",
                "stream": "流式输出",
                "search": "联网搜索",
                "settings": "设置",
                "status_running": "● 状态: 运行中",
                "status_stopped": "● 状态: 已停止",
                "ready": "就绪"
            }
        else:
            return {
                "home": "Home",
                "server": "Server",
                "cookie": "Cookie",
                "stream": "Streaming",
                "search": "Web Search",
                "settings": "Settings",
                "status_running": "● Status: Running",
                "status_stopped": "● Status: Stopped",
                "ready": "Ready"
            }
    
    def _update_ui_texts(self):
        """更新UI文本"""
        # 更新导航按钮
        for key, btn in self.nav_buttons.items():
            btn.setText(self.translations.get(key, key))
        
        # 更新状态标签
        if self.server_running:
            self.status_label.setText(self.translations["status_running"])
            self.status_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.status_label.setText(self.translations["status_stopped"])
            self.status_label.setStyleSheet(f"color: {COLORS['error']};")
        
        # 更新状态栏
        self.status_text.setText(self.translations["ready"])
    
    def _start_server(self):
        """启动服务器"""
        # 这里实现服务器启动逻辑
        self.server_running = True
        self.server_started.emit()
        self._update_ui_texts()
        self.status_text.setText("服务器已启动")
    
    def _stop_server(self):
        """停止服务器"""
        # 这里实现服务器停止逻辑
        self.server_running = False
        self.server_stopped.emit()
        self._update_ui_texts()
        self.status_text.setText("服务器已停止")
    
    def _open_dashboard(self):
        """打开面板"""
        # 这里实现打开面板逻辑
        import webbrowser
        webbrowser.open("http://localhost:8081/dashboard")
    
    def _quit_application(self):
        """退出应用"""
        # 停止服务器
        if self.server_running:
            self._stop_server()
        
        # 隐藏托盘图标
        self.tray_icon.hide()
        
        # 退出应用
        QApplication.quit()
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 最小化到托盘而不是关闭
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Gemini2API",
            "应用已最小化到系统托盘",
            QSystemTrayIcon.Information,
            2000
        )