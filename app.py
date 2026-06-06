"""Gemini2API Desktop - Win11 Style, i18n, Proxy, Animations."""
import customtkinter as ctk
import threading
import webbrowser
import json
import os
import sys
import time
import math

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "Gemini2API"
APP_VERSION = "2.1.0"
CONFIG_FILE = "config.json"
COOKIE_FILE = "cookie.txt"

ACCENT = "#0078D4"
ACCENT_HOVER = "#1A8AE8"
BG_DARK = "#202020"
BG_MICA = "#2C2C2C"
BG_CARD = "#333333"
BG_INPUT = "#3D3D3D"
BG_HOVER = "#454545"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SEC = "#999999"
TEXT_ACCENT = "#60CDFF"
BORDER = "#4A4A4A"
SUCCESS = "#2DB84B"
ERROR = "#FF6B6B"
WARNING = "#FFB900"
CLOSE_RED = "#E81123"

LANG = {
    "zh": {
        "home": "首页", "server": "服务器", "cookie": "Cookie",
        "stream": "流式输出", "search": "联网搜索", "settings": "设置",
        "welcome": "欢迎使用 Gemini2API",
        "subtitle": "Gemini 网页端转 OpenAI 兼容 API 代理",
        "status_run": "状态: 运行中", "status_stop": "状态: 已停止",
        "start": "启动服务", "stop": "停止服务", "dashboard": "打开面板",
        "quick_start": "快速开始",
        "step1": "1. 在侧边栏配置服务器、Cookie、流式模式",
        "step2": "2. 点击「启动服务」运行 API 服务器",
        "step3": "3. 用任何 OpenAI 兼容客户端连接",
        "step4": "4. 关闭窗口会最小化到托盘（服务继续运行）",
        "step5": "5. 访问 http://localhost:8081/dashboard 查看面板",
        "network": "网络配置", "port": "端口", "host": "主机",
        "proxy": "代理", "proxy_hint": "例: http://127.0.0.1:7890",
        "api_config": "API 配置", "api_keys": "API 密钥",
        "api_keys_hint": "多个用逗号分隔，留空免密钥",
        "default_model": "默认模型", "save": "保存",
        "cookie_source": "Cookie 来源", "auto_extract": "启动时自动提取 Cookie",
        "auto_refresh": "自动刷新", "interval": "间隔(小时)",
        "refresh_now": "立即刷新", "browser_login": "浏览器登录",
        "edge_ext": "Edge 扩展", "edge_ext_desc": "安装 Edge 扩展实现自动推送 Cookie",
        "open_ext": "打开扩展目录",
        "stream_mode": "流式模式", "stream_auto": "自动（有httpx真流式，否则假流式）",
        "stream_true": "真流式（需要 httpx）", "stream_fake": "假流式（快速逐字输出）",
        "fake_delay": "假流式延迟(ms)", "search_title": "联网搜索",
        "search_hint": "使用 @search 后缀或搜索专用模型名",
        "copy_cmd": "复制测试命令",
        "app_settings": "应用设置", "minimize_tray": "关闭窗口时最小化到托盘",
        "auto_start": "启动应用时自动启动服务器",
        "open_config": "打开配置文件", "open_logs": "打开日志",
        "about": "关于", "lang_switch": "切换语言",
        "saved": "已保存", "server_running": "服务已运行", "server_stopped": "服务已停止",
        "refreshing": "刷新中...", "login_ok": "登录成功！", "login_fail": "登录失败",
        "opening_browser": "正在打开浏览器，请手动登录...",
        "ext_not_found": "扩展目录未找到", "playwright_missing": "未安装 Playwright",
        "proxy_config": "代理配置", "proxy_type": "代理类型",
        "no_proxy": "无代理", "http_proxy": "HTTP 代理",
        "socks5_proxy": "SOCKS5 代理", "proxy_addr": "代理地址",
    },
    "en": {
        "home": "Home", "server": "Server", "cookie": "Cookie",
        "stream": "Streaming", "search": "Web Search", "settings": "Settings",
        "welcome": "Welcome to Gemini2API",
        "subtitle": "Gemini Web to OpenAI-compatible API proxy",
        "status_run": "Status: Running", "status_stop": "Status: Stopped",
        "start": "Start Server", "stop": "Stop Server", "dashboard": "Open Dashboard",
        "quick_start": "Quick Start",
        "step1": "1. Configure Server, Cookie, Stream in sidebar",
        "step2": "2. Click 'Start Server' to launch the API",
        "step3": "3. Connect with any OpenAI-compatible client",
        "step4": "4. Close window minimizes to tray (server keeps running)",
        "step5": "5. Access http://localhost:8081/dashboard for dashboard",
        "network": "Network", "port": "Port", "host": "Host",
        "proxy": "Proxy", "proxy_hint": "e.g. http://127.0.0.1:7890",
        "api_config": "API Config", "api_keys": "API Keys",
        "api_keys_hint": "Comma separated, empty = no auth",
        "default_model": "Default Model", "save": "Save",
        "cookie_source": "Cookie Source", "auto_extract": "Auto-extract cookies on startup",
        "auto_refresh": "Auto Refresh", "interval": "Interval (hours)",
        "refresh_now": "Refresh Now", "browser_login": "Browser Login",
        "edge_ext": "Edge Extension", "edge_ext_desc": "Install Edge extension for auto cookie push",
        "open_ext": "Open Extension Folder",
        "stream_mode": "Stream Mode", "stream_auto": "Auto (real if httpx available, else fake)",
        "stream_true": "True (real streaming, needs httpx)", "stream_fake": "Fake (fast char-by-char)",
        "fake_delay": "Fake Delay (ms)", "search_title": "Web Search",
        "search_hint": "Use @search suffix or search model names",
        "copy_cmd": "Copy Test Command",
        "app_settings": "Application", "minimize_tray": "Minimize to tray on close",
        "auto_start": "Auto-start server on app launch",
        "open_config": "Open Config File", "open_logs": "Open Logs",
        "about": "About", "lang_switch": "Switch Language",
        "saved": "Saved", "server_running": "Server running", "server_stopped": "Server stopped",
        "refreshing": "Refreshing...", "login_ok": "Login successful!", "login_fail": "Login failed",
        "opening_browser": "Opening browser, please log in...",
        "ext_not_found": "Extension folder not found", "playwright_missing": "Playwright not installed",
        "proxy_config": "Proxy", "proxy_type": "Proxy Type",
        "no_proxy": "No Proxy", "http_proxy": "HTTP Proxy",
        "socks5_proxy": "SOCKS5 Proxy", "proxy_addr": "Proxy Address",
    },
}


