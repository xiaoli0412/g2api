"""Server configuration page."""

from gemini_web2api.models import MODELS
from gui.components import FluentButton, FluentToggle
from .page_utils import Page


class ServerPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent, "server")
        self._create_ui()

    def _create_ui(self):
        self.title("server")
        cfg = self.main_window.config

        network = self.card("network")
        self.port_input = self.input_row(network, "port", cfg.get("port", 8081))
        self.host_input = self.input_row(network, "host", cfg.get("host", "0.0.0.0"))

        proxy = self.card("proxy_config")
        self.proxy_type = self.combo_row(proxy, "proxy_type", [self.t("no_proxy"), self.t("http_proxy"), self.t("socks5_proxy")])
        current_proxy = cfg.get("proxy") or ""
        if current_proxy.startswith("socks"):
            self.proxy_type.setCurrentText(self.t("socks5_proxy"))
        elif current_proxy:
            self.proxy_type.setCurrentText(self.t("http_proxy"))
        self.proxy_input = self.input_row(proxy, "proxy_addr", current_proxy, self.t("proxy_hint"))

        api = self.card("api_config")
        self.api_keys_input = self.input_row(api, "api_keys", ",".join(cfg.get("api_keys", [])))
        self.model_combo = self.combo_row(api, "default_model", sorted(MODELS.keys()), cfg.get("default_model", "gemini-3.5-flash"))

        pool = self.card("proxy_pool")
        self.pool_toggle = FluentToggle(cfg.get("proxy_pool_enabled", False))
        self.rotation_toggle = FluentToggle(cfg.get("proxy_rotation", False))
        for text, toggle in [("enable_proxy_pool", self.pool_toggle), ("enable_proxy_rotation", self.rotation_toggle)]:
            row = self.row(pool, text)
            row.addWidget(toggle)
            row.addStretch()
        self.strategy_combo = self.combo_row(pool, "proxy_strategy", ["round_robin", "random", "fastest", "least_connections", "ip_hash"], cfg.get("proxy_pool_strategy", "round_robin"))
        self.subs_edit = self.text_row(pool, "proxy_subs", "\n".join(cfg.get("proxy_subscriptions", [])))
        self.proxy_list_edit = self.text_row(pool, "proxy_list", "\n".join(cfg.get("proxies", [])))
        save = FluentButton(self.t("save"))
        save.clicked.connect(self._save_config)
        pool.layout.addWidget(save)
        self.root.addStretch()

    def _save_config(self):
        cfg = self.main_window.config
        cfg["port"] = int(self.port_input.text() or 8081)
        cfg["host"] = self.host_input.text() or "0.0.0.0"
        proxy_value = self.proxy_input.text().strip()
        proxy_type = self.proxy_type.currentText()
        if not proxy_value or proxy_type == self.t("no_proxy"):
            cfg["proxy"] = None
        elif proxy_type == self.t("socks5_proxy"):
            cfg["proxy"] = proxy_value if proxy_value.startswith("socks5://") else f"socks5://{proxy_value}"
        else:
            cfg["proxy"] = proxy_value if proxy_value.startswith("http") else f"http://{proxy_value}"
        keys = self.api_keys_input.text().strip()
        cfg["api_keys"] = [k.strip() for k in keys.split(",") if k.strip()] if keys else []
        cfg["default_model"] = self.model_combo.currentText()
        cfg["proxy_pool_enabled"] = self.pool_toggle.isChecked()
        cfg["proxy_rotation"] = self.rotation_toggle.isChecked()
        cfg["proxy_pool_strategy"] = self.strategy_combo.currentText()
        cfg["proxy_subscriptions"] = [s.strip() for s in self.subs_edit.toPlainText().splitlines() if s.strip()]
        cfg["proxies"] = [s.strip() for s in self.proxy_list_edit.toPlainText().splitlines() if s.strip()]
        self.main_window.save_config()
        self.main_window.toast(self.t("saved"))
