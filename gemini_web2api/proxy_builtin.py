"""
内置代理池 - 纯 Python 实现，零外部依赖，最小性能消耗

特性：
- 直接支持 HTTP/HTTPS/SOCKS5 代理
- 订阅解析（vmess/vless/ss/trojan/hy2/tuic）
- 自动健康检查和故障转移
- 代理测速
- 持久化缓存
- 多进程IP隔离
"""

import json
import base64
import re
import time
import random
import threading
import socket
import struct
import urllib.request
import urllib.parse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ProxyType(Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    DIRECT = "direct"


HEALTH_CHECKING = "checking"
HEALTH_HEALTHY = "healthy"
HEALTH_STALE = "stale"
HEALTH_COOLDOWN = "cooldown"
HEALTH_UNHEALTHY = "unhealthy"
HEALTH_DISABLED = "disabled"

GROUP_SELECTOR = "select"
GROUP_URL_TEST = "url-test"
GROUP_FALLBACK = "fallback"
GROUP_LOAD_BALANCE = "load-balance"


@dataclass
class ProxyNode:
    """代理节点"""
    name: str
    proxy_type: ProxyType
    host: str
    port: int
    username: str = ""
    password: str = ""
    raw_link: str = ""
    provider: str = "manual"
    source: str = "manual"

    # 状态
    latency_ms: float = 0
    is_healthy: bool = True
    health_status: str = HEALTH_HEALTHY
    failure_count: int = 0
    last_used: float = 0
    last_check: float = 0
    health_expires_at: float = 0
    cooldown_until: float = 0
    disabled: bool = False
    last_failure_reason: str = ""
    success_count: int = 0

    @property
    def node_id(self) -> str:
        raw = self.raw_link or self.url
        return f"{self.proxy_type.value}:{self.host}:{self.port}:{hash(raw) & 0xffffffff:x}"

    @property
    def url(self) -> str:
        if self.username:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

    @property
    def proxy_dict(self) -> Dict:
        return {
            "http": self.url,
            "https": self.url,
        }

    def selectable(self, now: float = None, status_ttl: int = 0, require_healthy: bool = True) -> bool:
        now = now or time.time()
        if self.disabled or self.health_status == HEALTH_DISABLED:
            return False
        if self.cooldown_until and self.cooldown_until > now:
            return False
        if self.health_status in {HEALTH_CHECKING, HEALTH_STALE, HEALTH_COOLDOWN, HEALTH_UNHEALTHY}:
            return False
        if require_healthy and not self.is_healthy:
            return False
        if status_ttl and self.last_check and now - self.last_check > status_ttl:
            self.health_status = HEALTH_STALE
            return False
        return True

    def to_dict(self) -> Dict:
        return {
            "id": self.node_id,
            "name": self.name,
            "type": self.proxy_type.value,
            "host": self.host,
            "port": self.port,
            "provider": self.provider,
            "source": self.source,
            "latency_ms": round(self.latency_ms, 1),
            "is_healthy": self.is_healthy,
            "health_status": self.health_status,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_check": self.last_check,
            "last_used": self.last_used,
            "health_expires_at": self.health_expires_at,
            "cooldown_until": self.cooldown_until,
            "last_failure_reason": self.last_failure_reason,
        }


@dataclass
class ProxyGroup:
    """2API-scoped proxy group inspired by Clash groups.

    This is intentionally not a system proxy/VPN feature. It only narrows and
    orders the exits that Gemini2API may use for upstream requests.
    """
    name: str
    group_type: str = GROUP_URL_TEST
    proxies: List[str] = field(default_factory=lambda: ["*"])
    providers: List[str] = field(default_factory=lambda: ["*"])
    exclude_providers: List[str] = field(default_factory=list)
    filter: str = ""
    exclude_filter: str = ""
    selected: str = ""
    tolerance_ms: int = 150
    test_url: str = "http://httpbin.org/ip"

    @classmethod
    def from_config(cls, data: Dict) -> "ProxyGroup":
        data = dict(data or {})
        group_type = str(data.get("type") or data.get("group_type") or GROUP_URL_TEST).lower()
        if group_type == "selector":
            group_type = GROUP_SELECTOR
        if group_type == "urltest":
            group_type = GROUP_URL_TEST
        if group_type == "loadbalance":
            group_type = GROUP_LOAD_BALANCE
        if group_type not in {GROUP_SELECTOR, GROUP_URL_TEST, GROUP_FALLBACK, GROUP_LOAD_BALANCE}:
            group_type = GROUP_URL_TEST
        return cls(
            name=str(data.get("name") or "GLOBAL"),
            group_type=group_type,
            proxies=_as_list(data.get("proxies"), default=["*"]),
            providers=_as_list(data.get("providers"), default=["*"]),
            exclude_providers=_as_list(data.get("exclude_providers") or data.get("exclude-providers")),
            filter=str(data.get("filter") or ""),
            exclude_filter=str(data.get("exclude_filter") or data.get("exclude-filter") or ""),
            selected=str(data.get("selected") or ""),
            tolerance_ms=int(data.get("tolerance_ms") or data.get("tolerance") or 150),
            test_url=str(data.get("test_url") or data.get("url") or "http://httpbin.org/ip"),
        )

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.group_type,
            "proxies": self.proxies,
            "providers": self.providers,
            "exclude_providers": self.exclude_providers,
            "filter": self.filter,
            "exclude_filter": self.exclude_filter,
            "selected": self.selected,
            "tolerance_ms": self.tolerance_ms,
            "test_url": self.test_url,
        }


