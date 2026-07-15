import { browser } from "wxt/browser"
import "./style.css"

const defaults = { baseUrl: "http://127.0.0.1:8766", token: "" }
const baseUrl = document.querySelector<HTMLInputElement>("#baseUrl")!
const token = document.querySelector<HTMLInputElement>("#token")!
const status = document.querySelector<HTMLElement>("#status")!

const saved = await browser.storage.local.get(defaults)
baseUrl.value = String(saved.baseUrl)
token.value = String(saved.token)

document.querySelector("#saveBtn")!.addEventListener("click", async () => {
  const endpoint = baseUrl.value.trim().replace(/\/$/, "")
  const bridgeToken = token.value.trim()
  await browser.storage.local.set({ baseUrl: endpoint, token: bridgeToken })
  try {
    const response = await fetch(`${endpoint}/api/browser/clips`, { headers: { "X-Language-Coach-Token": bridgeToken } })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || "连接失败")
    status.textContent = "连接成功"; status.dataset.ok = "true"
  } catch (error) { status.textContent = error instanceof Error ? error.message : String(error); status.dataset.ok = "false" }
})
