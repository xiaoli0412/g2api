const DEFAULT_SERVER = "http://127.0.0.1:8081";
const ALARM_NAME = "push-cookies";
const INTERVAL_MINUTES = 10;
const REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"];

// Get server URL from storage
async function getServerUrl() {
  const data = await chrome.storage.local.get("serverUrl");
  return data.serverUrl || DEFAULT_SERVER;
}

// Extract cookies from gemini.google.com
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
      
      // Check if we have enough required cookies
      const present = REQUIRED_COOKIES.filter(k => k in cookieMap);
      if (present.length < 3) {
        resolve(null);
        return;
      }
      
      // Build cookie string
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

// Push cookies to server
async function pushCookies() {
  const serverUrl = await getServerUrl();
  const data = await extractCookies();
  
  if (!data) {
    await chrome.storage.local.set({ 
      lastStatus: "no_cookies", 
      lastTime: Date.now() 
    });
    updateBadge("NC", "#f59e0b");
    return false;
  }
  
  try {
    const resp = await fetch(`${serverUrl}/api/cookie/push`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    
    if (resp.ok) {
      await chrome.storage.local.set({ 
        lastStatus: "ok", 
        lastTime: Date.now(),
        lastCookies: data.cookies.length
      });
      updateBadge("OK", "#22c55e");
      return true;
    } else {
      await chrome.storage.local.set({ 
        lastStatus: "server_error", 
        lastTime: Date.now() 
      });
      updateBadge("ERR", "#ef4444");
      return false;
    }
  } catch (e) {
    await chrome.storage.local.set({ 
      lastStatus: "disconnected", 
      lastTime: Date.now() 
    });
    updateBadge("OFF", "#6b7280");
    return false;
  }
}

// Update badge
function updateBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

// On installed
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: INTERVAL_MINUTES });
  pushCookies();
  console.log("Gemini Cookie Pusher installed");
});

// On startup
chrome.runtime.onStartup.addListener(() => {
  pushCookies();
});

// On alarm
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    pushCookies();
  }
});

// On message
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
    chrome.storage.local.set({ serverUrl: msg.url }).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }
});

// Log
console.log("Gemini Cookie Pusher background loaded");
