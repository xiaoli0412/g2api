"""Windows-native shell for Gemini2API."""

import json
import os
import sys
import threading
import webbrowser
import ctypes
from ctypes import wintypes

from PyQt5.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from gemini_web2api.config import CONFIG, DEFAULT_CONFIG, find_config, load_config
from gemini_web2api.server import GeminiHandler, ThreadedServer
from gui.components import CaptionButton, Sidebar, Toast
from gui.i18n import translate
from gui.pages.cookie_page import CookiePage
from gui.pages.home_page import HomePage
from gui.pages.proxy_page import ProxyPage
from gui.pages.server_page import ServerPage
from gui.pages.settings_page import SettingsPage
from gui.pages.stream_page import StreamPage
from gui.styles import COLORS, SIZES, SPACING, base_qss, qss_font
from gui.styles.fluent import WindowsMaterialShellMixin, apply_window_material, enable_frameless


CONFIG_FILE = "config.json"
COOKIE_FILE = "cookie.txt"
WM_NCHITTEST = 0x0084
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17


def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative)


class ServerThread(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.config = dict(config)
        self.running = False
        self.server = None

    def run(self):
        self.running = True
        try:
            CONFIG.update(self.config)
            from gemini_web2api.admin import init_admin
            init_admin()
            if CONFIG.get("proxy_pool_enabled"):
                from gemini_web2api.proxy_builtin import init_pool_from_config
                init_pool_from_config(CONFIG)
            if self.config.get("auto_cookie"):
                from gemini_web2api import cookie_manager
                cookie_str, sapisid = cookie_manager.extract_cookies()
                if cookie_str:
                    cookie_manager.write_cookie_file(cookie_str, sapisid, COOKIE_FILE)
                    CONFIG["cookie_file"] = COOKIE_FILE
                    init_admin()
            if self.config.get("auto_refresh_hours"):
                from gemini_web2api import cookie_manager
                cookie_manager.start_auto_refresh(int(self.config["auto_refresh_hours"]))
            self.server = ThreadedServer((CONFIG.get("host", "0.0.0.0"), int(CONFIG.get("port", 8081))), GeminiHandler)
            self.server.serve_forever()
        except Exception as exc:
            print(f"Server error: {exc}")
        finally:
            self.running = False

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class MaterialShell(QWidget, WindowsMaterialShellMixin):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("Shell")
        self._start_motion_timer()

    def paintEvent(self, event):
        painter = QPainter(self)
        self._paint_material_shell(
            painter,
            self.rect(),
            self.window.config.get("background_image") or "",
        )


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.drag_pos = None
        self.setFixedHeight(SIZES["titlebar_height"])
        self.setObjectName("TitleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["sm"], 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel("Gemini2API")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; {qss_font('window_title')}")
        layout.addWidget(title)
        layout.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; padding-right: {SPACING['sm']}px; {qss_font('helper')}")
        self.status_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        layout.addWidget(self.status_label)
        for text, tooltip, slot, danger in [
            ("\uE921", "Minimize", window.showMinimized, False),
            ("\uE922", "Maximize", window.toggle_maximized, False),
            ("\uE8BB", "Close", window.close, True),
        ]:
            btn = CaptionButton(text, danger=danger, tooltip=tooltip)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None


class MainWindow(QMainWindow):
    status_changed = pyqtSignal(bool)
    ui_call = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.config = self.load_config()
        self.lang = self.config.get("lang", "en")
        self.server_thread = None
        self.tray_icon = None
        enable_frameless(self)
        self.setWindowTitle("Gemini2API")
        self.setMinimumSize(980, 660)
        self.resize(1180, 760)
        self.setStyleSheet(base_qss())
        self._create_ui()
        apply_window_material(self, self.config.get("window_material", "mica"))
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self._create_tray()
        self.status_changed.connect(self._update_status)
        self.status_changed.emit(self.is_server_running())
        self.ui_call.connect(lambda fn: fn())
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.status_changed.emit(self.is_server_running()))
        self.timer.start(2000)
        QTimer.singleShot(800, self._try_auto_start)

    def t(self, key):
        return translate(self.lang, key)

    def post_ui(self, fn):
        self.ui_call.emit(fn)

    def load_config(self):
        config = dict(DEFAULT_CONFIG)
        config.update({
            "cookie_file": COOKIE_FILE,
            "auto_cookie": False,
            "auto_refresh_hours": None,
            "stream_mode": "auto",
            "fake_stream_delay_ms": 5,
            "cookie_source": "auto",
            "auto_start_server": False,
            "minimize_to_tray": True,
            "window_material": "mica",
            "background_image": "",
            "dynamic_background": False,
            "lang": "en",
        })
        try:
            cfg_path = find_config() or CONFIG_FILE
            if cfg_path and os.path.exists(cfg_path):
                load_config(cfg_path)
                config.update(CONFIG)
        except Exception:
            pass
        return config

    def save_config(self):
        self.config["lang"] = self.lang
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        CONFIG.update(self.config)

    def _create_ui(self):
        shell = MaterialShell(self)
        self.setCentralWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.titlebar = TitleBar(self)
        self.status_label = self.titlebar.status_label
        root.addWidget(self.titlebar)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        self.nav_items = [
            ("home", "\uE80F", self.t("home")),
            ("server", "\uE968", self.t("server")),
            ("proxy", "\uE8AB", self.t("proxy_workbench")),
            ("cookie", "\uE8D4", self.t("cookie")),
            ("stream", "\uE895", self.t("stream")),
            ("settings", "\uE713", self.t("settings")),
        ]
        self.sidebar = Sidebar(self.nav_items)
        self.sidebar.page_changed.connect(self.switch_page)
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.pages = {
            "home": HomePage(self),
            "server": ServerPage(self),
            "proxy": ProxyPage(self),
            "cookie": CookiePage(self),
            "stream": StreamPage(self),
            "settings": SettingsPage(self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        self.switch_page("home")
        self.status_changed.emit(self.is_server_running())

    def switch_page(self, key):
        if key not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[key])
        self.sidebar.set_active(key)

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def showEvent(self, event):
        super().showEvent(event)
        apply_window_material(self, self.config.get("window_material", "mica"))

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST and not self.isMaximized():
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                pos = self.mapFromGlobal(QPoint(x, y))
                margin = 6
                left = pos.x() <= margin
                right = pos.x() >= self.width() - margin
                top = pos.y() <= margin
                bottom = pos.y() >= self.height() - margin
                if top and left:
                    return True, HTTOPLEFT
                if top and right:
                    return True, HTTOPRIGHT
                if bottom and left:
                    return True, HTBOTTOMLEFT
                if bottom and right:
                    return True, HTBOTTOMRIGHT
                if left:
                    return True, HTLEFT
                if right:
                    return True, HTRIGHT
                if top:
                    return True, HTTOP
                if bottom:
                    return True, HTBOTTOM
        return super().nativeEvent(event_type, message)

    def _toggle_language(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.save_config()
        self._rebuild_ui()

    def _rebuild_ui(self):
        old = self.centralWidget()
        if old:
            old.deleteLater()
        self._create_ui()
        self.status_changed.emit(self.is_server_running())

    def _create_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(COLORS["accent"]))
        self.tray_icon.setIcon(QIcon(pixmap))
        menu = QMenu()
        menu.addAction(self.t("show_window"), self.show)
        menu.addAction(self.t("dashboard"), self._open_dashboard)
        menu.addSeparator()
        menu.addAction(self.t("start"), self._start_server)
        menu.addAction(self.t("stop"), self._stop_server)
        menu.addSeparator()
        menu.addAction(self.t("quit"), self._quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def update_background(self):
        shell = self.centralWidget()
        if shell:
            shell._loaded_background_path = None
            shell._frosted_cache_key = None
            if hasattr(shell, "_motion_timer"):
                if self.config.get("dynamic_background") and not shell._motion_timer.isActive():
                    shell._motion_timer.start()
                elif not self.config.get("dynamic_background") and shell._motion_timer.isActive():
                    shell._motion_timer.stop()
            shell.update()

    def update_window_material(self):
        apply_window_material(self, self.config.get("window_material", "mica"))
        self.update_background()

    def _try_auto_start(self):
        if self.config.get("auto_start_server"):
            self._start_server()

    def is_server_running(self):
        return bool(self.server_thread and self.server_thread.running)

    def _start_server(self):
        if self.is_server_running():
            self.toast(self.t("server_running"))
            return
        self.save_config()
        self.server_thread = ServerThread(self.config)
        self.server_thread.start()
        QTimer.singleShot(500, lambda: self.status_changed.emit(self.is_server_running()))
        self.toast(f"{self.t('server_running')} :{self.config.get('port', 8081)}")

    def _stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread = None
        self.status_changed.emit(False)
        self.toast(self.t("server_stopped"))

    def _update_status(self, running):
        self.status_label.setText("● " + (self.t("status_run") if running else self.t("status_stop")))
        self.status_label.setStyleSheet(
            f"color: {COLORS['text_primary'] if running else COLORS['text_secondary']}; "
            f"padding-right: {SPACING['sm']}px; {qss_font('helper')}"
        )
        home = self.pages.get("home")
        if home:
            home.update_status(running)

    def _open_dashboard(self):
        webbrowser.open(f"http://localhost:{self.config.get('port', 8081)}/dashboard")

    def _open_extension(self):
        path = resource_path("extension")
        if os.path.exists(path):
            os.startfile(path)
        else:
            self.toast(self.t("ext_not_found"))

    def _open_config(self):
        path = os.path.abspath(CONFIG_FILE)
        if os.path.exists(path):
            os.startfile(path)

    def toast(self, message):
        Toast(self, message)

    def closeEvent(self, event):
        if self.config.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            if self.tray_icon:
                self.tray_icon.showMessage("Gemini2API", "Minimized to tray", QSystemTrayIcon.Information, 1500)
        else:
            self._quit()

    def _quit(self):
        if self.server_thread:
            self._stop_server()
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
        QApplication.quit()
