const DEFAULT_SERVER = "http://127.0.0.1:8081";
const ALARM_NAME = "push-cookies";
const DEFAULT_INTERVAL = 10;
const REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID", "__Secure-3PSID"];
const COOKIE_DOMAINS = [".google.com", "google.com", "gemini.google.com"];

async function getServerUrl() {
  const data = await chrome.storage.local.get("serverUrl");
  return data.serverUrl || DEFAULT_SERVER;
}

async function getApiKey() {
  const data = await chrome.storage.local.get("apiKey");
  return data.apiKey || "";
}

async function getInterval() {
  const data = await chrome.storage.local.get("pushInterval");
  return data.pushInterval || DEFAULT_INTERVAL;
}

function getCookiesForDomain(domain) {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain }, (cookies) => resolve(cookies || []));
  });
}

async function extractCookies() {
  const allCookies = [];
  for (const domain of COOKIE_DOMAINS) {
    allCookies.push(...await getCookiesForDomain(domain));
  }

  if (!allCookies.length) {
    return null;
  }

  const cookieMap = {};
  for (const c of allCookies) {
    const domain = (c.domain || "").toLowerCase();
    if (!(domain === "google.com" || domain.endsWith(".google.com") || domain === "gemini.google.com")) {
      continue;
    }
    if (!c.value) {
      continue;
    }
    cookieMap[c.name] = c.value;
  }

  const present = REQUIRED_COOKIES.filter(k => k in cookieMap);
  const hasAuthMarker = "SID" in cookieMap || "__Secure-1PSID" in cookieMap || "__Secure-3PSID" in cookieMap;
  const hasApiMarker = "SAPISID" in cookieMap || "APISID" in cookieMap;
  if (present.length < 3 && !(hasAuthMarker && hasApiMarker)) {
    return null;
  }

  const cookieStr = Object.entries(cookieMap)
    .filter(([k]) => REQUIRED_COOKIES.includes(k) || k.startsWith("__Secure-") || ["LSID", "OSID", "ACCOUNT_CHOOSER"].includes(k))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");

  return {
    cookies: cookieStr,
    sapisid: cookieMap["SAPISID"] || "",
    source: "edge-extension",
    cookie_names: Object.keys(cookieMap).sort()
  };
}

async function pushCookies() {
  const serverUrl = await getServerUrl();
  const apiKey = await getApiKey();
  const data = await extractCookies();
  
  if (!data) {
    await chrome.storage.local.set({ 
      lastStatus: "no_cookies", 
      lastTime: Date.now(),
      pushCount: (await chrome.storage.local.get("pushCount")).pushCount || 0
    });
    updateBadge("NC", "#f59e0b");
    return false;
  }
  
  try {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["Authorization"] = "Bearer " + apiKey;
    const resp = await fetch(`${serverUrl}/api/cookie/push`, {
      method: "POST",
      headers,
      body: JSON.stringify(data)
    });
    
    if (resp.ok) {
      const result = await resp.json();
      const count = ((await chrome.storage.local.get("pushCount")).pushCount || 0) + 1;
      await chrome.storage.local.set({ 
        lastStatus: "ok", 
        lastTime: Date.now(),
        lastCookies: data.cookies.length,
        pushCount: count,
        lastServerResponse: result.message || "OK",
        lastDiagnostics: result.diagnostics || null,
        lastCookieNames: data.cookie_names || []
      });
      updateBadge("OK", "#22c55e");
      return true;
    } else {
      const errText = await resp.text().catch(() => resp.statusText);
      await chrome.storage.local.set({ 
        lastStatus: "server_error", 
        lastTime: Date.now(),
        lastServerError: errText
      });
      updateBadge("ERR", "#ef4444");
      return false;
    }
  } catch (e) {
    await chrome.storage.local.set({ 
      lastStatus: "disconnected", 
      lastTime: Date.now(),
      lastServerError: e.message
    });
    updateBadge("OFF", "#6b7280");
    return false;
  }
}

function updateBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

async function setupAlarm() {
  const interval = await getInterval();
  await chrome.alarms.clear(ALARM_NAME);
  await chrome.alarms.create(ALARM_NAME, { periodInMinutes: interval });
}

chrome.runtime.onInstalled.addListener(async () => {
  await setupAlarm();
  pushCookies();
  console.log("Gemini Cookie Pusher installed");
});

chrome.runtime.onStartup.addListener(() => {
  pushCookies();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    pushCookies();
  }
});

chrome.webNavigation.onCompleted.addListener((details) => {
  if (details.url && details.url.includes("gemini.google.com")) {
    setTimeout(() => pushCookies(), 3000);
  }
}, { url: [{ hostContains: "gemini.google.com" }] });

chrome.webNavigation.onHistoryStateUpdated.addListener((details) => {
  if (details.url && details.url.includes("gemini.google.com")) {
    setTimeout(() => pushCookies(), 1500);
  }
}, { url: [{ hostContains: "gemini.google.com" }] });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "pushNow") {
    pushCookies().then(ok => sendResponse({ success: ok }));
    return true;
  }
  
  if (msg.action === "getStatus") {
    chrome.storage.local.get(["lastStatus", "lastTime", "serverUrl", "apiKey", "pushCount", "lastServerResponse", "lastServerError", "lastDiagnostics", "lastCookieNames"], (data) => {
      sendResponse({
        lastStatus: data.lastStatus || "unknown",
        lastTime: data.lastTime || null,
        serverUrl: data.serverUrl || DEFAULT_SERVER,
        apiKey: data.apiKey || "",
        pushCount: data.pushCount || 0,
        lastServerResponse: data.lastServerResponse || "",
        lastServerError: data.lastServerError || "",
        lastDiagnostics: data.lastDiagnostics || null,
        lastCookieNames: data.lastCookieNames || []
      });
    });
    return true;
  }
  
  if (msg.action === "setServerUrl") {
    chrome.storage.local.set({ serverUrl: msg.url }).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (msg.action === "setApiKey") {
    chrome.storage.local.set({ apiKey: msg.key }).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (msg.action === "setInterval") {
    chrome.storage.local.set({ pushInterval: msg.interval }).then(async () => {
      await setupAlarm();
      sendResponse({ success: true });
    });
    return true;
  }
});

console.log("Gemini Cookie Pusher background loaded");
