"""Static guards for the Web operations console UI."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "gemini_web2api" / "dashboard.html"
WEB_VISUAL_SCRIPT = ROOT / "native" / "scripts" / "verify-web-dashboard-runtime.ps1"
VERIFY_ALL_NATIVE = ROOT / "native" / "scripts" / "verify-all-native.ps1"


def _html() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_dashboard_has_no_search_ui():
    html = _html()
    assert not re.search(r"search(box|input|field|icon)|autosuggest|queryicon|placeholder=[^>]*search|>\s*search\s*<|搜索", html, re.IGNORECASE)


def test_dashboard_polling_is_bounded_and_incremental():
    html = _html()
    assert "AbortController" in html
    assert "FETCH_TIMEOUT_MS" in html
    assert "requestAnimationFrame" in html
    assert "scheduleRender()" in html
    assert "function renderCurrentPanel" in html
    assert "if(state.loading&&!force) return" in html


def test_dashboard_keeps_request_bodies_cookie_paths_and_proxy_groups_visible():
    html = _html()
    for token in (
        "/api/request/",
        "request_body",
        "response_body",
        "detailMetrics",
        "detail-chip",
        "detailOpsTicker",
        "detail-head-main",
        "operationTotals",
        "prompt_tokens",
        "completion_tokens",
        "maskProxy",
        "cookieFile",
        "/api/cookie/import",
        "/api/cookie/push",
        "/api/cookie/browser-login",
        "sources.manual_import",
        "sources.edge_extension",
        "sources.internal_browser",
        "manualSource",
        "proxyGroups",
        "accountRouteSummary",
        "accountBindingsTable",
        "cfgAccountBindings",
        "renderAccountRoutes",
        "proxyEditable",
        "account_route_policy",
        "visualFile",
        "traceBody",
        "cfgStreamMode",
        "cfgFakeDelay",
        "cfgStreamChunk",
        "cfgUploadRetry",
        "cfgProxyEnabled",
        "cfgLogRequests",
        "cfgCaptureReq",
        "cfgCaptureResp",
        "cfgUpstreamRaw",
        "cfgDashboardBypass",
        "cfgGeminiBl",
        "cfgAuthUser",
    ):
        assert token in html


def test_dashboard_language_keys_and_responsive_layout_are_guarded():
    html = _html()
    assert 'refresh:"Refresh"' in html
    assert 'refresh:"刷新"' in html
    assert "min-width:980px" not in html
    assert "min-width:760px" not in html
    assert re.search(r"body\{\s*min-width:0", html)
    assert "grid-template-columns:minmax(0,1fr) auto" in html
    assert "@media(max-width:720px)" in html


def test_dashboard_keeps_glass_without_full_viewport_backdrop_cost():
    html = _html()
    app_rule = re.search(r"\.app\{([^}]*)\}", html)
    assert app_rule
    assert "backdrop-filter" not in app_rule.group(1)
    assert "@supports ((backdrop-filter:blur(1px))" in html
    assert ".side,.top,.box,.detail,.toast" in html
    assert "scrollbar-color:#4a5660 transparent" in html
    assert "::-webkit-scrollbar-thumb" in html


def test_dashboard_token_chart_uses_new_api_style_quota_chart_not_stock_candles():
    html = _html()
    assert ".quota-head" in html
    assert ".quota-tabs" in html
    assert ".quota-cards" in html
    assert ".quota-mini.primary" in html
    assert ".quota-mini.delta" in html
    assert ".quota-body" in html
    assert ".quota-table-card" in html
    assert ".quota-share" in html
    assert ".quota-bars" in html
    assert ".quota-bar" in html
    assert ".quota-leaders" in html
    assert "<table class=\"quota-table\"" in html
    assert "usageTrend" in html
    assert "requestVolume" in html
    assert "rangeTotal" in html
    assert "topBuckets" in html
    assert "quota-svg" not in html
    assert "quota-area" not in html
    assert "quota-line" not in html
    assert "quota-point" not in html
    assert "stock-" not in html
    assert "stock-candle" not in html
    assert "quota-plot" not in html
    assert "quota-y-axis" not in html
    assert "quota-x-axis" not in html
    assert "maFast" not in html
    assert "maSlow" not in html
    assert ".bar{" not in html
    assert "trend-" not in html


def test_dashboard_runtime_visual_verifier_covers_real_viewports_and_language():
    script = WEB_VISUAL_SCRIPT.read_text(encoding="utf-8")
    verify_all = VERIFY_ALL_NATIVE.read_text(encoding="utf-8")

    for token in (
        "remote-debugging-port",
        "deviceScaleFactor: vp.dpr",
        "desktop-125",
        "compact-125",
        "mobile",
        "searchElements.length",
        "horizontal overflow",
        "htmlLang !== 'zh-CN'",
        "Page.captureScreenshot",
        "dashboard-cdp-detail",
        "opsTicker",
        "visual request body",
        "proxyMasked",
        "dashboard-cdp-cookie-sources",
        "cookieSources",
        "network-file",
    ):
        assert token in script

    assert "[switch]$RunWebVisual" in verify_all
    assert "verify-web-dashboard-runtime.ps1" in verify_all
