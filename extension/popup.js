const statusEl = document.getElementById("status");
const lastTimeEl = document.getElementById("lastTime");
const cookieCountEl = document.getElementById("cookieCount");
const serverUrlEl = document.getElementById("serverUrl");
const apiKeyEl = document.getElementById("apiKey");
const pushIntervalEl = document.getElementById("pushInterval");
const pushCountEl = document.getElementById("pushCount");
const serverDiagEl = document.getElementById("serverDiag");
const pushBtn = document.getElementById("pushBtn");
const refreshBtn = document.getElementById("refreshBtn");
const loginGuideBtn = document.getElementById("loginGuideBtn");
const loginGuide = document.getElementById("loginGuide");

const REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID", "__Secure-3PSID"];

const STATUS_MAP = {
  ok: { text: "Connected", cls: "status-ok" },
  no_cookies: { text: "No Cookies", cls: "status-warn" },
  server_error: { text: "Server Error", cls: "status-err" },
  disconnected: { text: "Disconnected", cls: "status-off" },
  unknown: { text: "Unknown", cls: "status-off" }
};

function formatTime(ts) {
  if (!ts) return "--";
  const d = new Date(ts);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return d.toLocaleTimeString();
}

async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get("serverUrl", (data) => {
      resolve(data.serverUrl || "http://127.0.0.1:8081");
    });
  });
}

async function checkCookies() {
  return new Promise((resolve) => {
    // Query cookies from ALL Google domains - auth cookies live on .google.com
    const domains = [".google.com", "google.com", "gemini.google.com"];
    const cookieMap = {};
    let pending = domains.length;
    for (const domain of domains) {
      chrome.cookies.getAll({ domain }, (cookies) => {
        for (const c of (cookies || [])) {
          if (c.value) cookieMap[c.name] = c.value;
        }
        pending--;
        if (pending === 0) resolve(cookieMap);
      });
    }
  });
}

function setLoading(el, loading) {
  if (!el) return;
  if (loading) {
    el.dataset.origText = el.textContent;
    el.innerHTML = '<span class="spinner"></span> Loading...';
    el.disabled = true;
  } else {
    el.textContent = el.dataset.origText || el.textContent;
    el.disabled = false;
  }
}

async function refresh() {
    chrome.runtime.sendMessage({ action: "getStatus" }, async (data) => {
    if (data) {
      const info = STATUS_MAP[data.lastStatus] || STATUS_MAP.unknown;
      statusEl.textContent = info.text;
      statusEl.className = "value " + info.cls;
      lastTimeEl.textContent = formatTime(data.lastTime);
      if (serverUrlEl) serverUrlEl.value = data.serverUrl || "http://127.0.0.1:8081";
      if (apiKeyEl) apiKeyEl.value = data.apiKey || "";
      if (pushCountEl) pushCountEl.textContent = data.pushCount || 0;
      if (serverDiagEl) {
        const diag = data.lastDiagnostics || {};
        if (diag.web_ui_likely_complete) {
          serverDiagEl.textContent = "Web UI ready";
          serverDiagEl.className = "value status-ok";
        } else if (diag.api_streamgenerate_ready) {
          serverDiagEl.textContent = "API ready";
          serverDiagEl.className = "value status-warn";
        } else if (data.lastServerError) {
          serverDiagEl.textContent = "Server error";
          serverDiagEl.className = "value status-err";
        } else {
          serverDiagEl.textContent = "--";
          serverDiagEl.className = "value status-off";
        }
      }
    }
  });

  chrome.storage.local.get("pushInterval", (data) => {
    if (pushIntervalEl && data.pushInterval) pushIntervalEl.value = data.pushInterval;
  });

  const cookies = await checkCookies();
  let found = 0;
  
  for (const name of REQUIRED_COOKIES) {
    const el = document.getElementById(`cookie-${name}`);
    if (el) {
      if (cookies[name]) {
        el.textContent = "Found";
        el.className = "cookie-status";
        found++;
      } else {
        el.textContent = "Missing";
        el.className = "cookie-missing";
      }
    }
  }
  
  cookieCountEl.textContent = `${found}/${REQUIRED_COOKIES.length}`;
  cookieCountEl.className = found >= 3 ? "value status-ok" : "value status-warn";
}

pushBtn.addEventListener("click", async () => {
  setLoading(pushBtn, true);
  try {
    const result = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "pushNow" }, resolve);
    });
    if (result && result.success) {
      pushBtn.textContent = "Pushed!";
      setTimeout(() => { pushBtn.textContent = "Push Cookies Now"; }, 2000);
    }
  } catch (e) {
    console.error("Push failed:", e);
  }
  setLoading(pushBtn, false);
  await refresh();
});

refreshBtn.addEventListener("click", async () => {
  setLoading(refreshBtn, true);
  await refresh();
  setLoading(refreshBtn, false);
  refreshBtn.textContent = "Check Cookies";
});

if (loginGuideBtn && loginGuide) {
  loginGuideBtn.addEventListener("click", () => {
    const visible = loginGuide.style.display !== "none";
    loginGuide.style.display = visible ? "none" : "block";
    loginGuideBtn.textContent = visible ? "How to Login" : "Hide Guide";
  });
}

if (serverUrlEl) {
  serverUrlEl.addEventListener("change", () => {
    chrome.storage.local.set({ serverUrl: serverUrlEl.value });
  });
}

if (apiKeyEl) {
  apiKeyEl.addEventListener("change", () => {
    chrome.runtime.sendMessage({ action: "setApiKey", key: apiKeyEl.value });
  });
}

if (pushIntervalEl) {
  pushIntervalEl.addEventListener("change", () => {
    const interval = parseInt(pushIntervalEl.value) || 10;
    chrome.runtime.sendMessage({ action: "setInterval", interval });
  });
}

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "r") {
    e.preventDefault();
    refresh();
  }
  if (e.key === "p" && !e.ctrlKey && !e.metaKey && e.target.tagName !== "INPUT") {
    pushBtn.click();
  }
});

refresh();
setInterval(refresh, 10000);