@dataclass
class ProxyPool:
    """代理池"""
    nodes: List[ProxyNode] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _index: int = 0
    _strategy: str = "round_robin"
    _last_update: float = 0
    _update_interval: int = 3600
    _subscriptions: List[str] = field(default_factory=list)
    _health_check_thread: threading.Thread = None
    _running: bool = False
    _status_ttl: int = 600
    _probe_concurrency: int = 8
    _probe_timeout: int = 8
    _max_failures: int = 2
    _cooldown_seconds: int = 120
    _require_healthy: bool = True
    _groups: Dict[str, ProxyGroup] = field(default_factory=dict)
    _selected_map: Dict[str, str] = field(default_factory=dict)
    _group_indices: Dict[str, int] = field(default_factory=dict)
    _inflight: Dict[str, int] = field(default_factory=dict)
    _max_concurrent_per_proxy: int = 0
    _default_group: str = "GLOBAL"

    def add(self, node: ProxyNode) -> bool:
        with self._lock:
            # 去重
            for n in self.nodes:
                if n.proxy_type == node.proxy_type and n.host == node.host and n.port == node.port:
                    return False
            self.nodes.append(node)
            return True

    def add_many(self, nodes: List[ProxyNode]) -> int:
        added = 0
        for node in nodes:
            if self.add(node):
                added += 1
        return added

    def configure_service_routing(self, groups=None, selected=None, anonymous_policy=None, account_policy=None):
        """Configure request-scoped routing groups for Gemini2API.

        FlClash exposes proxy groups to users as a client feature. Here the same
        idea is scoped down to upstream routing: select a healthy exit for this
        service, keep delay-aware choices stable, and cap per-node concurrency.
        """
        anonymous_policy = anonymous_policy or {}
        account_policy = account_policy or {}
        configured = [ProxyGroup.from_config(group) for group in (groups or []) if isinstance(group, dict)]
        if not configured:
            configured = [
                ProxyGroup(name="GLOBAL", group_type=GROUP_URL_TEST, proxies=["*"], providers=["*"]),
                ProxyGroup(name="Healthy", group_type=GROUP_FALLBACK, proxies=["*"], providers=["*"]),
            ]
        if "GLOBAL" not in {group.name for group in configured}:
            configured.insert(0, ProxyGroup(name="GLOBAL", group_type=GROUP_URL_TEST, proxies=["*"], providers=["*"]))
        self._groups = {group.name: group for group in configured if group.name}
        self._selected_map = dict(selected or {})
        for name, value in self._selected_map.items():
            if name in self._groups:
                self._groups[name].selected = value
        self._default_group = (
            anonymous_policy.get("group")
            or anonymous_policy.get("proxy_group")
            or account_policy.get("fallback_group")
            or "GLOBAL"
        )
        self._max_concurrent_per_proxy = int(
            anonymous_policy.get("max_concurrent_per_proxy")
            or account_policy.get("max_concurrent_per_proxy")
            or 0
        )

    def _node_tokens(self, node: ProxyNode) -> set:
        return {node.node_id, node.name, node.url, node.raw_link, node.host}

    def _node_matches_group(self, node: ProxyNode, group: ProxyGroup) -> bool:
        provider = node.provider or "manual"
        if group.providers and "*" not in group.providers and provider not in group.providers:
            return False
        if group.exclude_providers and provider in group.exclude_providers:
            return False
        tokens = self._node_tokens(node)
        if group.proxies and "*" not in group.proxies and not tokens.intersection(set(group.proxies)):
            return False
        label = " ".join(str(v or "") for v in (node.name, node.provider, node.host))
        if group.filter:
            try:
                if not re.search(group.filter, label, re.I):
                    return False
            except re.error:
                return False
        if group.exclude_filter:
            try:
                if re.search(group.exclude_filter, label, re.I):
                    return False
            except re.error:
                pass
        return True

    def _has_capacity(self, node: ProxyNode) -> bool:
        if not self._max_concurrent_per_proxy:
            return True
        return self._inflight.get(node.node_id, 0) < self._max_concurrent_per_proxy

    def _group_nodes(self, group: ProxyGroup, require_capacity: bool = False) -> List[ProxyNode]:
        now = time.time()
        nodes = [
            node for node in self.nodes
            if node.selectable(now, self._status_ttl, self._require_healthy)
            and self._node_matches_group(node, group)
        ]
        if require_capacity:
            nodes = [node for node in nodes if self._has_capacity(node)]
        return nodes

    def _select_strategy_node(self, nodes: List[ProxyNode], strategy: str, index_key: str = "GLOBAL") -> Optional[ProxyNode]:
        if not nodes:
            return None
        strategy = (strategy or self._strategy or "round_robin").lower()
        if strategy == "round_robin":
            idx = self._group_indices.get(index_key, 0)
            node = nodes[idx % len(nodes)]
            self._group_indices[index_key] = idx + 1
        elif strategy == "random":
            node = random.choice(nodes)
        elif strategy in {"fastest", GROUP_URL_TEST}:
            latency_nodes = [node for node in nodes if node.latency_ms > 0]
            node = min(latency_nodes or nodes, key=lambda n: (n.latency_ms if n.latency_ms > 0 else float("inf"), self._inflight.get(n.node_id, 0), n.last_used))
        elif strategy in {"least_used", GROUP_LOAD_BALANCE, "load_balance"}:
            node = min(nodes, key=lambda n: (self._inflight.get(n.node_id, 0), n.success_count, n.latency_ms if n.latency_ms > 0 else float("inf"), n.last_used))
        else:
            node = nodes[0]
        node.last_used = time.time()
        return node

    def _choose_group_node(self, group_name: str = "", strategy: str = None, require_capacity: bool = False) -> Optional[ProxyNode]:
        group = self._groups.get(group_name or self._default_group) or self._groups.get("GLOBAL")
        if not group:
            return self._select_strategy_node(self._eligible_nodes(strategy), strategy or self._strategy)
        nodes = self._group_nodes(group, require_capacity=require_capacity)
        if not nodes:
            return None
        group_type = (strategy or group.group_type or GROUP_URL_TEST).lower()
        selected = self._selected_map.get(group.name) or group.selected
        if group_type in {GROUP_SELECTOR, "selector"} and selected:
            selected_node = self._find_node_in_list(selected, nodes)
            if selected_node:
                selected_node.last_used = time.time()
                return selected_node
        if group_type == GROUP_FALLBACK:
            node = nodes[0]
            node.last_used = time.time()
            return node
        if group_type == GROUP_LOAD_BALANCE:
            return self._select_strategy_node(nodes, GROUP_LOAD_BALANCE, group.name)
        if group_type == GROUP_URL_TEST:
            latency_nodes = [node for node in nodes if node.latency_ms > 0]
            if not latency_nodes:
                return self._select_strategy_node(nodes, GROUP_LOAD_BALANCE, group.name)
            fastest = min(latency_nodes, key=lambda n: n.latency_ms)
            current = self._find_node_in_list(selected, latency_nodes) if selected else None
            if current and current.latency_ms <= fastest.latency_ms + group.tolerance_ms:
                current.last_used = time.time()
                return current
            self._selected_map[group.name] = fastest.node_id
            group.selected = fastest.node_id
            fastest.last_used = time.time()
            return fastest
        return self._select_strategy_node(nodes, group_type, group.name)

    def _find_node_in_list(self, identifier: str, nodes: List[ProxyNode]) -> Optional[ProxyNode]:
        if not identifier:
            return None
        for node in nodes:
            if identifier in self._node_tokens(node):
                return node
        return None

    def select_node(self, identifier: str = "", group: str = "", strategy: str = None, require_capacity: bool = False) -> Optional[ProxyNode]:
        """Select a node by explicit node/group identifier or by a routing group."""
        with self._lock:
            if identifier:
                if identifier in self._groups:
                    return self._choose_group_node(identifier, strategy=strategy, require_capacity=require_capacity)
                node = self._find_node_in_list(identifier, self._eligible_nodes(strategy))
                if node and (not require_capacity or self._has_capacity(node)):
                    node.last_used = time.time()
                    return node
                return None
            return self._choose_group_node(group or self._default_group, strategy=strategy, require_capacity=require_capacity)

    def lease_node(self, identifier: str = "", group: str = "", strategy: str = None) -> Optional[ProxyNode]:
        """Select and reserve capacity for one upstream request."""
        with self._lock:
            node = self.select_node(identifier=identifier, group=group, strategy=strategy, require_capacity=True)
            if not node:
                return None
            self._inflight[node.node_id] = self._inflight.get(node.node_id, 0) + 1
            return node

    def release_node(self, node_id: str):
        if not node_id:
            return
        with self._lock:
            current = self._inflight.get(node_id, 0)
            if current <= 1:
                self._inflight.pop(node_id, None)
            else:
                self._inflight[node_id] = current - 1

    def set_group_selection(self, group_name: str, proxy_name: str) -> bool:
        with self._lock:
            group = self._groups.get(group_name)
            if not group:
                return False
            group.selected = proxy_name or ""
            if proxy_name:
                self._selected_map[group_name] = proxy_name
            else:
                self._selected_map.pop(group_name, None)
            return True

    def _eligible_nodes(self, strategy: str = None) -> List[ProxyNode]:
        strategy = strategy or self._strategy
        now = time.time()
        eligible = [n for n in self.nodes if n.selectable(now, self._status_ttl, self._require_healthy)]
        if strategy == "fastest":
            eligible = [n for n in eligible if n.latency_ms > 0]
        return eligible

    def get(self, strategy: str = None) -> Optional[ProxyNode]:
        strategy = strategy or self._strategy

        with self._lock:
            healthy = self._eligible_nodes(strategy)
            if not healthy:
                return None

            if strategy == "round_robin":
                node = healthy[self._index % len(healthy)]
                self._index += 1
            elif strategy == "random":
                node = random.choice(healthy)
            elif strategy == "fastest":
                node = min(healthy, key=lambda n: n.latency_ms or float('inf'))
            elif strategy == "least_used":
                node = min(healthy, key=lambda n: n.success_count)
            else:
                node = healthy[0]

            node.last_used = time.time()
            return node

    def get_for_process(self, process_id: int) -> Optional[ProxyNode]:
        """为指定进程获取节点（确保IP隔离）"""
        with self._lock:
            healthy = self._eligible_nodes()
            if not healthy:
                return None
            return healthy[process_id % len(healthy)]

    def get_by_identifier(self, identifier: str) -> Optional[ProxyNode]:
        """Return a selectable node by id, name, raw link, or URL."""
        if not identifier:
            return None
        now = time.time()
        with self._lock:
            for node in self.nodes:
                if identifier not in {node.node_id, node.name, node.url, node.raw_link}:
                    continue
                if not node.selectable(now, self._status_ttl, self._require_healthy):
                    return None
                node.last_used = now
                return node
        return None

    def mark_success(self, node: ProxyNode, latency_ms: float = 0):
        node.is_healthy = True
        node.failure_count = 0
        node.health_status = HEALTH_HEALTHY
        node.last_failure_reason = ""
        node.cooldown_until = 0
        node.latency_ms = latency_ms
        node.last_check = time.time()
        node.health_expires_at = node.last_check + self._status_ttl if self._status_ttl else 0
        node.success_count += 1

    def mark_failure(self, node: ProxyNode, max_failures: int = None, reason: str = ""):
        max_failures = max_failures or self._max_failures
        node.failure_count += 1
        node.last_failure_reason = (reason or "probe failed")[:160]
        if node.failure_count >= max_failures:
            node.is_healthy = False
            node.health_status = HEALTH_COOLDOWN
            node.cooldown_until = time.time() + self._cooldown_seconds
            logger.warning(f"Proxy {node.name} marked cooldown after {max_failures} failures")
        else:
            node.health_status = HEALTH_UNHEALTHY

    def check_health(self, node: ProxyNode, timeout: float = 10) -> bool:
        """检查代理健康状态"""
        try:
            start = time.time()
            if node.disabled:
                node.health_status = HEALTH_DISABLED
                node.is_healthy = False
                return False
            node.health_status = HEALTH_CHECKING

            if node.proxy_type == ProxyType.SOCKS5:
                # SOCKS5 健康检查
                sock = socks5_connect(node.host, node.port, "httpbin.org", 80,
                                     node.username, node.password, timeout)
                sock.close()
            else:
                # HTTP/HTTPS 健康检查
                proxy_handler = urllib.request.ProxyHandler({
                    "http": node.url,
                    "https": node.url,
                })
                opener = urllib.request.build_opener(proxy_handler)
                req = urllib.request.Request("http://httpbin.org/ip")
                resp = opener.open(req, timeout=timeout)
                resp.read()

            latency = (time.time() - start) * 1000
            self.mark_success(node, latency)
            return True

        except Exception as e:
            logger.debug(f"Health check failed for {node.name}: {e}")
            self.mark_failure(node, reason=str(e))
            node.last_check = time.time()
            return False

    def check_all_health(self, timeout: float = None, concurrency: int = None, only_stale: bool = False) -> Dict:
        """检查所有节点健康状态"""
        timeout = timeout or self._probe_timeout
        concurrency = max(1, int(concurrency or self._probe_concurrency or 1))
        now = time.time()
        with self._lock:
            nodes = list(self.nodes)
        if only_stale:
            nodes = [
                n for n in nodes
                if not n.disabled and (not n.last_check or n.health_status == HEALTH_STALE or (self._status_ttl and now - n.last_check > self._status_ttl))
            ]
        results = {"total": len(nodes), "healthy": 0, "unhealthy": 0, "checking": 0}
        if not nodes:
            return results
        with ThreadPoolExecutor(max_workers=min(concurrency, len(nodes))) as executor:
            futures = [executor.submit(self.check_health, node, timeout) for node in nodes]
            for future in as_completed(futures):
                if future.result():
                    results["healthy"] += 1
                else:
                    results["unhealthy"] += 1
        return results

    def speed_test(self, node: ProxyNode, test_url: str = "http://httpbin.org/ip",
                   timeout: float = 30) -> float:
        """测试代理速度（返回延迟毫秒）"""
        try:
            start = time.time()

            if node.proxy_type == ProxyType.SOCKS5:
                sock = socks5_connect(node.host, node.port, "httpbin.org", 80,
                                     node.username, node.password, timeout)
                sock.sendall(b"GET /ip HTTP/1.1\r\nHost: httpbin.org\r\n\r\n")
                sock.recv(4096)
                sock.close()
            else:
                proxy_handler = urllib.request.ProxyHandler({
                    "http": node.url,
                    "https": node.url,
                })
                opener = urllib.request.build_opener(proxy_handler)
                req = urllib.request.Request(test_url)
                resp = opener.open(req, timeout=timeout)
                resp.read()

            latency = (time.time() - start) * 1000
            node.latency_ms = latency
            return latency

        except Exception as e:
            logger.debug(f"Speed test failed for {node.name}: {e}")
            return float('inf')

    def update_subscriptions(self) -> int:
        """更新订阅"""
        if not self._subscriptions:
            return 0

        total_new = 0
        for sub_url in self._subscriptions:
            try:
                nodes = fetch_subscription(sub_url)
                for node in nodes:
                    node.provider = _provider_name(sub_url)
                    node.source = "subscription"
                    node.health_status = HEALTH_CHECKING
                    node.is_healthy = False
                new_count = self.add_many(nodes)
                total_new += new_count
                logger.info(f"Subscription updated: {new_count} new nodes from {sub_url}")
            except Exception as e:
                logger.error(f"Failed to update subscription {sub_url}: {e}")

        self._last_update = time.time()
        return total_new

    def import_sources(self, subscriptions=None, direct_links=None, provider: str = "") -> Dict:
        """Import many subscription URLs and direct proxy links with de-duplication."""
        subscriptions = [s.strip() for s in (subscriptions or []) if isinstance(s, str) and s.strip()]
        direct_links = [p.strip() for p in (direct_links or []) if isinstance(p, str) and p.strip()]
        provider = provider.strip() or "manual"
        summary = {
            "subscriptions": len(subscriptions),
            "direct_links": len(direct_links),
            "parsed": 0,
            "added": 0,
            "duplicates": 0,
            "errors": [],
            "providers": {},
        }

        parsed_nodes = []
        for link in direct_links:
            try:
                node = parse_proxy_link(link)
                if not node:
                    summary["errors"].append({"source": "direct", "value": _short_value(link), "error": "unsupported proxy link"})
                    continue
                node.provider = provider
                node.source = "direct"
                node.health_status = HEALTH_CHECKING
                node.is_healthy = False
                parsed_nodes.append(node)
            except Exception as e:
                summary["errors"].append({"source": "direct", "value": _short_value(link), "error": str(e)[:160]})

        for sub_url in subscriptions:
            sub_provider = provider if provider != "manual" else _provider_name(sub_url)
            try:
                nodes = fetch_subscription(sub_url)
                if sub_url not in self._subscriptions:
                    self._subscriptions.append(sub_url)
                for node in nodes:
                    node.provider = sub_provider
                    node.source = "subscription"
                    node.health_status = HEALTH_CHECKING
                    node.is_healthy = False
                parsed_nodes.extend(nodes)
            except Exception as e:
                summary["errors"].append({"source": "subscription", "value": _short_value(sub_url), "error": str(e)[:160]})

        summary["parsed"] = len(parsed_nodes)
        for node in parsed_nodes:
            added = self.add(node)
            if added:
                summary["added"] += 1
                provider_stats = summary["providers"].setdefault(node.provider, {"added": 0})
                provider_stats["added"] += 1
            else:
                summary["duplicates"] += 1
        return summary

    def start_background_tasks(self, health_check_interval: int = 300):
        """启动后台任务（健康检查、订阅更新）"""
        if self._running:
            return

        self._running = True

        def background_worker():
            while self._running:
                try:
                    # 健康检查
                    if self.nodes:
                        logger.info(f"Running health check on {len(self.nodes)} nodes...")
                        self.check_all_health(timeout=self._probe_timeout, concurrency=self._probe_concurrency, only_stale=True)

                    # 更新订阅
                    if self._subscriptions and time.time() - self._last_update > self._update_interval:
                        self.update_subscriptions()

                except Exception as e:
                    logger.error(f"Background task error: {e}")

                time.sleep(health_check_interval)

        self._health_check_thread = threading.Thread(target=background_worker, daemon=True)
        self._health_check_thread.start()
        logger.info(f"Background tasks started (interval: {health_check_interval}s)")

    def stop_background_tasks(self):
        """停止后台任务"""
        self._running = False

    def provider_summaries(self) -> List[Dict]:
        providers = {}
        with self._lock:
            nodes = list(self.nodes)
        for node in nodes:
            item = providers.setdefault(node.provider or "manual", {
                "name": node.provider or "manual",
                "nodes": 0,
                "healthy": 0,
                "unhealthy": 0,
                "checking": 0,
                "stale": 0,
                "cooldown": 0,
            })
            item["nodes"] += 1
            status = node.health_status or (HEALTH_HEALTHY if node.is_healthy else HEALTH_UNHEALTHY)
            if status == HEALTH_HEALTHY and node.selectable(time.time(), self._status_ttl, self._require_healthy):
                item["healthy"] += 1
            elif status == HEALTH_CHECKING:
                item["checking"] += 1
            elif status == HEALTH_STALE:
                item["stale"] += 1
            elif status == HEALTH_COOLDOWN:
                item["cooldown"] += 1
            else:
                item["unhealthy"] += 1
        return sorted(providers.values(), key=lambda p: p["name"])

    def group_summaries(self) -> List[Dict]:
        now = time.time()
        with self._lock:
            groups = list(self._groups.values())
            summaries = []
            for group in groups:
                matched = [node for node in self.nodes if self._node_matches_group(node, group)]
                selectable = [
                    node for node in matched
                    if node.selectable(now, self._status_ttl, self._require_healthy)
                ]
                selected = self._selected_map.get(group.name) or group.selected
                selected_node = self._find_node_in_list(selected, selectable) if selected else None
                summaries.append({
                    **group.to_dict(),
                    "nodes": len(matched),
                    "available": len(selectable),
                    "selected": selected_node.node_id if selected_node else selected,
                    "selected_name": selected_node.name if selected_node else "",
                    "inflight": sum(self._inflight.get(node.node_id, 0) for node in selectable),
                })
        return summaries

    def node_payloads(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    **node.to_dict(),
                    "inflight": self._inflight.get(node.node_id, 0),
                    "groups": [
                        group.name for group in self._groups.values()
                        if self._node_matches_group(node, group)
                    ],
                }
                for node in self.nodes
            ]

    def health_report(self) -> Dict:
        now = time.time()
        with self._lock:
            nodes = list(self.nodes)
        statuses = {
            HEALTH_HEALTHY: 0,
            HEALTH_CHECKING: 0,
            HEALTH_STALE: 0,
            HEALTH_COOLDOWN: 0,
            HEALTH_UNHEALTHY: 0,
            HEALTH_DISABLED: 0,
        }
        last_check = 0
        for node in nodes:
            node.selectable(now, self._status_ttl, self._require_healthy)
            statuses[node.health_status] = statuses.get(node.health_status, 0) + 1
            last_check = max(last_check, node.last_check or 0)
        return {
            "total_nodes": len(nodes),
            "available_nodes": sum(1 for n in nodes if n.selectable(now, self._status_ttl, self._require_healthy)),
            "statuses": statuses,
            "last_check": last_check,
            "policy": {
                "require_healthy": self._require_healthy,
                "status_ttl_seconds": self._status_ttl,
                "probe_concurrency": self._probe_concurrency,
                "probe_timeout_seconds": self._probe_timeout,
                "max_failures": self._max_failures,
                "cooldown_seconds": self._cooldown_seconds,
                "max_concurrent_per_proxy": self._max_concurrent_per_proxy,
                "default_group": self._default_group,
            },
        }

    @property
    def healthy_count(self) -> int:
        return sum(1 for n in self.nodes if n.selectable(time.time(), self._status_ttl, self._require_healthy))

    @property
    def total_count(self) -> int:
        return len(self.nodes)

    def to_json(self) -> str:
        """导出为 JSON"""
        data = {
            "total_nodes": self.total_count,
            "healthy_nodes": self.healthy_count,
            "strategy": self._strategy,
            "nodes": [n.to_dict() for n in self.nodes],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save_to_file(self, path: str):
        """保存到文件"""
        data = {
            "nodes": [n.raw_link for n in self.nodes if n.raw_link],
            "strategy": self._strategy,
            "subscriptions": self._subscriptions,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, path: str) -> int:
        """从文件加载"""
        if not os.path.exists(path):
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            count = 0
            for link in data.get("nodes", []):
                try:
                    node = parse_proxy_link(link)
                    if node:
                        self.add(node)
                        count += 1
                except Exception:
                    pass

            if data.get("strategy"):
                self._strategy = data["strategy"]

            if data.get("subscriptions"):
                self._subscriptions = data["subscriptions"]

            return count
        except Exception as e:
            logger.error(f"Failed to load from file: {e}")
            return 0


def parse_proxy_link(link: str) -> Optional[ProxyNode]:
    """解析代理链接（纯 Python，无外部依赖）"""
    link = link.strip()

    # HTTP/HTTPS/SOCKS5 直接解析
    if link.startswith(("http://", "https://", "socks5://")):
        return _parse_standard_proxy(link)

    # vmess://
    if link.startswith("vmess://"):
        return _parse_vmess(link)

    # vless://
    if link.startswith("vless://"):
        return _parse_vless(link)

    # ss://
    if link.startswith("ss://"):
        return _parse_ss(link)

    # trojan://
    if link.startswith("trojan://"):
        return _parse_trojan(link)

    # hy2:// / hysteria2://
    if link.startswith(("hy2://", "hysteria2://")):
        return _parse_hy2(link)

    # tuic://
    if link.startswith("tuic://"):
        return _parse_tuic(link)

    return None


def _parse_standard_proxy(link: str) -> ProxyNode:
    """解析 HTTP/HTTPS/SOCKS5 代理"""
    parsed = urllib.parse.urlparse(link)

    proxy_type = ProxyType(parsed.scheme)

    return ProxyNode(
        name=parsed.hostname,
        proxy_type=proxy_type,
        host=parsed.hostname,
        port=parsed.port or (443 if parsed.scheme == "https" else (1080 if parsed.scheme == "socks5" else 80)),
        username=parsed.username or "",
        password=parsed.password or "",
        raw_link=link,
    )


def _parse_vmess(link: str) -> ProxyNode:
    """解析 vmess:// 链接"""
    b64data = link[8:]
    padding = 4 - len(b64data) % 4
    if padding != 4:
        b64data += "=" * padding

    data = json.loads(base64.b64decode(b64data))

    return ProxyNode(
        name=data.get("ps", data.get("add", "vmess")),
        proxy_type=ProxyType.HTTP,  # 需要本地转换
        host=data.get("add", ""),
        port=int(data.get("port", 443)),
        raw_link=link,
    )


def _parse_vless(link: str) -> ProxyNode:
    """解析 vless:// 链接"""
    match = re.match(r'vless://([^@]+)@([^:]+):(\d+)', link)
    if not match:
        raise ValueError("Invalid vless link")

    return ProxyNode(
        name=link.split("#")[-1] if "#" in link else match.group(2),
        proxy_type=ProxyType.HTTP,
        host=match.group(2),
        port=int(match.group(3)),
        raw_link=link,
    )


def _parse_ss(link: str) -> ProxyNode:
    """解析 ss:// 链接"""
    content = link[5:]
    name = ""
    if "#" in content:
        content, name = content.rsplit("#", 1)
        name = urllib.parse.unquote(name)

    if "@" in content:
        _, serverinfo = content.split("@", 1)
        host, port = serverinfo.split(":", 1)
    else:
        padding = 4 - len(content) % 4
        if padding != 4:
            content += "=" * padding
        decoded = base64.b64decode(content).decode()
        _, rest = decoded.split(":", 1)
        _, serverinfo = rest.rsplit("@", 1)
        host, port = serverinfo.split(":", 1)

    return ProxyNode(
        name=name or host,
        proxy_type=ProxyType.HTTP,
        host=host,
        port=int(port),
        raw_link=link,
    )


def _parse_trojan(link: str) -> ProxyNode:
    """解析 trojan:// 链接"""
    match = re.match(r'trojan://([^@]+)@([^:]+):(\d+)', link)
    if not match:
        raise ValueError("Invalid trojan link")

    return ProxyNode(
        name=link.split("#")[-1] if "#" in link else match.group(2),
        proxy_type=ProxyType.HTTP,
        host=match.group(2),
        port=int(match.group(3)),
        raw_link=link,
    )


def _parse_hy2(link: str) -> ProxyNode:
    """解析 hy2:// 链接"""
    prefix = "hy2://" if link.startswith("hy2://") else "hysteria2://"
    content = link[len(prefix):]

    match = re.match(r'([^@]+)@([^:]+):(\d+)', content)
    if not match:
        raise ValueError("Invalid hy2 link")

    return ProxyNode(
        name=link.split("#")[-1] if "#" in link else match.group(2),
        proxy_type=ProxyType.HTTP,
        host=match.group(2),
        port=int(match.group(3)),
        raw_link=link,
    )


def _parse_tuic(link: str) -> ProxyNode:
    """解析 tuic:// 链接"""
    match = re.match(r'tuic://([^@]+)@([^:]+):(\d+)', link)
    if not match:
        raise ValueError("Invalid tuic link")

    return ProxyNode(
        name=link.split("#")[-1] if "#" in link else match.group(2),
        proxy_type=ProxyType.HTTP,
        host=match.group(2),
        port=int(match.group(3)),
        raw_link=link,
    )


def parse_subscription(content: str) -> List[ProxyNode]:
    """解析订阅内容（支持多种格式）"""
    nodes = []

    # 检测是否是 Clash YAML 格式
    if content.strip().startswith("proxies:") or "Proxy:" in content:
        return _parse_clash_yaml(content)

    # 尝试 base64 解码
    try:
        padding = 4 - len(content) % 4
        if padding != 4:
            content += "=" * padding
        content = base64.b64decode(content).decode("utf-8")
    except Exception:
        pass

    # 按行解析
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            node = parse_proxy_link(line)
            if node:
                nodes.append(node)
        except Exception as e:
            logger.debug(f"Skip invalid link: {e}")

    return nodes


def _parse_clash_yaml(content: str) -> List[ProxyNode]:
    """解析 Clash YAML 格式的订阅（纯 Python，不依赖 pyyaml）"""
    nodes = []
    in_proxies = False
    current_proxy = {}

    for line in content.split("\n"):
        stripped = line.strip()

        # 检测 proxies 段开始
        if stripped == "proxies:":
            in_proxies = True
            continue

        if not in_proxies:
            continue

        # 检测新代理开始
        if stripped.startswith("- name:"):
            if current_proxy:
                node = _clash_dict_to_node(current_proxy)
                if node:
                    nodes.append(node)
            current_proxy = {"name": stripped.split(":", 1)[1].strip().strip('"\'')}
        elif stripped.startswith("- {") or stripped.startswith("-{"):
            # 单行格式
            try:
                dict_str = stripped[1:].strip()
                if dict_str.startswith("{"):
                    # JSON 格式
                    proxy_data = json.loads(dict_str)
                    node = _clash_dict_to_node(proxy_data)
                    if node:
                        nodes.append(node)
            except Exception:
                pass
        elif ":" in stripped and current_proxy:
            # 多行格式的键值对
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip().strip('"\'')
                if value:
                    current_proxy[key] = value

    # 处理最后一个代理
    if current_proxy:
        node = _clash_dict_to_node(current_proxy)
        if node:
            nodes.append(node)

    return nodes


def _clash_dict_to_node(proxy: Dict) -> Optional[ProxyNode]:
    """将 Clash 代理字典转换为 ProxyNode"""
    proxy_type = proxy.get("type", "").lower()
    name = proxy.get("name", "unknown")
    server = proxy.get("server", "")
    port = int(proxy.get("port", 0))

    if not server or not port:
        return None

    # 协议映射
    protocol_map = {
        "http": ProxyType.HTTP,
        "https": ProxyType.HTTPS,
        "socks5": ProxyType.SOCKS5,
        "socks": ProxyType.SOCKS5,
    }

    # 构建链接
    if proxy_type in ("http", "https", "socks5", "socks"):
        ptype = protocol_map.get(proxy_type, ProxyType.HTTP)
        username = proxy.get("username", "")
        password = proxy.get("password", "")

        if username:
            auth = f"{username}:{password}@"
        else:
            auth = ""

        raw_link = f"{ptype.value}://{auth}{server}:{port}"

        return ProxyNode(
            name=name,
            proxy_type=ptype,
            host=server,
            port=port,
            username=username,
            password=password,
            raw_link=raw_link,
        )

    # 对于 vmess/vless/trojan/ss 等，构建原始链接
    elif proxy_type == "vmess":
        vmess_data = {
            "v": "2",
            "ps": name,
            "add": server,
            "port": str(port),
            "id": proxy.get("uuid", ""),
            "aid": str(proxy.get("alterId", 0)),
            "scy": proxy.get("cipher", "auto"),
            "net": proxy.get("network", "tcp"),
            "type": "none",
            "host": proxy.get("servername", ""),
            "path": proxy.get("ws-opts", {}).get("path", "") if isinstance(proxy.get("ws-opts"), dict) else "",
            "tls": "tls" if proxy.get("tls") else "",
        }
        b64 = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        raw_link = f"vmess://{b64}"

        return ProxyNode(
            name=name,
            proxy_type=ProxyType.HTTP,
            host=server,
            port=port,
            raw_link=raw_link,
        )

    elif proxy_type == "vless":
        uuid = proxy.get("uuid", "")
        params = urllib.parse.urlencode({
            "encryption": proxy.get("encryption", "none"),
            "security": proxy.get("tls", "tls"),
            "type": proxy.get("network", "tcp"),
        })
        raw_link = f"vless://{uuid}@{server}:{port}?{params}#{name}"

        return ProxyNode(
            name=name,
            proxy_type=ProxyType.HTTP,
            host=server,
            port=port,
            raw_link=raw_link,
        )

    elif proxy_type in ("ss", "shadowsocks"):
        method = proxy.get("method", proxy.get("cipher", "aes-256-gcm"))
        password = proxy.get("password", "")
        userinfo = base64.b64encode(f"{method}:{password}".encode()).decode()
        raw_link = f"ss://{userinfo}@{server}:{port}#{name}"

        return ProxyNode(
            name=name,
            proxy_type=ProxyType.HTTP,
            host=server,
            port=port,
            raw_link=raw_link,
        )

    elif proxy_type == "trojan":
        password = proxy.get("password", "")
        raw_link = f"trojan://{password}@{server}:{port}#{name}"

        return ProxyNode(
            name=name,
            proxy_type=ProxyType.HTTP,
            host=server,
            port=port,
            raw_link=raw_link,
        )

    elif proxy_type in ("hysteria2", "hy2"):
        password = proxy.get("password", "")
        raw_link = f"hy2://{password}@{server}:{port}#{name}"

        return ProxyNode(
            name=name,
            proxy_type=ProxyType.HTTP,
            host=server,
            port=port,
            raw_link=raw_link,
        )

    return None


def fetch_subscription(url: str) -> List[ProxyNode]:
    """获取订阅"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "ClashForAndroid/2.5.12",
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")

    return parse_subscription(content)


def _short_value(value: str, limit: int = 96) -> str:
    value = value or ""
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _as_list(value, default=None) -> List[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        items = [item.strip() for item in re.split(r"[\n,]", value) if item.strip()]
        return items or list(default or [])
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or list(default or [])
    return list(default or [])


def _provider_name(url: str) -> str:
    """Return a stable, non-secret provider label for a subscription URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or "subscription"


# ────────────────────────────────────────────────────────────────
# SOCKS5 原生实现（零依赖，最小性能消耗）
# ────────────────────────────────────────────────────────────────

def socks5_connect(proxy_host: str, proxy_port: int, target_host: str, target_port: int,
                   username: str = "", password: str = "", timeout: float = 30) -> socket.socket:
    """通过 SOCKS5 代理建立连接（纯 Python 实现）"""

    # 连接代理服务器
    sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)

    try:
        # 握手
        if username:
            sock.sendall(b"\x05\x02\x00\x02")  # 支持无认证和用户名/密码
        else:
            sock.sendall(b"\x05\x01\x00")  # 仅无认证

        resp = sock.recv(2)
        if resp[0] != 0x05:
            raise ValueError("SOCKS5 version mismatch")

        if resp[1] == 0x02:  # 需要用户名/密码认证
            if not username:
                raise ValueError("SOCKS5 requires authentication")

            auth = b"\x01"
            auth += bytes([len(username)]) + username.encode()
            auth += bytes([len(password)]) + password.encode()
            sock.sendall(auth)

            auth_resp = sock.recv(2)
            if auth_resp[1] != 0x00:
                raise ValueError("SOCKS5 authentication failed")

        elif resp[1] != 0x00:
            raise ValueError("SOCKS5 authentication method not supported")

        # 连接请求
        req = b"\x05\x01\x00"  # VER, CMD (CONNECT), RSV

        # 尝试解析为 IP
        try:
            addr = socket.inet_aton(target_host)
            req += b"\x01" + addr  # IPv4
        except socket.error:
            # 域名
            req += b"\x03" + bytes([len(target_host)]) + target_host.encode()

        req += struct.pack("!H", target_port)
        sock.sendall(req)

        # 响应
        resp = sock.recv(4)
        if resp[0] != 0x05 or resp[1] != 0x00:
            raise ValueError(f"SOCKS5 connect failed: {resp[1]}")

        # 读取绑定地址（忽略）
        atyp = resp[3]
        if atyp == 0x01:  # IPv4
            sock.recv(4)
        elif atyp == 0x03:  # 域名
            length = sock.recv(1)[0]
            sock.recv(length)
        elif atyp == 0x04:  # IPv6
            sock.recv(16)

        sock.recv(2)  # 端口

        return sock

    except Exception:
        sock.close()
        raise


