import Defuddle from "defuddle"
import { browser } from "wxt/browser"

const STYLE = `
#lc-bridge-popover{position:absolute;z-index:2147483647;width:320px;padding:8px;border:1px solid #cfd8d4;border-radius:8px;background:#fff;color:#1f2a28;box-shadow:0 12px 30px rgba(24,36,33,.18);font:14px/1.45 "Segoe UI","Microsoft YaHei",sans-serif}
#lc-bridge-popover *{box-sizing:border-box}.lc-bridge-actions{display:grid;grid-template-columns:repeat(3,1fr) 32px;gap:5px}.lc-bridge-actions button{min-height:32px;padding:0 8px;border:1px solid #d8ded8;border-radius:6px;background:#f7faf8;color:#1f2a28;cursor:pointer}.lc-bridge-actions button:hover{border-color:#1b7f78;color:#115d58}.lc-bridge-result{max-height:180px;margin-top:7px;padding:8px;overflow-y:auto;border-left:3px solid #d8ded8;background:#f7f9f7;white-space:pre-wrap}.lc-bridge-result:empty{display:none}.lc-bridge-result[data-kind=success]{border-left-color:#1b7f78}.lc-bridge-result[data-kind=error]{border-left-color:#b43b3b;color:#8d2929}.lc-bridge-result[data-kind=loading],.lc-bridge-result[data-kind=muted]{color:#66736f}
`

type BridgeResponse = { ok: boolean; data?: any; error?: string }
let popover: HTMLDivElement | null = null
let selectedText = ""
let selectedContext = ""
let translatedText = ""

function removePopover() { popover?.remove(); popover = null }

function setResult(text: string, kind = "") {
  const result = popover?.querySelector<HTMLElement>(".lc-bridge-result")
  if (!result) return
  result.textContent = text
  result.dataset.kind = kind
}

async function bridge(action: string, payload: Record<string, unknown> = {}) {
  const response = await browser.runtime.sendMessage({ action, ...payload }) as BridgeResponse
  if (!response?.ok) throw new Error(response?.error || "Language Coach is unavailable")
  return response.data
}

function contextFor(range: Range) {
  const node = range.commonAncestorContainer
  const element = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement
  return (element?.closest("p,li,blockquote,article,main")?.textContent || selectedText).trim().slice(0, 2000)
}

async function extractArticle() {
  setResult("正在提取正文...", "loading")
  const snapshot = document.implementation.createHTMLDocument(document.title)
  snapshot.documentElement.innerHTML = document.documentElement.outerHTML
  const parsed = new Defuddle(snapshot, { url: location.href, useAsync: false }).parse()
  const holder = document.createElement("div")
  holder.innerHTML = parsed.content || ""
  const paragraphs = Array.from(holder.querySelectorAll("h1,h2,h3,p,li,blockquote"))
    .map(element => element.textContent?.trim() || "")
    .filter(Boolean)
  const text = paragraphs.join("\n\n") || document.querySelector("article,main")?.textContent?.trim() || ""
  if (text.length < 200) throw new Error("没有识别到足够的正文内容")
  const data = await bridge("clip", { payload: { kind: "article", text, page_title: parsed.title || document.title, page_url: location.href, save_to: "articles" } })
  showStatus(`已导入文章池：${data.article?.title || document.title}`, "success")
}

async function handleAction(action: string) {
  try {
    setResult("处理中...", "loading")
    if (action === "lookup") {
      const data = await bridge("lookup", { text: selectedText })
      const item = data.results?.[0]
      setResult(item ? `${item.headword || item.form}  ${item.meaning_zh || item.core_meaning || ""}` : "本地词库暂未收录", item ? "success" : "muted")
    }
    if (action === "translate") {
      const data = await bridge("translate", { text: selectedText })
      translatedText = data.translated_text
      setResult(translatedText, "success")
    }
    if (action === "save") {
      await bridge("clip", { payload: { kind: selectedText.includes(" ") ? "selection" : "word", text: selectedText, translation: translatedText, context: selectedContext, page_title: document.title, page_url: location.href, save_to: "wordbook" } })
      setResult("已加入 Language Coach 生词本", "success")
    }
  } catch (error) { setResult(error instanceof Error ? error.message : String(error), "error") }
}

function showStatus(text: string, kind = "") {
  showPopover({ left: window.innerWidth - 340, bottom: 14, top: 14 } as DOMRect)
  setResult(text, kind)
}

function showPopover(rect: DOMRect) {
  removePopover()
  popover = document.createElement("div")
  popover.id = "lc-bridge-popover"
  popover.innerHTML = `<div class="lc-bridge-actions"><button data-action="lookup">查词</button><button data-action="translate">翻译</button><button data-action="save">保存</button><button data-action="close" title="关闭">×</button></div><div class="lc-bridge-result"></div>`
  document.documentElement.appendChild(popover)
  popover.style.left = `${Math.max(8, Math.min(window.innerWidth - 328, rect.left + window.scrollX))}px`
  popover.style.top = `${Math.max(8, rect.bottom + window.scrollY + 8)}px`
  popover.addEventListener("mousedown", event => event.stopPropagation())
  popover.addEventListener("click", event => {
    const action = (event.target as Element).closest<HTMLButtonElement>("button")?.dataset.action
    if (action === "close") removePopover()
    else if (action) void handleAction(action)
  })
}

export default defineContentScript({
  matches: ["http://*/*", "https://*/*"],
  main() {
    const style = document.createElement("style"); style.textContent = STYLE; document.documentElement.appendChild(style)
    document.addEventListener("mouseup", () => setTimeout(() => {
      const selection = window.getSelection(); const text = selection?.toString().trim().replace(/\s+/g, " ") || ""
      if (!text || text.length > 8000 || !selection?.rangeCount) return
      const range = selection.getRangeAt(0); selectedText = text; selectedContext = contextFor(range); translatedText = ""; showPopover(range.getBoundingClientRect())
    }, 0))
    document.addEventListener("mousedown", event => { if (popover && !popover.contains(event.target as Node)) removePopover() })
    browser.runtime.onMessage.addListener(message => {
      if (message.action === "extractArticle") void extractArticle().catch(error => showStatus(error.message, "error"))
    })
  },
})
