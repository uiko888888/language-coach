import { browser } from "wxt/browser"

const DEFAULTS = { baseUrl: "http://127.0.0.1:8766", token: "" }
const IMPORT_MENU_ID = "language-coach-import-article"

async function settings() {
  return browser.storage.local.get(DEFAULTS)
}

async function api(path: string, options: RequestInit = {}) {
  const config = await settings()
  const response = await fetch(`${config.baseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Language-Coach-Token": String(config.token),
      ...(options.headers || {}),
    },
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`)
  return data
}

export default defineBackground(() => {
  browser.runtime.onInstalled.addListener(async () => {
    await browser.contextMenus.removeAll()
    browser.contextMenus.create({ id: IMPORT_MENU_ID, title: "导入当前页面到 Language Coach", contexts: ["page"] })
  })

  browser.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId === IMPORT_MENU_ID && tab?.id) {
      await browser.tabs.sendMessage(tab.id, { action: "extractArticle" })
    }
  })

  browser.runtime.onMessage.addListener((message: Record<string, unknown>, _sender, sendResponse) => {
    void (async () => {
      if (message.action === "lookup") {
        const config = await settings()
        const response = await fetch(`${config.baseUrl}/api/lexicon/search?q=${encodeURIComponent(String(message.text || ""))}`)
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || "Lookup failed")
        return data
      }
      if (message.action === "translate") {
        return api("/api/browser/translate", { method: "POST", body: JSON.stringify({ text: message.text }) })
      }
      if (message.action === "clip") {
        return api("/api/browser/clips", { method: "POST", body: JSON.stringify(message.payload) })
      }
      if (message.action === "status") return api("/api/browser/status")
      throw new Error("Unknown browser bridge action")
    })().then(data => sendResponse({ ok: true, data })).catch(error => sendResponse({ ok: false, error: error.message }))
    return true
  })

  browser.action.onClicked.addListener(() => browser.runtime.openOptionsPage())
})
