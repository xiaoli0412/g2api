const statusEl = document.getElementById("status");
const lastTimeEl = document.getElementById("lastTime");
const cookieCountEl = document.getElementById("cookieCount");
const serverUrlEl = document.getElementById("serverUrl");
const pushBtn = document.getElementById("pushBtn");
const refreshBtn = document.getElementById("refreshBtn");

const REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"];

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
    chrome.cookies.getAll({ domain: "gemini.google.com" }, (cookies) => {
      const cookieMap = {};
      for (const c of cookies) {
        cookieMap[c.name] = c.value;
      }
      resolve(cookieMap);
    });
  });
}

async function refresh() {
  // Get server status
  chrome.runtime.sendMessage({ action: "getStatus" }, async (data) => {
    if (data) {
      const info = STATUS_MAP[data.lastStatus] || STATUS_MAP.unknown;
      statusEl.textContent = info.text;
      statusEl.className = "value " + info.cls;
      lastTimeEl.textContent = formatTime(data.lastTime);
      serverUrlEl.value = data.serverUrl || "http://127.0.0.1:8081";
    }
  });

  // Check cookies
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
  pushBtn.innerHTML = '<span class="spinner"></span> Pushing...';
  pushBtn.disabled = true;
  
  chrome.runtime.sendMessage({ action: "pushNow" }, async (result) => {
    pushBtn.textContent = "Push Cookies Now";
    pushBtn.disabled = false;
    await refresh();
  });
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.textContent = "Checking...";
  refreshBtn.disabled = true;
  
  await refresh();
  
  refreshBtn.textContent = "Check Cookies";
  refreshBtn.disabled = false;
});

serverUrlEl.addEventListener("change", () => {
  chrome.storage.local.set({ serverUrl: serverUrlEl.value });
});

// Initial load
refresh();

// Auto-refresh every 10 seconds
setInterval(refresh, 10000);
