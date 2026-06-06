const DEFAULT_SERVER = "http://127.0.0.1:8081";
const ALARM_NAME = "push-cookies";
const INTERVAL_MINUTES = 10;
const REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"];

async function getServerUrl() {
  const data = await chrome.storage.local.get("serverUrl");
  return data.serverUrl || DEFAULT_SERVER;
}

async function extractCookies() {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain: "gemini.google.com" }, (cookies) => {
      if (!cookies || cookies.length === 0) {
        resolve(null);
        return;
      }
      const cookieMap = {};
      for (const c of cookies) {
        cookieMap[c.name] = c.value;
      }
      const present = REQUIRED_COOKIES.filter(k => k in cookieMap);
      if (present.length < 3) {
        resolve(null);
        return;
      }
      const cookieStr = Object.entries(cookieMap)
        .filter(([k]) => REQUIRED_COOKIES.includes(k) || k.startsWith("__Secure-"))
        .map(([k, v]) => `${k}=${v}`)
        .join("; ");
      resolve({
        cookies: cookieStr,
        sapisid: cookieMap["SAPISID"] || ""
      });
    });
  });
}

async function pushCookies() {
  const serverUrl = await getServerUrl();
  const data = await extractCookies();
  if (!data) {
    await chrome.storage.local.set({ lastStatus: "no_cookies", lastTime: Date.now() });
    chrome.action.setBadgeText({ text: "NC" });
    chrome.action.setBadgeBackgroundColor({ color: "#f59e0b" });
    return false;
  }
  try {
    const resp = await fetch(`${serverUrl}/api/cookie/push`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    if (resp.ok) {
      await chrome.storage.local.set({ lastStatus: "ok", lastTime: Date.now() });
      chrome.action.setBadgeText({ text: "OK" });
      chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
      return true;
    } else {
      await chrome.storage.local.set({ lastStatus: "server_error", lastTime: Date.now() });
      chrome.action.setBadgeText({ text: "ERR" });
      chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });
      return false;
    }
  } catch (e) {
    await chrome.storage.local.set({ lastStatus: "disconnected", lastTime: Date.now() });
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#6b7280" });
    return false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: INTERVAL_MINUTES });
  pushCookies();
});

chrome.runtime.onStartup.addListener(() => {
  pushCookies();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    pushCookies();
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "pushNow") {
    pushCookies().then(ok => sendResponse({ success: ok }));
    return true;
  }
  if (msg.action === "getStatus") {
    chrome.storage.local.get(["lastStatus", "lastTime", "serverUrl"], (data) => {
      sendResponse({
        lastStatus: data.lastStatus || "unknown",
        lastTime: data.lastTime || null,
        serverUrl: data.serverUrl || DEFAULT_SERVER
      });
    });
    return true;
  }
  if (msg.action === "setServerUrl") {
    chrome.storage.local.set({ serverUrl: msg.url }).then(() => sendResponse({ success: true }));
    return true;
  }
});