def socks5_fetch_url(proxy_host: str, proxy_port: int, url: str,
                     username: str = "", password: str = "", timeout: float = 30) -> str:
    """通过 SOCKS5 代理获取 URL 内容"""
    parsed = urllib.parse.urlparse(url)
    target_host = parsed.hostname
    target_port = parsed.port or (443 if parsed.scheme == "https" else 80)

    sock = socks5_connect(proxy_host, proxy_port, target_host, target_port,
                         username, password, timeout)

    try:
        # 发送 HTTP 请求
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        request = f"GET {path} HTTP/1.1\r\nHost: {target_host}\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())

        # 接收响应
        response = b""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            response += data

        return response.decode("utf-8", errors="replace")
    finally:
        sock.close()


# ────────────────────────────────────────────────────────────────
# 全局代理池
# ────────────────────────────────────────────────────────────────

_global_pool = ProxyPool()
_pool_lock = threading.Lock()
_cache_file = os.path.join(os.path.dirname(__file__), "..", "proxy_cache.json")


def get_pool() -> ProxyPool:
    return _global_pool


def init_pool_from_config(config: Dict) -> ProxyPool:
    """从配置初始化代理池"""
    global _global_pool

    with _pool_lock:
        _global_pool = ProxyPool()
        _global_pool._strategy = config.get("proxy_pool_strategy", "round_robin")
        _global_pool._update_interval = config.get("proxy_pool_update_interval", 3600)
        health_policy = config.get("proxy_health_policy") or {}
        _global_pool._require_healthy = bool(health_policy.get("require_healthy", True))
        _global_pool._status_ttl = int(health_policy.get("status_ttl_seconds", 600) or 0)
        _global_pool._probe_concurrency = int(health_policy.get("probe_concurrency", 8) or 1)
        _global_pool._probe_timeout = int(health_policy.get("probe_timeout_seconds", 8) or 8)
        _global_pool._max_failures = int(health_policy.get("max_failures", config.get("proxy_pool_max_failures", 2)) or 2)
        _global_pool._cooldown_seconds = int(health_policy.get("cooldown_seconds", 120) or 120)
        check_on_import = bool(health_policy.get("check_on_import", config.get("proxy_pool_health_check", True)))
        _global_pool.configure_service_routing(
            groups=config.get("proxy_groups") or [],
            selected=config.get("proxy_group_selections") or {},
            anonymous_policy=config.get("anonymous_route_policy") or {},
            account_policy=config.get("account_route_policy") or {},
        )

        import_sources = config.get("proxy_import_sources") or {}
        source_providers = import_sources.get("providers") or {}

        def unique_strings(values):
            result = []
            seen = set()
            for value in values or []:
                if not isinstance(value, str):
                    continue
                value = value.strip()
                if value and value not in seen:
                    result.append(value)
                    seen.add(value)
            return result

        # 直接添加代理链接
        proxies = unique_strings(list(config.get("proxies", []) or []) + list(import_sources.get("direct_links", []) or []))
        for p in proxies:
            if isinstance(p, str):
                try:
                    node = parse_proxy_link(p)
                    if node:
                        node.provider = source_providers.get(p) or "config"
                        node.source = "direct"
                        if check_on_import:
                            node.health_status = HEALTH_CHECKING
                            node.is_healthy = False
                        _global_pool.add(node)
                except Exception as e:
                    logger.warning(f"Failed to parse proxy: {e}")

        # 设置订阅
        subscriptions = unique_strings(list(config.get("proxy_subscriptions", []) or []) + list(import_sources.get("subscriptions", []) or []))
        _global_pool._subscriptions = subscriptions

        # 加载订阅
        for sub_url in subscriptions:
            if isinstance(sub_url, str) and sub_url.startswith("http"):
                try:
                    nodes = fetch_subscription(sub_url)
                    provider = source_providers.get(sub_url) or _provider_name(sub_url)
                    for node in nodes:
                        node.provider = provider
                        node.source = "subscription"
                        if check_on_import:
                            node.health_status = HEALTH_CHECKING
                            node.is_healthy = False
                    _global_pool.add_many(nodes)
                    logger.info(f"Loaded {len(nodes)} nodes from subscription")
                except Exception as e:
                    logger.error(f"Failed to load subscription: {e}")

        # 尝试从缓存加载
        if os.path.exists(_cache_file):
            cached = _global_pool.load_from_file(_cache_file)
            if cached:
                logger.info(f"Loaded {cached} nodes from cache")

        # 保存缓存
        _global_pool.save_to_file(_cache_file)

        # 启动后台任务
        if config.get("proxy_pool_health_check", True):
            interval = config.get("proxy_pool_health_check_interval", 300)
            _global_pool.start_background_tasks(interval)

        logger.info(f"Proxy pool initialized: {_global_pool.total_count} nodes, {_global_pool.healthy_count} healthy")

        return _global_pool


