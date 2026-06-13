param(
    [int]$ServerPort = 8129,
    [int]$CdpPort = 9223,
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repo "output\web-visual"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

function Find-Browser {
    $candidates = @(
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "No Chrome or Edge executable was found for runtime visual verification."
}

function Find-Node {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }
    throw "Node.js is required for CDP visual verification."
}

function Wait-HttpOk([string]$Url, [int]$Attempts = 40) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for $Url"
}

function Stop-TestProcesses([int]$Port, [string]$ProfileMarker) {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "msedge|chrome" -and
            ($_.CommandLine -match "remote-debugging-port=$Port" -or $_.CommandLine -match [regex]::Escape($ProfileMarker))
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

$serverStdout = Join-Path $OutputDirectory "server-$ServerPort.out.log"
$serverStderr = Join-Path $OutputDirectory "server-$ServerPort.err.log"
$server = $null
$browserProcess = $null
$profile = Join-Path $env:TEMP ("gemini2api-cdp-" + $ServerPort + "-" + [Guid]::NewGuid().ToString("N"))

try {
    $server = Start-Process -FilePath python `
        -ArgumentList @("-m", "gemini_web2api", "--port", "$ServerPort") `
        -WorkingDirectory $repo `
        -RedirectStandardOutput $serverStdout `
        -RedirectStandardError $serverStderr `
        -WindowStyle Hidden `
        -PassThru

    Wait-HttpOk "http://127.0.0.1:$ServerPort/dashboard"

    $browser = Find-Browser
    $browserProcess = Start-Process -FilePath $browser `
        -ArgumentList @(
            "--remote-debugging-port=$CdpPort",
            "--user-data-dir=$profile",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "about:blank"
        ) `
        -WindowStyle Hidden `
        -PassThru

    Wait-HttpOk "http://127.0.0.1:$CdpPort/json/version"

    $node = Find-Node
    $skillNodeModules = Join-Path $env:USERPROFILE ".agents\skills\browser\node_modules"
    if (Test-Path -LiteralPath (Join-Path $skillNodeModules "ws")) {
        $env:NODE_PATH = $skillNodeModules
    }
    $env:GEMINI2API_VISUAL_URL = "http://127.0.0.1:$ServerPort/dashboard"
    $env:GEMINI2API_VISUAL_OUT = $OutputDirectory
    $env:GEMINI2API_CDP_PORT = "$CdpPort"

    $js = @'
const http = require('http');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

const port = Number(process.env.GEMINI2API_CDP_PORT || 9223);
const urlBase = process.env.GEMINI2API_VISUAL_URL;
const outDir = process.env.GEMINI2API_VISUAL_OUT;
const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '').replace('T', '-');
const viewports = [
  { name: 'desktop-125', width: 1536, height: 864, dpr: 1.25, mobile: false },
  { name: 'compact-125', width: 900, height: 620, dpr: 1.25, mobile: false },
  { name: 'mobile', width: 390, height: 844, dpr: 1, mobile: true }
];

function getJson(pathname) {
  return new Promise((resolve, reject) => {
    http.get({ hostname: '127.0.0.1', port, path: pathname }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (error) { reject(error); }
      });
    }).on('error', reject);
  });
}

async function connect() {
  const targets = await getJson('/json');
  const target = targets.find(t => t.type === 'page');
  if (!target) throw new Error('No page target is available through CDP.');

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map();
  let id = 0;
  ws.on('message', raw => {
    const msg = JSON.parse(raw);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result || {});
    }
  });
  await new Promise((resolve, reject) => {
    ws.once('open', resolve);
    ws.once('error', reject);
  });
  return {
    send(method, params = {}) {
      const callId = ++id;
      ws.send(JSON.stringify({ id: callId, method, params }));
      return new Promise((resolve, reject) => pending.set(callId, { resolve, reject }));
    },
    close() { ws.close(); }
  };
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function evalJson(cdp, expression, label) {
  const result = await cdp.send('Runtime.evaluate', {
    expression: `JSON.stringify(${expression})`,
    returnByValue: true,
    awaitPromise: true
  });
  if (result.exceptionDetails) {
    const details = result.exceptionDetails;
    const message = details.exception?.description || details.exception?.value || details.text || 'Runtime.evaluate failed';
    throw new Error(`${label}: ${message}`);
  }
  if (!result.result || typeof result.result.value !== 'string') {
    throw new Error(`${label}: Runtime.evaluate did not return JSON.`);
  }
  return JSON.parse(result.result.value);
}
const layoutExpression = `(() => {
  const searchElements = Array.from(document.querySelectorAll('input, textarea, button, [placeholder], [aria-label], [title]')).filter(el => {
    const text = [el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('title'), el.textContent].join(' ');
    return /\\bsearch\\b|\u641c\u7d22/.test(String(text).toLowerCase());
  }).map(el => ({
    tag: el.tagName,
    id: el.id || '',
    text: String(el.textContent || el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').trim().slice(0, 60)
  }));
  const offenders = [];
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    if (el.closest('#detail') && !document.querySelector('#detail')?.classList.contains('open')) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.right > innerWidth + 1 || r.left < -1)) {
      offenders.push({
        tag: el.tagName,
        id: el.id || '',
        cls: String(el.className || '').slice(0, 80),
        text: String(el.textContent || '').trim().slice(0, 60),
        left: Math.round(r.left),
        right: Math.round(r.right),
        width: Math.round(r.width)
      });
      if (offenders.length >= 8) break;
    }
  }
  return {
    htmlLang: document.documentElement.lang,
    title: document.querySelector('#pageTitle')?.textContent || '',
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
    bodyOverflowX: getComputedStyle(document.body).overflowX,
    searchElements,
    offenders
  };
})()`;

(async () => {
  const cdp = await connect();
  const report = { url: urlBase, stamp, viewports: [] };
  try {
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    for (const vp of viewports) {
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: vp.dpr,
        mobile: vp.mobile
      });
      await cdp.send('Page.navigate', { url: `${urlBase}?visual=${encodeURIComponent(vp.name)}-${stamp}` });
      await sleep(1400);
      await cdp.send('Runtime.evaluate', {
        expression: `localStorage.setItem('lang','en'); localStorage.setItem('panel','overview'); location.reload();`,
        awaitPromise: false
      });
      await sleep(1600);
      const before = await evalJson(cdp, layoutExpression, `${vp.name} layout`);
      await cdp.send('Runtime.evaluate', {
        expression: `document.querySelector('#langZh').click()`,
        awaitPromise: false
      });
      await sleep(350);
      const afterLang = await evalJson(cdp, `(() => ({
          htmlLang: document.documentElement.lang,
          title: document.querySelector('#pageTitle')?.textContent || '',
          zhActive: document.querySelector('#langZh')?.classList.contains('active') || false,
          enActive: document.querySelector('#langEn')?.classList.contains('active') || false
        }))()`, `${vp.name} language`);
      const shotResult = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
      const shot = path.join(outDir, `dashboard-cdp-${vp.name}-${stamp}.png`);
      fs.writeFileSync(shot, Buffer.from(shotResult.data, 'base64'));
      const record = { ...vp, before, afterLang, screenshot: shot };
      if (vp.name === 'desktop-125') {
        const tokenChartMetrics = await evalJson(cdp, `(() => {
          const request = {
            id: 'req_visual_detail',
            time_str: '2026-06-09 17:30:00',
            endpoint: '/v1/chat/completions',
            method: 'POST',
            protocol: 'openai.chat',
            model: 'gemini-3.5-flash',
            prompt_tokens: 1280,
            completion_tokens: 420,
            total_tokens: 1700,
            status: 'ok',
            duration_ms: 21.4,
            proxy: 'http://user:password@example.proxy:8080',
            stream: false,
            request_body: { model: 'gemini-3.5-flash', messages: [{ role: 'user', content: 'visual request body' }] },
            response_body: { choices: [{ message: { content: 'visual response body' } }], usage: { prompt_tokens: 1280, completion_tokens: 420, total_tokens: 1700 } },
            trace: { route: 'dashboard-visual', upstream: 'mock' }
          };
          state.data = {
            uptime: '0h 1m 1s',
            summary: {
              total_requests: 42,
              total_prompt_tokens: 32000,
              total_completion_tokens: 8000,
              total_tokens: 40000,
              total_errors: 0,
              success_rate: 100,
              avg_latency_ms: 21,
              requests_per_minute: 7,
              last_request_at: '2026-06-09 17:30:00'
            },
            recent_requests: [request],
            recent_logs: [],
            hourly_stats: [
              { hour: '11:00', requests: 7, tokens: 1700 },
              { hour: '12:00', requests: 12, tokens: 3400 },
              { hour: '13:00', requests: 10, tokens: 2800 },
              { hour: '14:00', requests: 16, tokens: 5200 },
              { hour: '15:00', requests: 11, tokens: 4100 },
              { hour: '16:00', requests: 18, tokens: 6800 },
              { hour: '17:00', requests: 14, tokens: 5600 }
            ],
            daily_stats: [
              { day: '2026-06-05', requests: 26, tokens: 18000 },
              { day: '2026-06-06', requests: 34, tokens: 24000 },
              { day: '2026-06-07', requests: 31, tokens: 22000 },
              { day: '2026-06-08', requests: 38, tokens: 31000 },
              { day: '2026-06-09', requests: 42, tokens: 40000 }
            ],
            model_stats: { 'gemini-3.5-flash': { requests: 42, prompt_tokens: 32000, completion_tokens: 8000, total_tokens: 40000, errors: 0 } }
          };
          state.renderHashes = Object.create(null);
          renderPanels();
          setPanel('tokens');
          const chart = document.querySelector('#hourlyChart2');
          const r = chart.getBoundingClientRect();
          return {
            panel: state.panel,
            quotaTabs: document.querySelectorAll('.quota-tabs').length,
            quotaBodies: document.querySelectorAll('.quota-body').length,
            quotaCards: document.querySelectorAll('.quota-mini').length,
            quotaTables: document.querySelectorAll('.quota-table-card .quota-table').length,
            quotaRows: document.querySelectorAll('.quota-table tbody tr').length,
            quotaShares: document.querySelectorAll('.quota-share .quota-bar').length,
            quotaBars: document.querySelectorAll('.quota-bar').length,
            quotaLeaders: document.querySelectorAll('.quota-leader').length,
            oldLines: document.querySelectorAll('.quota-svg, .quota-line, .quota-area, .quota-point').length,
            oldPlots: document.querySelectorAll('.quota-plot, .quota-y-axis, .quota-x-axis').length,
            tableCards: document.querySelectorAll('.cell-main, .token-stack, .model-cell').length,
            stockElements: document.querySelectorAll('[class*="stock-"], .stock-candle, .stock-line').length,
            chartText: chart?.textContent || '',
            overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
            width: Math.round(r.width),
            height: Math.round(r.height)
          };
        })()`, `${vp.name} token chart`);
        if (tokenChartMetrics.panel !== 'tokens' || tokenChartMetrics.quotaTabs < 2 || tokenChartMetrics.quotaBodies < 2 || tokenChartMetrics.quotaCards < 8 || tokenChartMetrics.quotaTables < 2 || tokenChartMetrics.quotaRows < 12 || tokenChartMetrics.quotaShares < 12 || tokenChartMetrics.quotaLeaders < 6 || tokenChartMetrics.tableCards < 2) {
          throw new Error(`${vp.name}: New API style quota/table view did not render: ${JSON.stringify(tokenChartMetrics)}`);
        }
        if (tokenChartMetrics.stockElements || tokenChartMetrics.oldLines || tokenChartMetrics.oldPlots || tokenChartMetrics.overflow > 1) {
          throw new Error(`${vp.name}: token chart visual guard failed: ${JSON.stringify(tokenChartMetrics)}`);
        }
        const tokenShotResult = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
        const tokenShot = path.join(outDir, `dashboard-cdp-token-newapi-${vp.name}-${stamp}.png`);
        fs.writeFileSync(tokenShot, Buffer.from(tokenShotResult.data, 'base64'));
        record.tokenChart = tokenChartMetrics;
        record.tokenChartScreenshot = tokenShot;

        const detailMetrics = await evalJson(cdp, `(() => {
          const request = {
            id: 'req_visual_detail',
            time_str: '2026-06-09 17:30:00',
            endpoint: '/v1/chat/completions',
            method: 'POST',
            protocol: 'openai.chat',
            model: 'gemini-3.5-flash',
            prompt_tokens: 1280,
            completion_tokens: 420,
            total_tokens: 1700,
            status: 'ok',
            duration_ms: 21.4,
            proxy: 'http://user:password@example.proxy:8080',
            stream: false,
            request_body: { model: 'gemini-3.5-flash', messages: [{ role: 'user', content: 'visual request body' }] },
            response_body: { choices: [{ message: { content: 'visual response body' } }], usage: { prompt_tokens: 1280, completion_tokens: 420, total_tokens: 1700 } },
            trace: { route: 'dashboard-visual', upstream: 'mock' }
          };
          state.data = state.data || {};
          state.data.summary = {
            total_requests: 42,
            total_tokens: 40000,
            success_rate: 100,
            requests_per_minute: 7
          };
          state.data.recent_requests = [request];
          setPanel('requests');
          document.querySelector('#detail').style.transition = 'none';
          renderDetailView(request);
          const detail = document.querySelector('#detail');
          const tickerText = document.querySelector('#detailMetrics')?.textContent || '';
          const opsTickerText = document.querySelector('#detailOpsTicker')?.textContent || '';
          const r = detail.getBoundingClientRect();
          const offenders = [];
          for (const el of Array.from(detail.querySelectorAll('*'))) {
            const box = el.getBoundingClientRect();
            if (box.width > 0 && box.height > 0 && (box.right > innerWidth + 1 || box.left < -1)) {
              offenders.push({ tag: el.tagName, id: el.id || '', cls: String(el.className || '').slice(0, 60), right: Math.round(box.right), width: Math.round(box.width) });
              if (offenders.length >= 6) break;
            }
          }
          return {
            open: detail.classList.contains('open'),
            detailWidth: Math.round(r.width),
            title: document.querySelector('#detailTitle')?.textContent || '',
            ticker: tickerText,
            opsTicker: opsTickerText,
            requestBody: document.querySelector('#requestBody')?.textContent || '',
            responseBody: document.querySelector('#responseBody')?.textContent || '',
            proxyMasked: opsTickerText.includes('://***@') && !opsTickerText.includes('password'),
            offenders
          };
        })()`, `${vp.name} detail`);
        if (!detailMetrics.open || !detailMetrics.opsTicker.includes('42') || !detailMetrics.opsTicker.includes('40.0K')) {
          throw new Error(`${vp.name}: request detail metrics did not render: ${JSON.stringify(detailMetrics)}`);
        }
        if (!detailMetrics.ticker.includes('1.7K') || !detailMetrics.requestBody.includes('visual request body') || !detailMetrics.responseBody.includes('visual response body')) {
          throw new Error(`${vp.name}: request detail bodies were not visible: ${JSON.stringify(detailMetrics)}`);
        }
        if (!detailMetrics.proxyMasked || detailMetrics.offenders.length) {
          throw new Error(`${vp.name}: request detail visual guard failed: ${JSON.stringify(detailMetrics)}`);
        }
        const detailShotResult = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
        const detailShot = path.join(outDir, `dashboard-cdp-detail-${vp.name}-${stamp}.png`);
        fs.writeFileSync(detailShot, Buffer.from(detailShotResult.data, 'base64'));
        record.detail = detailMetrics;
        record.detailScreenshot = detailShot;

        const cookieMetrics = await evalJson(cdp, `(() => {
          document.querySelector('#detail')?.classList.remove('open');
          state.cookie = JSON.parse('{"cookie_valid":true,"cookie_length":88,"has_sapisid":true,"status":"ok_full_web","last_push_str":"2026-06-09 17:31:00","next_refresh_str":"N/A","diagnostics":{"web_ui_likely_complete":true,"api_streamgenerate_ready":true},"sources":{"manual_import":{"status":"ok_api","source":"network-file","last_sync_str":"2026-06-09 17:28:00","cookie_length":42,"diagnostics":{"api_streamgenerate_ready":true,"web_ui_likely_complete":false}},"edge_extension":{"status":"ok_full_web","source":"edge-extension","last_sync_str":"2026-06-09 17:29:00","cookie_length":88,"diagnostics":{"api_streamgenerate_ready":true,"web_ui_likely_complete":true}},"internal_browser":{"status":"ok_full_web","source":"internal-browser","last_sync_str":"2026-06-09 17:30:00","cookie_length":90,"diagnostics":{"api_streamgenerate_ready":true,"web_ui_likely_complete":true}}},"internal_browser":{"status":"saved","available":true,"running":false,"cookie_length":90,"profile_dir":"browser-profile"}}');
          state.renderHashes = Object.create(null);
          setPanel('cookies');
          renderCookies();
          const text = document.querySelector('#panel-cookies')?.textContent || '';
          const offenders = [];
          for (const el of Array.from(document.querySelector('#panel-cookies').querySelectorAll('*'))) {
            const box = el.getBoundingClientRect();
            if (box.width > 0 && box.height > 0 && (box.right > innerWidth + 1 || box.left < -1)) {
              offenders.push({ tag: el.tagName, id: el.id || '', cls: String(el.className || '').slice(0, 60), right: Math.round(box.right), width: Math.round(box.width) });
              if (offenders.length >= 6) break;
            }
          }
          return {
            panel: state.panel,
            text,
            hasManual: text.includes(t('manualSource')) && text.includes(displayState('ok_api')),
            hasEdge: text.includes(t('edgeExtension')) && text.includes(displayState('ok_full_web')),
            hasInternal: text.includes(t('internalBrowser')) && text.includes(displayState('ok_full_web')),
            overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
            offenders
          };
        })()`, `${vp.name} cookie sources`);
        if (cookieMetrics.panel !== 'cookies' || !cookieMetrics.hasManual || !cookieMetrics.hasEdge || !cookieMetrics.hasInternal || cookieMetrics.overflow > 1 || cookieMetrics.offenders.length) {
          throw new Error(`${vp.name}: cookie source status visual guard failed: ${JSON.stringify(cookieMetrics)}`);
        }
        const cookieShotResult = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
        const cookieShot = path.join(outDir, `dashboard-cdp-cookie-sources-${vp.name}-${stamp}.png`);
        fs.writeFileSync(cookieShot, Buffer.from(cookieShotResult.data, 'base64'));
        record.cookieSources = cookieMetrics;
        record.cookieSourcesScreenshot = cookieShot;

        const proxyRouteMetrics = await evalJson(cdp, `(() => {
          state.proxy = {
            proxy_enabled: true,
            enabled: true,
            configured_proxy: 'http://user:password@fallback.proxy:8080',
            strategy: 'least_used',
            configured_nodes: 3,
            subscriptions: 1,
            runtime: {
              available_nodes: 2,
              total_nodes: 3,
              healthy_nodes: 2,
              providers: ['manual'],
              health: { available_nodes: 2, total_nodes: 3, statuses: { checking: 0, cooldown: 1 } },
              nodes: [
                { provider: 'manual', name: 'edge-a', health_status: 'healthy', latency_ms: 21, failure_count: 0 },
                { provider: 'manual', name: 'edge-b', health_status: 'cooldown', latency_ms: 90, failure_count: 2 }
              ],
              groups: [
                { name: 'Healthy', type: 'latency', available: 2, nodes: 3, selected_name: 'edge-a', inflight: 1 }
              ]
            }
          };
          state.config = {
            proxy_enabled: true,
            proxy_pool_strategy: 'least_used',
            account_route_policy: 'bound_proxy_then_fallback',
            accounts: [
              { id: 'u/1', label: 'Work', primary_proxy: 'http://***@account.proxy:9001', fallback_group: 'Healthy', enabled: true },
              { id: 'u/2', label: 'Personal', fallback_group: 'Healthy', enabled: false }
            ],
            proxy_account_bindings: [
              { account_id: 'u/1', primary_proxy: 'http://***@account.proxy:9001', fallback_group: 'Healthy' }
            ]
          };
          state.renderHashes = Object.create(null);
          setPanel('proxy');
          renderProxy();
          fillConfig();
          const text = document.querySelector('#panel-proxy')?.textContent || '';
          const editValue = document.querySelector('#cfgAccountBindings')?.value || '';
          const offenders = [];
          for (const el of Array.from(document.querySelector('#panel-proxy').querySelectorAll('*'))) {
            const box = el.getBoundingClientRect();
            if (box.width > 0 && box.height > 0 && (box.right > innerWidth + 1 || box.left < -1)) {
              offenders.push({ tag: el.tagName, id: el.id || '', cls: String(el.className || '').slice(0, 60), right: Math.round(box.right), width: Math.round(box.width) });
              if (offenders.length >= 6) break;
            }
          }
          return {
            panel: state.panel,
            routeCards: document.querySelectorAll('#accountRouteSummary .route-card').length,
            bindingRows: document.querySelectorAll('#accountBindingsTable tr').length,
            text,
            editValue,
            hasMaskedProxy: text.includes('http://***@account.proxy:9001'),
            leaksPassword: text.includes('password') || editValue.includes('password'),
            maskedValueEditable: editValue.includes('***'),
            overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
            offenders
          };
        })()`, `${vp.name} proxy routes`);
        if (proxyRouteMetrics.panel !== 'proxy' || proxyRouteMetrics.routeCards < 4 || proxyRouteMetrics.bindingRows < 2 || !proxyRouteMetrics.hasMaskedProxy || proxyRouteMetrics.leaksPassword || proxyRouteMetrics.maskedValueEditable || proxyRouteMetrics.overflow > 1 || proxyRouteMetrics.offenders.length) {
          throw new Error(`${vp.name}: proxy account route visual guard failed: ${JSON.stringify(proxyRouteMetrics)}`);
        }
        const proxyShotResult = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true });
        const proxyShot = path.join(outDir, `dashboard-cdp-proxy-routes-${vp.name}-${stamp}.png`);
        fs.writeFileSync(proxyShot, Buffer.from(proxyShotResult.data, 'base64'));
        record.proxyRoutes = proxyRouteMetrics;
        record.proxyRoutesScreenshot = proxyShot;
      }
      report.viewports.push(record);
      if (before.searchElements.length) {
        throw new Error(`${vp.name}: search UI remained: ${JSON.stringify(before.searchElements)}`);
      }
      if (before.scrollWidth > before.clientWidth + 1 || before.bodyScrollWidth > before.clientWidth + 1) {
        throw new Error(`${vp.name}: horizontal overflow ${before.scrollWidth}/${before.bodyScrollWidth} > ${before.clientWidth}`);
      }
      if (before.offenders.length) {
        throw new Error(`${vp.name}: visible element overflow ${JSON.stringify(before.offenders)}`);
      }
      if (!afterLang.zhActive || afterLang.htmlLang !== 'zh-CN') {
        throw new Error(`${vp.name}: language switch failed: ${JSON.stringify(afterLang)}`);
      }
    }
  } finally {
    cdp.close();
  }
  const reportPath = path.join(outDir, `dashboard-cdp-visual-report-${stamp}.json`);
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`[OK] CDP dashboard visual report: ${reportPath}`);
  for (const item of report.viewports) {
    console.log(`[OK] ${item.name}: ${item.screenshot}`);
  }
})().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
'@

    $js | & $node -
    if ($LASTEXITCODE -ne 0) {
        throw "Web dashboard runtime visual verification failed with exit code $LASTEXITCODE"
    }
} finally {
    Stop-TestProcesses $CdpPort $profile
    if ($browserProcess -and -not $browserProcess.HasExited) {
        Stop-Process -Id $browserProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
}
