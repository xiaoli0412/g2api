"""Tests for the built-in proxy pool routing semantics."""

from gemini_web2api import proxy_builtin
from gemini_web2api.proxy_builtin import ProxyNode, ProxyPool, ProxyType


def _node(name, port, *, healthy=True, latency_ms=0, success_count=0):
    return ProxyNode(
        name=name,
        proxy_type=ProxyType.HTTP,
        host=f"{name}.example.test",
        port=port,
        is_healthy=healthy,
        latency_ms=latency_ms,
        success_count=success_count,
    )


def test_proxy_pool_round_robin_skips_unhealthy_nodes():
    pool = ProxyPool()
    pool.add(_node("a", 8001))
    pool.add(_node("b", 8002, healthy=False))
    pool.add(_node("c", 8003))

    assert [pool.get().name, pool.get().name, pool.get().name] == ["a", "c", "a"]


def test_global_proxy_url_uses_pool_strategy_when_process_id_is_omitted():
    old_pool = proxy_builtin._global_pool
    pool = ProxyPool()
    pool.add(_node("a", 8001))
    pool.add(_node("b", 8002))
    proxy_builtin._global_pool = pool
    try:
        assert proxy_builtin.get_proxy_url() == "http://a.example.test:8001"
        assert proxy_builtin.get_proxy_url() == "http://b.example.test:8002"
        assert proxy_builtin.get_proxy_dict() == {
            "http": "http://a.example.test:8001",
            "https": "http://a.example.test:8001",
        }
    finally:
        proxy_builtin._global_pool = old_pool


def test_global_proxy_url_with_process_id_remains_deterministic():
    old_pool = proxy_builtin._global_pool
    pool = ProxyPool()
    pool.add(_node("a", 8001))
    pool.add(_node("b", 8002))
    proxy_builtin._global_pool = pool
    try:
        assert proxy_builtin.get_proxy_url(0) == "http://a.example.test:8001"
        assert proxy_builtin.get_proxy_url(0) == "http://a.example.test:8001"
        assert proxy_builtin.get_proxy_url(1) == "http://b.example.test:8002"
        assert proxy_builtin.get_proxy_dict(1)["https"] == "http://b.example.test:8002"
    finally:
        proxy_builtin._global_pool = old_pool


def test_proxy_pool_fastest_and_least_used_strategies():
    pool = ProxyPool()
    pool.add(_node("slow", 8001, latency_ms=250, success_count=9))
    pool.add(_node("fast", 8002, latency_ms=42, success_count=7))
    pool.add(_node("fresh", 8003, latency_ms=120, success_count=0))

    assert pool.get("fastest").name == "fast"
    assert pool.get("least_used").name == "fresh"


def test_proxy_pool_does_not_resurrect_unhealthy_nodes():
    pool = ProxyPool()
    pool.add(_node("a", 8001, healthy=False))
    pool.add(_node("b", 8002, healthy=False))

    assert pool.get() is None
    assert [node.is_healthy for node in pool.nodes] == [False, False]


def test_imported_proxy_links_require_health_before_selection():
    pool = ProxyPool()
    summary = pool.import_sources(
        direct_links=[
            "http://127.0.0.1:9001",
            "http://127.0.0.1:9001",
            "socks5://127.0.0.1:9002",
        ],
        provider="vendor-a",
    )

    assert summary["parsed"] == 3
    assert summary["added"] == 2
    assert summary["duplicates"] == 1
    assert pool.get() is None
    assert {node.health_status for node in pool.nodes} == {"checking"}

    pool.mark_success(pool.nodes[0], latency_ms=25)
    selected = pool.get()
    assert selected is pool.nodes[0]
    assert selected.provider == "vendor-a"


def test_proxy_pool_update_subscriptions_sets_safe_provider(monkeypatch):
    pool = ProxyPool()
    pool._subscriptions = ["https://provider.example.test/sub?token=secret"]

    monkeypatch.setattr(proxy_builtin, "fetch_subscription", lambda url: [_node("sub-a", 8101)])

    assert pool.update_subscriptions() == 1
    node = pool.nodes[0]
    assert node.provider == "provider.example.test"
    assert node.source == "subscription"
    assert node.health_status == proxy_builtin.HEALTH_CHECKING
    assert node.is_healthy is False


def test_proxy_group_url_test_keeps_selection_within_tolerance():
    pool = ProxyPool()
    slow = _node("slow", 8001, latency_ms=140)
    fast = _node("fast", 8002, latency_ms=100)
    pool.add(slow)
    pool.add(fast)
    pool.configure_service_routing(
        groups=[{
            "name": "GLOBAL",
            "type": "url-test",
            "proxies": ["*"],
            "providers": ["*"],
            "selected": slow.node_id,
            "tolerance_ms": 50,
        }],
        selected={"GLOBAL": slow.node_id},
        anonymous_policy={"group": "GLOBAL", "max_concurrent_per_proxy": 2},
    )

    assert pool.select_node(group="GLOBAL").name == "slow"

    slow.latency_ms = 180
    assert pool.select_node(group="GLOBAL").name == "fast"


def test_proxy_group_fallback_uses_first_available_node():
    pool = ProxyPool()
    first = _node("first", 8001, healthy=False)
    second = _node("second", 8002)
    third = _node("third", 8003)
    pool.add(first)
    pool.add(second)
    pool.add(third)
    pool.configure_service_routing(groups=[{"name": "Healthy", "type": "fallback", "proxies": ["*"]}], anonymous_policy={"group": "Healthy"})

    assert pool.select_node(group="Healthy").name == "second"


def test_proxy_group_load_balance_respects_inflight_capacity():
    pool = ProxyPool()
    pool.add(_node("a", 8001, latency_ms=40))
    pool.add(_node("b", 8002, latency_ms=60))
    pool.configure_service_routing(
        groups=[{"name": "GLOBAL", "type": "load-balance", "proxies": ["*"]}],
        anonymous_policy={"group": "GLOBAL", "max_concurrent_per_proxy": 1},
    )

    first = pool.lease_node(group="GLOBAL")
    second = pool.lease_node(group="GLOBAL")
    third = pool.lease_node(group="GLOBAL")

    assert {first.name, second.name} == {"a", "b"}
    assert third is None
    assert sum(pool._inflight.values()) == 2

    pool.release_node(first.node_id)
    assert pool.lease_node(group="GLOBAL").name == first.name


def test_proxy_group_selector_can_pin_node_by_name():
    pool = ProxyPool()
    pool.add(_node("a", 8001, latency_ms=40))
    pool.add(_node("b", 8002, latency_ms=60))
    pool.configure_service_routing(
        groups=[{"name": "Pinned", "type": "select", "proxies": ["*"], "selected": "b"}],
        selected={"Pinned": "b"},
    )

    assert pool.select_node(identifier="Pinned").name == "b"
