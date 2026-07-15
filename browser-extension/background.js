const DEFAULTS = { baseUrl: "http://127.0.0.1:8766", token: "" };

async function settings() {
  return chrome.storage.local.get(DEFAULTS);
}

async function api(path, options = {}) {
  const config = await settings();
  const response = await fetch(`${config.baseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Language-Coach-Token": config.token,
      ...(options.headers || {}),
    },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message.action === "lookup") {
      const config = await settings();
      const response = await fetch(`${config.baseUrl}/api/lexicon/search?q=${encodeURIComponent(message.text)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Lookup failed");
      return data;
    }
    if (message.action === "translate") {
      return api("/api/browser/translate", { method: "POST", body: JSON.stringify({ text: message.text }) });
    }
    if (message.action === "clip") {
      return api("/api/browser/clips", { method: "POST", body: JSON.stringify(message.payload) });
    }
    if (message.action === "status") return api("/api/browser/status");
    throw new Error("Unknown browser bridge action");
  })().then(data => sendResponse({ ok: true, data })).catch(error => sendResponse({ ok: false, error: error.message }));
  return true;
});

chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
