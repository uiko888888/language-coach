const fs = require("fs");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const port = 8774;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "output-training-e2e.sqlite3");

function removeDatabase() {
  for (const suffix of ["", "-shm", "-wal"]) {
    const target = `${database}${suffix}`;
    if (fs.existsSync(target)) fs.rmSync(target);
  }
}

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/version`);
      if (response.ok) return response.json();
    } catch (_error) {}
    await new Promise(resolve => setTimeout(resolve, 120));
  }
  throw new Error("Temporary Language Coach server did not start");
}

async function post(url, body) {
  const response = await fetch(`${baseUrl}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${url} failed: ${response.status} ${await response.text()}`);
  return response.json();
}

async function run() {
  removeDatabase();
  const server = spawn("python", ["backend/server.py", String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, LANGUAGE_COACH_DB_PATH: database },
  });
  let browser;
  const failures = [];
  try {
    const version = await waitForServer();
    if (version.app_version !== "0.8.0-alpha.24.0" || version.database_schema_version !== 14) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const body = [
      "Independent bookstores create welcoming spaces where readers can discover unfamiliar writers and discuss ideas with neighbors after work.",
      "Online recommendations are convenient, but they often repeat familiar choices instead of encouraging readers to explore different styles.",
      "Local booksellers remember community interests and can connect a new novel with conversations that are already happening nearby.",
      "Supporting these shops therefore protects more than retail activity; it keeps cultural discovery visible in everyday public life.",
    ].join("\n\n");
    const translation = [
      "独立书店营造出亲切的空间，读者可以发现陌生作家，并在下班后与邻居讨论观点。",
      "网络推荐很方便，但它们往往重复熟悉的选择，而不是鼓励读者探索不同风格。",
      "本地书商会记住社区兴趣，并能把一本新小说与附近正在发生的讨论联系起来。",
      "因此，支持这些书店所保护的不只是零售活动，也让文化发现持续出现在日常公共生活中。",
    ].join("\n\n");
    const created = await post("/api/articles", { title: "Why independent bookstores matter", body, level: "B2", source: "manual" });
    const articleId = created.article.id;
    await post(`/api/articles/${articleId}/translation`, { translation_zh: translation, exam: "IELTS" });
    const taskSet = await post(`/api/articles/${articleId}/output-tasks`, {});
    const reconstruction = taskSet.tasks.find(task => task.task_type === "zh_to_en");

    const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
    browser = await chromium.launch({ headless: true, executablePath: fs.existsSync(edgePath) ? edgePath : undefined });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    if (await page.locator("#assistantDialog[open]").count()) await page.click("#closeAssistantBtn");
    if (await page.locator("#profileEditor[open]").count()) await page.click("#cancelProfileDialogBtn");
    await page.click('[data-view="articles"]');
    await page.click(`[data-select-article="${articleId}"]`);
    await page.click(`[data-output-article="${articleId}"]`);
    await page.waitForSelector("#view-output.active");
    const sidebarPosition = await page.locator(".sidebar").evaluate(node => getComputedStyle(node).position);
    if (sidebarPosition !== "fixed") failures.push(`sidebar position is ${sidebarPosition}`);
    const columns = await page.locator(".output-workspace").evaluate(node => getComputedStyle(node).gridTemplateColumns);
    if (!columns || columns.split(" ").length < 2) failures.push(`output workspace is not split: ${columns}`);
    await page.waitForFunction(() => document.querySelectorAll("#outputTaskTabs button").length === 4);
    if (await page.locator("#outputTaskTabs button").count() !== 4) failures.push("four output task tabs were not rendered");
    await page.click('[data-output-task-index="1"]');
    await page.fill("#outputResponse", reconstruction.reference_text);
    await page.selectOption("#outputConfidence", "3");
    await page.click("#submitOutputBtn");
    await page.waitForSelector(".output-feedback");
    if (await page.locator(".output-check.passed").count() < 2) failures.push("deterministic feedback did not pass known reconstruction signals");
    await page.selectOption("#selfReviewInformation", "3");
    await page.selectOption("#selfReviewNaturalness", "2");
    await page.selectOption("#selfReviewChunk", "2");
    await page.fill("#selfReviewNote", "Review the collocation next week.");
    await page.click("[data-save-output-self-review]");
    await page.click("[data-save-output-review]");
    await page.waitForFunction(() => document.querySelector("[data-save-output-review]")?.disabled === true);
    await page.screenshot({ path: path.join(root, "artifacts", "output-training-desktop.png"), fullPage: true });
    await page.click('[data-view="reader"]');
    await page.click("#markArticleReadBtn");
    await page.waitForTimeout(150);

    const dbState = execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      "a=c.execute(\"SELECT response_text, self_review_json FROM output_attempts ORDER BY id DESC LIMIT 1\").fetchone()",
      "print(a[0])",
      "print(a[1])",
      "print(c.execute(\"SELECT COUNT(*) FROM output_review_links\").fetchone()[0])",
      "print(dict(c.execute(\"SELECT metric, value FROM daily_learning_metrics\").fetchall()))",
    ].join("; ")], { cwd: root, env: { ...process.env, LANGUAGE_COACH_DB_PATH: database } }).toString();
    if (!dbState.includes("Review the collocation next week.")) failures.push("self review was not persisted");
    if (!dbState.includes("'reading_words':") || !dbState.includes("'output_sentences':")) failures.push(`daily metrics are incomplete: ${dbState}`);
    if (!/\r?\n1\r?\n/.test(dbState)) failures.push(`output review link was not persisted: ${dbState}`);
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  console.log("contextual output desktop E2E passed");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
