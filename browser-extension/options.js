const defaults = { baseUrl: "http://127.0.0.1:8766", token: "" };

async function load() {
  const data = await chrome.storage.local.get(defaults);
  document.querySelector("#baseUrl").value = data.baseUrl;
  document.querySelector("#token").value = data.token;
}

document.querySelector("#saveBtn").addEventListener("click", async () => {
  const baseUrl = document.querySelector("#baseUrl").value.trim().replace(/\/$/, "");
  const token = document.querySelector("#token").value.trim();
  const status = document.querySelector("#status");
  await chrome.storage.local.set({ baseUrl, token });
  try {
    const response = await fetch(`${baseUrl}/api/browser/clips`, { headers: { "X-Language-Coach-Token": token } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "连接失败");
    status.textContent = "连接成功";
    status.dataset.ok = "true";
  } catch (error) {
    status.textContent = error.message;
    status.dataset.ok = "false";
  }
});

load();