def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _create_icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill="#0078D4")
    draw.text((18, 10), "G", fill="white")
    return img


class ServerThread(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.config = config
        self.running = False

    def run(self):
        self.running = True
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from gemini_web2api.config import CONFIG
            from gemini_web2api.server import GeminiHandler, ThreadedServer
            from gemini_web2api import cookie_manager
            CONFIG.update(self.config)
            if self.config.get("auto_cookie"):
                cookie_str, sapisid = cookie_manager.extract_cookies()
                if cookie_str:
                    cookie_manager.write_cookie_file(cookie_str, sapisid, COOKIE_FILE)
                    CONFIG["cookie_file"] = COOKIE_FILE
            if self.config.get("auto_refresh_hours"):
                cookie_manager.start_auto_refresh(int(self.config["auto_refresh_hours"]))
            port = CONFIG["port"]
            self.server = ThreadedServer(("0.0.0.0", port), GeminiHandler)
            self.server.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.running = False

    def stop(self):
        if hasattr(self, "server"):
            self.server.shutdown()


class AnimatedFrame(ctk.CTkFrame):
    def fade_in(self, duration=150):
        steps = 8
        delay = duration // steps
        for i in range(steps + 1):
            alpha = i / steps
            try:
                self.winfo_toplevel().after(i * delay, lambda a=alpha: self._set_alpha(a))
            except Exception:
                pass

    def _set_alpha(self, alpha):
        try:
            fg = self.cget("fg_color")
        except Exception:
            pass


class GeminiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.lang_code = "zh"
        self.t = LANG["zh"]
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("960x660")
        self.minsize(860, 600)
        self.configure(fg_color=BG_DARK)
        self.server_thread = None
        self.tray_icon = None
        self._is_minimized = False
        self.config = self._load_config()
        self.lang_code = self.config.get("lang", "zh")
        self.t = LANG.get(self.lang_code, LANG["zh"])

        self._build_sidebar()
        self._build_content()
        self._show_page("home")
        self._start_tray()
        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self.after(200, self._check_server)
        self.after(1000, self._try_auto_start)

    def t(self, key):
        return LANG.get(self.lang_code, LANG["zh"]).get(key, key)

    def _try_auto_start(self):
        if self.config.get("auto_start_server"):
            self._start_server()

    def _load_config(self):
        default = {
            "port": 8081, "host": "0.0.0.0", "default_model": "gemini-3.5-flash",
            "proxy": None, "proxy_type": "none", "api_keys": [],
            "cookie_file": COOKIE_FILE, "auto_cookie": False,
            "auto_refresh_hours": None, "stream_mode": "auto",
            "fake_stream_delay_ms": 5, "cookie_source": "auto",
            "log_requests": True, "auto_start_server": False,
            "minimize_to_tray": True, "lang": "zh",
        }
        try:
            with open(CONFIG_FILE) as f:
                default.update(json.load(f))
        except Exception:
            pass
        return default

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _start_tray(self):
        try:
            import pystray
            from PIL import Image
            image = _create_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem(lambda item: self.t["home"] if hasattr(self, 't') else "Show", self._tray_show, default=True),
                pystray.MenuItem(lambda item: self.t["dashboard"], self._tray_dashboard),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(lambda item: self.t["start"], self._tray_start),
                pystray.MenuItem(lambda item: self.t["stop"], self._tray_stop),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._tray_quit),
            )
            self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            pass

    def _tray_show(self, *_): self.after(0, self._restore_from_tray)
    def _tray_dashboard(self, *_):
        webbrowser.open(f"http://localhost:{self.config.get('port', 8081)}/dashboard")
    def _tray_start(self, *_): self.after(0, self._start_server)
    def _tray_stop(self, *_): self.after(0, self._stop_server)
    def _tray_quit(self, *_):
        if self.tray_icon: self.tray_icon.stop()
        self.after(0, self._real_quit)

    def _minimize_to_tray(self):
        if not self.config.get("minimize_to_tray", True):
            self._real_quit(); return
        self._is_minimized = True
        self.withdraw()

    def _restore_from_tray(self):
        if self._is_minimized:
            self._is_minimized = False
            self.deiconify(); self.lift(); self.focus_force()

    def _real_quit(self):
        if self.server_thread and self.server_thread.running:
            self.server_thread.stop()
        if self.tray_icon:
            try: self.tray_icon.stop()
            except Exception: pass
        self.destroy()
        os._exit(0)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=BG_MICA)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(20, 20))
        ctk.CTkLabel(top, text=APP_NAME, font=("Segoe UI Semibold", 20),
                     text_color=TEXT_ACCENT).pack(anchor="w")
        ctk.CTkLabel(top, text=f"v{APP_VERSION}", font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w")

        self.nav_btns = {}
        for key in ["home", "server", "cookie", "stream", "search", "settings"]:
            btn = ctk.CTkButton(
                self.sidebar, text=self.t.get(key, key), anchor="w",
                font=("Segoe UI", 13), height=36, corner_radius=8,
                fg_color="transparent", text_color=TEXT_SEC,
                hover_color=BG_HOVER, command=lambda k=key: self._show_page(k)
            )
            btn.pack(fill="x", padx=8, pady=1)
            self.nav_btns[key] = btn

        ctk.CTkLabel(self.sidebar, text="", fg_color="transparent").pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 16))
        self.status_lbl = ctk.CTkLabel(bottom, text="● " + self.t.get("status_stop", "Stopped"),
                                        font=("Segoe UI", 11), text_color=ERROR)
        self.status_lbl.pack(anchor="w")
        lang_btn = ctk.CTkButton(bottom, text="中文 / EN", font=("Segoe UI", 11),
                                  height=28, corner_radius=6, fg_color=BG_CARD,
                                  hover_color=BG_HOVER, text_color=TEXT_SEC,
                                  command=self._toggle_lang)
        lang_btn.pack(fill="x", pady=(8, 0))

    def _toggle_lang(self):
        self.lang_code = "en" if self.lang_code == "zh" else "zh"
        self.config["lang"] = self.lang_code
        self._save_config()
        self._rebuild_ui()

    def _rebuild_ui(self):
        self.t = LANG.get(self.lang_code, LANG["zh"])
        for key, btn in self.nav_btns.items():
            btn.configure(text=self.t.get(key, key))
        self.status_lbl.configure(text="● " + (self.t["status_run"] if self.server_thread and self.server_thread.running else self.t["status_stop"]))
        for name, frame in self.pages.items():
            frame.destroy()
        self.pages = {}
        for name in ["home", "server", "cookie", "stream", "search", "settings"]:
            frame = ctk.CTkFrame(self.content, fg_color=BG_DARK, corner_radius=0)
            self.pages[name] = frame
        self._build_home_page()
        self._build_server_page()
        self._build_cookie_page()
        self._build_stream_page()
        self._build_search_page()
        self._build_settings_page()
        self._show_page("home")

    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)
        self.pages = {}
        for name in ["home", "server", "cookie", "stream", "search", "settings"]:
            frame = ctk.CTkFrame(self.content, fg_color=BG_DARK, corner_radius=0)
            self.pages[name] = frame
        self._build_home_page()
        self._build_server_page()
        self._build_cookie_page()
        self._build_stream_page()
        self._build_search_page()
        self._build_settings_page()

    def _show_page(self, name):
        for k, f in self.pages.items():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True, padx=28, pady=24)
        for k, btn in self.nav_btns.items():
            btn.configure(fg_color=ACCENT if k == name else "transparent",
                         text_color="white" if k == name else TEXT_SEC)

    def _label(self, parent, key, font=("Segoe UI Semibold", 18), **kw):
        if "text_color" not in kw:
            kw["text_color"] = TEXT_PRIMARY
        return ctk.CTkLabel(parent, text=self.t.get(key, key), font=font, **kw)

    def _card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)
        return inner

    def _input(self, parent, key, value, options=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row, text=self.t.get(key, key), font=("Segoe UI", 12),
                     text_color=TEXT_SEC, width=130, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(value) if value is not None else "")
        if options:
            ctk.CTkOptionMenu(row, values=options, variable=var,
                              font=("Segoe UI", 12), width=300,
                              fg_color=BG_INPUT, button_color=ACCENT,
                              corner_radius=8).pack(side="left", padx=(8, 0))
        else:
            ctk.CTkEntry(row, textvariable=var, font=("Segoe UI", 12),
                         width=300, fg_color=BG_INPUT, border_color=BORDER,
                         corner_radius=8, text_color=TEXT_PRIMARY).pack(side="left", padx=(8, 0))
        return var

    def _btn(self, parent, key, command, color=ACCENT, width=140):
        return ctk.CTkButton(parent, text=self.t.get(key, key), command=command,
                             font=("Segoe UI Semibold", 12), height=36,
                             corner_radius=8, fg_color=color,
                             hover_color=ACCENT_HOVER if color == ACCENT else color,
                             width=width)

    def _build_home_page(self):
        f = self.pages["home"]
        self._label(f, "welcome").pack(anchor="w", pady=(0, 4))
        self._label(f, "subtitle", font=("Segoe UI", 12), text_color=TEXT_SEC).pack(anchor="w", pady=(0, 16))

        card = self._card(f)
        self.home_status = ctk.CTkLabel(card, text=self.t["status_stop"],
                                         font=("Segoe UI Semibold", 15), text_color=ERROR)
        self.home_status.pack(anchor="w", pady=(0, 10))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x")
        self._btn(row, "start", self._start_server, color=SUCCESS).pack(side="left", padx=(0, 8))
        self._btn(row, "stop", self._stop_server, color=CLOSE_RED).pack(side="left", padx=(0, 8))
        self._btn(row, "dashboard", self._open_dashboard).pack(side="left")

        card2 = self._card(f)
        self._label(card2, "quick_start", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        for key in ["step1", "step2", "step3", "step4", "step5"]:
            ctk.CTkLabel(card2, text=self.t.get(key, key), font=("Segoe UI", 11),
                         text_color=TEXT_SEC, anchor="w").pack(anchor="w", pady=1)

        card3 = self._card(f)
        self._label(card3, "edge_ext", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(card3, text=self.t.get("edge_ext_desc", ""), font=("Segoe UI", 11),
                     text_color=TEXT_SEC).pack(anchor="w")
        self._btn(card3, "open_ext", self._open_extension, width=180).pack(anchor="w", pady=(8, 0))

    def _build_server_page(self):
        f = self.pages["server"]
        self._label(f, "server", font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(0, 12))

        card = self._card(f)
        self._label(card, "network", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.port_var = self._input(card, "port", self.config.get("port", 8081))
        self.host_var = self._input(card, "host", self.config.get("host", "0.0.0.0"))

        card2 = self._card(f)
        self._label(card2, "proxy_config", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        proxy_type = self.config.get("proxy_type", "none")
        if self.config.get("proxy"):
            proxy_type = "http" if "socks" not in self.config["proxy"].lower() else "socks5"
        self.proxy_type_var = self._input(card2, "proxy_type",
            self.t.get(f"{proxy_type}_proxy", proxy_type),
            options=[self.t["no_proxy"], self.t["http_proxy"], self.t["socks5_proxy"]])
        self.proxy_var = self._input(card2, "proxy_addr",
            self.config.get("proxy", ""), )
        ctk.CTkLabel(card2, text=self.t.get("proxy_hint", ""), font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w", pady=(0, 4))

        card3 = self._card(f)
        self._label(card3, "api_config", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.apikeys_var = self._input(card3, "api_keys",
            ",".join(self.config.get("api_keys", [])))
        ctk.CTkLabel(card3, text=self.t.get("api_keys_hint", ""), font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w", pady=(0, 8))
        self.default_model_var = self._input(card3, "default_model",
            self.config.get("default_model", "gemini-3.5-flash"),
            options=["gemini-3.5-flash", "gemini-3.5-flash-thinking",
                     "gemini-3.1-pro", "gemini-auto", "gemini-flash-lite"])
        self._btn(card3, "save", self._save_server_config).pack(anchor="w", pady=(8, 0))

    def _save_server_config(self):
        self.config["port"] = int(self.port_var.get())
        self.config["host"] = self.host_var.get()
        proxy = self.proxy_var.get().strip()
        ptype = self.proxy_type_var.get()
        if ptype == self.t["no_proxy"] or not proxy:
            self.config["proxy"] = None
            self.config["proxy_type"] = "none"
        elif ptype == self.t["socks5_proxy"]:
            self.config["proxy"] = proxy if proxy.startswith("socks5") else f"socks5://{proxy}"
            self.config["proxy_type"] = "socks5"
        else:
            self.config["proxy"] = proxy if proxy.startswith("http") else f"http://{proxy}"
            self.config["proxy_type"] = "http"
        self.config["default_model"] = self.default_model_var.get()
        keys = self.apikeys_var.get().strip()
        self.config["api_keys"] = [k.strip() for k in keys.split(",") if k.strip()] if keys else []
        self._save_config()
        self._toast(self.t["saved"])

    def _build_cookie_page(self):
        f = self.pages["cookie"]
        self._label(f, "cookie", font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(0, 12))

        card = self._card(f)
        self._label(card, "cookie_source", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.cookie_source_var = self._input(card, "cookie_source",
            self.config.get("cookie_source", "auto"), options=["auto", "playwright"])
        self.auto_cookie_var = ctk.BooleanVar(value=self.config.get("auto_cookie", False))
        ctk.CTkCheckBox(card, text=self.t["auto_extract"], variable=self.auto_cookie_var,
                        font=("Segoe UI", 12), text_color=TEXT_SEC, fg_color=ACCENT,
                        hover_color=ACCENT_HOVER).pack(anchor="w", pady=(8, 0))

        card2 = self._card(f)
        self._label(card2, "auto_refresh", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.refresh_var = self._input(card2, "interval",
            str(self.config.get("auto_refresh_hours", "")))

        card3 = self._card(f)
        self._label(card3, "edge_ext", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(card3, text=self.t.get("edge_ext_desc", ""), font=("Segoe UI", 11),
                     text_color=TEXT_SEC).pack(anchor="w")
        self._btn(card3, "open_ext", self._open_extension, width=180).pack(anchor="w", pady=(8, 0))

        card4 = self._card(f)
        row = ctk.CTkFrame(card4, fg_color="transparent")
        row.pack(fill="x")
        self._btn(row, "refresh_now", self._cookie_refresh).pack(side="left", padx=(0, 8))
        self._btn(row, "browser_login", self._browser_login, color="#7C3AED").pack(side="left", padx=(0, 8))
        self._btn(row, "save", self._save_cookie_config).pack(side="left")
        self.cookie_status = ctk.CTkLabel(card4, text="", font=("Segoe UI", 11), text_color=TEXT_SEC)
        self.cookie_status.pack(anchor="w", pady=(8, 0))

    def _save_cookie_config(self):
        self.config["cookie_source"] = self.cookie_source_var.get()
        self.config["auto_cookie"] = self.auto_cookie_var.get()
        r = self.refresh_var.get().strip()
        self.config["auto_refresh_hours"] = int(r) if r else None
        self._save_config()
        self._toast(self.t["saved"])

    def _cookie_refresh(self):
        def do():
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from gemini_web2api.cookie_manager import manual_refresh
                r = manual_refresh()
                self.after(0, lambda: self.cookie_status.configure(
                    text=f"{'OK' if r.get('success') else 'FAIL'}: {r.get('status','')}",
                    text_color=SUCCESS if r.get("success") else ERROR))
            except Exception as e:
                self.after(0, lambda: self.cookie_status.configure(text=str(e), text_color=ERROR))
        threading.Thread(target=do, daemon=True).start()
        self.cookie_status.configure(text=self.t["refreshing"], text_color=TEXT_SEC)

    def _browser_login(self):
        def do():
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from gemini_web2api import playwright_cookie
                from gemini_web2api.cookie_manager import write_cookie_file
                if not playwright_cookie.is_playwright_available():
                    self.after(0, lambda: self._toast(self.t["playwright_missing"]))
                    return
                self.after(0, lambda: self._toast(self.t["opening_browser"]))
                r = playwright_cookie.launch_browser_login()
                if r.get("success"):
                    write_cookie_file(r["cookies"], r.get("sapisid", ""), COOKIE_FILE)
                    self.config["cookie_file"] = COOKIE_FILE
                    self.after(0, lambda: self._toast(self.t["login_ok"]))
                else:
                    self.after(0, lambda: self._toast(self.t["login_fail"]))
            except Exception as e:
                self.after(0, lambda: self._toast(str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _build_stream_page(self):
        f = self.pages["stream"]
        self._label(f, "stream", font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(0, 12))

        card = self._card(f)
        self._label(card, "stream_mode", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        modes = ["auto", "true", "fake"]
        self.stream_mode_var = self._input(card, "stream_mode",
            self.config.get("stream_mode", "auto"), options=modes)
        ctk.CTkLabel(card, text=f"auto: {self.t['stream_auto']}", font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w", pady=1)
        ctk.CTkLabel(card, text=f"true: {self.t['stream_true']}", font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w", pady=1)
        ctk.CTkLabel(card, text=f"fake: {self.t['stream_fake']}", font=("Segoe UI", 10),
                     text_color=TEXT_SEC).pack(anchor="w", pady=1)

        card2 = self._card(f)
        self._label(card2, "fake_delay", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.delay_var = self._input(card2, "fake_delay",
            str(self.config.get("fake_stream_delay_ms", 5)))
        self._btn(card2, "save", self._save_stream_config).pack(anchor="w", pady=(8, 0))

    def _save_stream_config(self):
        self.config["stream_mode"] = self.stream_mode_var.get()
        self.config["fake_stream_delay_ms"] = int(self.delay_var.get())
        self._save_config()
        self._toast(self.t["saved"])

    def _build_search_page(self):
        f = self.pages["search"]
        self._label(f, "search", font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(0, 12))

        card = self._card(f)
        self._label(card, "search_title", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(card, text=self.t.get("search_hint", ""), font=("Segoe UI", 11),
                     text_color=TEXT_SEC).pack(anchor="w", pady=(0, 8))
        examples = [
            "  gemini-3.5-flash-search",
            "  gemini-3.5-flash-thinking-search",
            "  gemini-3.1-pro-search",
            "  gemini-3.5-flash@search",
            "  gemini-3.5-flash-thinking@search@think=2",
        ]
        for ex in examples:
            ctk.CTkLabel(card, text=ex, font=("Consolas", 11),
                         text_color=TEXT_ACCENT, anchor="w").pack(anchor="w", pady=1)
        self._btn(card, "copy_cmd", self._copy_search, width=180).pack(anchor="w", pady=(10, 0))

    def _copy_search(self):
        port = self.config.get("port", 8081)
        cmd = f'curl http://localhost:{port}/v1/chat/completions -H "Content-Type: application/json" -d \'{{"model":"gemini-3.5-flash@search","messages":[{{"role":"user","content":"today news"}}]}}\''
        self.clipboard_clear()
        self.clipboard_append(cmd)
        self._toast("Copied!")

    def _build_settings_page(self):
        f = self.pages["settings"]
        self._label(f, "settings", font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(0, 12))

        card = self._card(f)
        self._label(card, "app_settings", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        self.tray_var = ctk.BooleanVar(value=self.config.get("minimize_to_tray", True))
        ctk.CTkCheckBox(card, text=self.t["minimize_tray"], variable=self.tray_var,
                        font=("Segoe UI", 12), text_color=TEXT_SEC, fg_color=ACCENT,
                        hover_color=ACCENT_HOVER).pack(anchor="w", pady=(0, 4))
        self.autostart_var = ctk.BooleanVar(value=self.config.get("auto_start_server", False))
        ctk.CTkCheckBox(card, text=self.t["auto_start"], variable=self.autostart_var,
                        font=("Segoe UI", 12), text_color=TEXT_SEC, fg_color=ACCENT,
                        hover_color=ACCENT_HOVER).pack(anchor="w", pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x")
        self._btn(row, "save", self._save_settings).pack(side="left", padx=(0, 8))
        self._btn(row, "open_config", self._open_config, width=160).pack(side="left", padx=(0, 8))
        self._btn(row, "open_logs", self._open_logs, width=120).pack(side="left")

        card2 = self._card(f)
        self._label(card2, "about", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        for line in [f"{APP_NAME} v{APP_VERSION}", "Gemini Web -> OpenAI API",
                     "Flash / Pro / Thinking / Search / Streaming", "MIT License"]:
            ctk.CTkLabel(card2, text=line, font=("Segoe UI", 11),
                         text_color=TEXT_SEC).pack(anchor="w", pady=1)

    def _save_settings(self):
        self.config["minimize_to_tray"] = self.tray_var.get()
        self.config["auto_start_server"] = self.autostart_var.get()
        self._save_config()
        self._toast(self.t["saved"])

    def _open_config(self):
        p = os.path.abspath(CONFIG_FILE)
        if os.path.exists(p): os.startfile(p)

    def _open_logs(self):
        webbrowser.open(f"http://localhost:{self.config.get('port', 8081)}/dashboard")

    def _open_extension(self):
        p = resource_path("extension")
        if os.path.exists(p): os.startfile(p)
        else: self._toast(self.t["ext_not_found"])

    def _start_server(self):
        if self.server_thread and self.server_thread.running:
            self._toast(self.t["server_running"]); return
        self._save_config()
        self.server_thread = ServerThread(self.config)
        self.server_thread.start()
        time.sleep(0.5)
        self._update_status()
        self._toast(f"{self.t['server_running']} :{self.config.get('port', 8081)}")

    def _stop_server(self):
        if self.server_thread and self.server_thread.running:
            self.server_thread.stop()
            self.server_thread = None
            self._update_status()
            self._toast(self.t["server_stopped"])

    def _open_dashboard(self):
        webbrowser.open(f"http://localhost:{self.config.get('port', 8081)}/dashboard")

    def _update_status(self):
        running = self.server_thread and self.server_thread.running
        if running:
            self.home_status.configure(text=self.t["status_run"], text_color=SUCCESS)
            self.status_lbl.configure(text="● " + self.t["status_run"], text_color=SUCCESS)
        else:
            self.home_status.configure(text=self.t["status_stop"], text_color=ERROR)
            self.status_lbl.configure(text="● " + self.t["status_stop"], text_color=ERROR)

    def _check_server(self):
        self._update_status()
        self.after(2000, self._check_server)

    def _toast(self, msg):
        try:
            t = ctk.CTkToplevel(self)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            w, h = 340, 44
            x = self.winfo_x() + (self.winfo_width() - w) // 2
            y = self.winfo_y() + self.winfo_height() - 70
            t.geometry(f"{w}x{h}+{x}+{y}")
            t.configure(fg_color=BG_CARD)
            ctk.CTkLabel(t, text=f"  {msg}", font=("Segoe UI", 12),
                         text_color=TEXT_PRIMARY, anchor="w").pack(fill="both", expand=True)
            t.after(2500, t.destroy)
        except Exception:
            pass


def main():
    app = GeminiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
