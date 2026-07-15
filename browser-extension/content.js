let popover;
let selectedText = "";
let selectedContext = "";
let translatedText = "";

function removePopover() {
  popover?.remove();
  popover = null;
}

function surroundingContext(range) {
  const element = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
    ? range.commonAncestorContainer
    : range.commonAncestorContainer.parentElement;
  return (element?.closest("p, li, blockquote, article, main")?.innerText || selectedText).trim().slice(0, 2000);
}

function setResult(text, kind = "") {
  const result = popover?.querySelector(".lc-bridge-result");
  if (!result) return;
  result.textContent = text;
  result.dataset.kind = kind;
}

async function bridge(action, payload = {}) {
  const response = await chrome.runtime.sendMessage({ action, ...payload });
  if (!response?.ok) throw new Error(response?.error || "Language Coach is unavailable");
  return response.data;
}

async function handleAction(action) {
  try {
    setResult("处理中...", "loading");
    if (action === "lookup") {
      const data = await bridge("lookup", { text: selectedText });
      const item = data.results?.[0];
      setResult(item ? `${item.headword || item.form}  ${item.meaning_zh || item.core_meaning || ""}` : "本地词库暂未收录", item ? "success" : "muted");
    }
    if (action === "translate") {
      const data = await bridge("translate", { text: selectedText });
      translatedText = data.translated_text;
      setResult(translatedText, "success");
    }
    if (action === "save") {
      await bridge("clip", {
        payload: {
          kind: selectedText.includes(" ") ? "selection" : "word",
          text: selectedText,
          translation: translatedText,
          context: selectedContext,
          page_title: document.title,
          page_url: location.href,
          save_to: "wordbook"
        }
      });
      setResult("已加入 Language Coach 生词本", "success");
    }
  } catch (error) {
    setResult(error.message, "error");
  }
}

function showPopover(rect) {
  removePopover();
  popover = document.createElement("div");
  popover.id = "lc-bridge-popover";
  popover.innerHTML = `
    <div class="lc-bridge-actions">
      <button data-action="lookup">查词</button>
      <button data-action="translate">翻译</button>
      <button data-action="save">保存</button>
      <button data-action="close" title="关闭" aria-label="关闭">×</button>
    </div>
    <div class="lc-bridge-result"></div>`;
  document.documentElement.appendChild(popover);
  const left = Math.max(8, Math.min(window.innerWidth - 328, rect.left + window.scrollX));
  const top = Math.max(8, rect.bottom + window.scrollY + 8);
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
  popover.addEventListener("mousedown", event => event.stopPropagation());
  popover.addEventListener("click", event => {
    const action = event.target.closest("button")?.dataset.action;
    if (action === "close") return removePopover();
    if (action) handleAction(action);
  });
}

document.addEventListener("mouseup", () => {
  setTimeout(() => {
    const selection = window.getSelection();
    const text = selection?.toString().trim().replace(/\s+/g, " ") || "";
    if (!text || text.length > 8000 || selection.rangeCount === 0 || popover?.contains(selection.anchorNode)) return;
    const range = selection.getRangeAt(0);
    selectedText = text;
    selectedContext = surroundingContext(range);
    translatedText = "";
    showPopover(range.getBoundingClientRect());
  }, 0);
});

document.addEventListener("mousedown", event => {
  if (popover && !popover.contains(event.target)) removePopover();
});
