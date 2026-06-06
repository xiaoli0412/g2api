const statusEl = document.getElementById("status");
const lastTimeEl = document.getElementById("lastTime");
const serverUrlEl = document.getElementById("serverUrl");
const pushBtn = document.getElementById("pushBtn");

const STATUS_MAP = {
  ok: { text: "Connected", cls: "ok" },
  no_cookies: { text: "No Cookies", cls: "warn" },
  server_error: { text: "Server Error", cls: "err" },
  disconnected: { text: "Disconnected", cls: "off" },
  unknown: { text: "Unknown", cls: "off" }
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

async function refresh() {
  chrome.runtime.sendMessage({ action: "getStatus" }, (data) => {
    if (!data) return;
    const info = STATUS_MAP[data.lastStatus] || STATUS_MAP.unknown;
    statusEl.textContent = info.text;
    statusEl.className = "value " + info.cls;
    lastTimeEl.textContent = formatTime(data.lastTime);
    serverUrlEl.value = data.serverUrl || "http://127.0.0.1:8081";
  });
}

pushBtn.addEventListener("click", () => {
  pushBtn.textContent = "Pushing...";
  pushBtn.disabled = true;
  chrome.runtime.sendMessage({ action: "pushNow" }, (result) => {
    pushBtn.textContent = "Push Now";
    pushBtn.disabled = false;
    refresh();
  });
});

serverUrlEl.addEventListener("change", () => {
  chrome.runtime.sendMessage({ action: "setServerUrl", url: serverUrlEl.value });
});

refresh();
setInterval(refresh, 5000);