def get_proxy_for_process(process_id: int) -> Optional[ProxyNode]:
    """为进程获取代理"""
    return _global_pool.get_for_process(process_id)


def get_proxy_url(process_id: Optional[int] = None) -> Optional[str]:
    """获取代理 URL.

    When process_id is omitted, use the configured pool strategy
    (round_robin/random/fastest/least_used). Passing a process_id opts into
    deterministic process isolation.
    """
    node = _global_pool.get_for_process(process_id) if process_id is not None else _global_pool.get()
    return node.url if node else None


def get_proxy_url_by_identifier(identifier: str) -> Optional[str]:
    """Return a selectable proxy URL for a configured account binding."""
    node = _global_pool.select_node(identifier=identifier)
    return node.url if node else None


def lease_proxy_route(identifier: str = "", group: str = "", strategy: str = None) -> Optional[Dict]:
    """Lease a proxy for one Gemini2API upstream request."""
    node = _global_pool.lease_node(identifier=identifier, group=group, strategy=strategy)
    if not node:
        return None
    return {
        "id": node.node_id,
        "name": node.name,
        "url": node.url,
        "provider": node.provider,
        "group": identifier if identifier in _global_pool._groups else (group or _global_pool._default_group),
    }


def release_proxy_route(node_id: str):
    _global_pool.release_node(node_id)


