"""Compact proxy workbench page."""

import threading
import urllib.parse

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from gemini_web2api.config import CONFIG
from gui.components import FluentButton
from gui.styles import COLORS, SPACING, qss_font
from .page_utils import Page


class ProxyPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent, "proxy_workbench")
        self.summary_labels = {}
        self._create_ui()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)

    def _create_ui(self):
        self.title("proxy_workbench", self.t("proxy_workbench_desc"))

        summary = self.card("proxy_health_summary")
        for key in ("total_nodes", "available_nodes", "checking_nodes", "cooldown_nodes", "provider_count", "group_count", "last_check"):
            self.summary_labels[key] = self.info_row(summary, key, "--", numeric=key.endswith("nodes") or key in {"provider_count", "group_count"})

        importer = self.card("proxy_import")
        self.provider_input = self.input_row(importer, "provider", "manual")
        self.subs_edit = self.text_row(importer, "import_subscriptions", "\n".join(self.main_window.config.get("proxy_subscriptions", [])))
        self.links_edit = self.text_row(importer, "import_proxy_links", "\n".join(self.main_window.config.get("proxies", [])))
        actions = self.row(importer, "actions")
        import_btn = FluentButton(self.t("import_sources"))
        refresh_btn = FluentButton(self.t("refresh_now"))
        check_btn = FluentButton(self.t("check_stale"))
        check_all_btn = FluentButton(self.t("check_all"))
        import_btn.clicked.connect(self.import_sources)
        refresh_btn.clicked.connect(self.refresh)
        check_btn.clicked.connect(lambda: self.check_health(only_stale=True))
        check_all_btn.clicked.connect(lambda: self.check_health(only_stale=False))
        for btn in (import_btn, refresh_btn, check_btn, check_all_btn):
            actions.addWidget(btn)
        actions.addStretch()

        accounts = self.card("account_bindings")
        binding_lines = []
        for account in self.main_window.config.get("accounts", []) or []:
            account_id = account.get("id")
            proxy = account.get("primary_proxy") or account.get("proxy")
            if account_id and proxy:
                binding_lines.append(f"{account_id}={proxy}")
        self.bindings_edit = self.text_row(accounts, "account_bindings", "\n".join(binding_lines))
        bind_actions = self.row(accounts, "actions")
        save_bindings_btn = FluentButton(self.t("save_bindings"))
        save_bindings_btn.clicked.connect(self.save_account_bindings)
        bind_actions.addWidget(save_bindings_btn)
        bind_actions.addStretch()

        nodes = self.card("proxy_nodes_compact")
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            self.t("health_status"),
            self.t("proxy_name"),
            self.t("provider"),
            self.t("proxy_type"),
            self.t("host"),
            self.t("latency"),
            self.t("failures"),
            self.t("last_check"),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: transparent;
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                gridline-color: {COLORS['border']};
                {qss_font('body')}
            }}
            QHeaderView::section {{
                background: {COLORS['control_bg']};
                color: {COLORS['text_secondary']};
                border: none;
                padding: 6px;
                {qss_font('column')}
            }}
            QTableWidget::item {{ padding: 4px; }}
        """)
        nodes.layout.addWidget(self.table)

        groups = self.card("proxy_groups_compact")
        self.group_table = QTableWidget(0, 5)
        self.group_table.setHorizontalHeaderLabels([
            self.t("proxy_group"),
            self.t("proxy_type"),
            self.t("available_nodes"),
            self.t("selected_proxy"),
            self.t("inflight"),
        ])
        self.group_table.verticalHeader().setVisible(False)
        self.group_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.group_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.group_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.group_table.setStyleSheet(self.table.styleSheet())
        groups.layout.addWidget(self.group_table)

    def _run_bg(self, label, func):
        self.main_window.toast(self.t(label))

        def run():
            try:
                result = func()
                self.main_window.post_ui(lambda: self._finish_bg(result))
            except Exception as exc:
                self.main_window.post_ui(lambda: self.main_window.toast(str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def _finish_bg(self, result):
        self.refresh()
        message = result.get("message") if isinstance(result, dict) else ""
        self.main_window.toast(message or self.t("saved"))

    def import_sources(self):
        subscriptions = [line.strip() for line in self.subs_edit.toPlainText().splitlines() if line.strip()]
        direct_links = [line.strip() for line in self.links_edit.toPlainText().splitlines() if line.strip()]
        provider = self.provider_input.text().strip() or "manual"

        def work():
            from gemini_web2api.admin import handle_admin_request
            payload, status = handle_admin_request("/admin/proxy/import", "POST", {
                "provider": provider,
                "subscriptions": subscriptions,
                "direct_links": direct_links,
            })
            if status >= 400:
                raise RuntimeError(payload.get("error") or "proxy import failed")
            self.main_window.config["proxy_pool_enabled"] = True
            self.main_window.config["proxy_subscriptions"] = CONFIG.get("proxy_subscriptions", [])
            self.main_window.config["proxies"] = CONFIG.get("proxies", [])
            return payload

        self._run_bg("importing", work)

    def check_health(self, only_stale=True):
        def work():
            from gemini_web2api.admin import handle_admin_request
            payload, status = handle_admin_request("/admin/proxy/test-all", "POST", {
                "only_stale": only_stale,
            })
            if status >= 400:
                raise RuntimeError(payload.get("error") or "proxy health check failed")
            return payload

        self._run_bg("checking", work)

    def save_account_bindings(self):
        entries = []
        for line in self.bindings_edit.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            if "=" in line:
                account_id, proxy = line.split("=", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                account_id, proxy = parts
            account_id = account_id.strip()
            proxy = proxy.strip()
            if account_id and proxy:
                entries.append((account_id, proxy))

        def work():
            from gemini_web2api.admin import handle_admin_request
            saved = 0
            for account_id, proxy in entries:
                path = f"/admin/accounts/{urllib.parse.quote(account_id, safe='')}/bind-proxy"
                payload, status = handle_admin_request(path, "POST", {"primary_proxy": proxy})
                if status >= 400:
                    raise RuntimeError(payload.get("error") or "account binding failed")
                saved += 1
            self.main_window.config["accounts"] = CONFIG.get("accounts", [])
            self.main_window.config["proxy_account_bindings"] = CONFIG.get("proxy_account_bindings", [])
            return {"success": True, "message": f"{self.t('saved')}: {saved}"}

        self._run_bg("saving", work)

    def refresh(self):
        try:
            from gemini_web2api.admin import get_proxy_status
            status = get_proxy_status()
            runtime = status.get("runtime") or {}
            health = runtime.get("health") or {}
            statuses = health.get("statuses") or {}
            providers = runtime.get("providers") or []
            values = {
                "total_nodes": health.get("total_nodes", runtime.get("total_nodes", 0)),
                "available_nodes": health.get("available_nodes", runtime.get("available_nodes", 0)),
                "checking_nodes": statuses.get("checking", 0),
                "cooldown_nodes": statuses.get("cooldown", 0),
                "provider_count": len(providers),
                "group_count": len(runtime.get("groups") or []),
                "last_check": self._fmt_time(health.get("last_check")),
            }
            for key, value in values.items():
                self.summary_labels[key].setText(str(value))
            self._fill_nodes(runtime.get("nodes") or [])
            self._fill_groups(runtime.get("groups") or [])
        except Exception as exc:
            self.main_window.toast(str(exc))

    def _fill_nodes(self, nodes):
        self.table.setRowCount(len(nodes))
        for row, node in enumerate(nodes):
            values = [
                node.get("health_status") or ("healthy" if node.get("is_healthy") else "unhealthy"),
                node.get("name") or "",
                node.get("provider") or "manual",
                node.get("type") or "",
                node.get("host") or "",
                f"{node.get('latency_ms') or 0} ms",
                str(node.get("failure_count") or 0),
                self._fmt_time(node.get("last_check")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if col in (5, 6) else Qt.AlignLeft | Qt.AlignVCenter)
                if col == 0:
                    color = {
                        "healthy": "#7BD88F",
                        "checking": "#4CC9F0",
                        "stale": "#F2C86B",
                        "cooldown": "#F2C86B",
                        "unhealthy": "#FF5F6D",
                        "disabled": COLORS["text_disabled"],
                    }.get(str(value), COLORS["text_primary"])
                    item.setForeground(QtGuiColor(color))
                self.table.setItem(row, col, item)

    def _fill_groups(self, groups):
        self.group_table.setRowCount(len(groups))
        for row, group in enumerate(groups):
            values = [
                group.get("name") or "",
                group.get("type") or "",
                str(group.get("available") or 0),
                group.get("selected_name") or group.get("selected") or "",
                str(group.get("inflight") or 0),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if col in (2, 4) else Qt.AlignLeft | Qt.AlignVCenter)
                self.group_table.setItem(row, col, item)

    @staticmethod
    def _fmt_time(value):
        if not value:
            return "--"
        try:
            import time
            return time.strftime("%H:%M:%S", time.localtime(float(value)))
        except Exception:
            return "--"


def QtGuiColor(value):
    from PyQt5.QtGui import QColor
    return QColor(value)