def get_proxy_dict(process_id: Optional[int] = None) -> Optional[Dict]:
    """获取代理字典（用于 requests）"""
    node = _global_pool.get_for_process(process_id) if process_id is not None else _global_pool.get()
    return node.proxy_dict if node else None


def get_pool_status() -> Dict:
    """获取代理池状态"""
    health = _global_pool.health_report()
    return {
        "total_nodes": _global_pool.total_count,
        "healthy_nodes": _global_pool.healthy_count,
        "available_nodes": health["available_nodes"],
        "strategy": _global_pool._strategy,
        "health": health,
        "providers": _global_pool.provider_summaries(),
        "groups": _global_pool.group_summaries(),
        "nodes": _global_pool.node_payloads(),
    }


def import_proxy_sources(subscriptions=None, direct_links=None, provider: str = "") -> Dict:
    """Import subscriptions and direct links into the global pool."""
    return _global_pool.import_sources(subscriptions=subscriptions, direct_links=direct_links, provider=provider)


def check_pool_health(timeout: int = None, concurrency: int = None, only_stale: bool = False) -> Dict:
    return _global_pool.check_all_health(timeout=timeout, concurrency=concurrency, only_stale=only_stale)


def get_pool_health() -> Dict:
    return _global_pool.health_report()


def get_provider_summaries() -> List[Dict]:
    return _global_pool.provider_summaries()


def get_group_summaries() -> List[Dict]:
    return _global_pool.group_summaries()


def set_group_selection(group_name: str, proxy_name: str) -> bool:
    return _global_pool.set_group_selection(group_name, proxy_name)

