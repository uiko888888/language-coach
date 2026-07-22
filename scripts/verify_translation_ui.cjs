const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = 8768;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "translation-e2e.sqlite");

function removeDatabase() {
  for (const suffix of ["", "-wal", "-shm"]) {
    try { fs.unlinkSync(database + suffix); } catch (_error) { /* already absent */ }
  }
}

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/version`);
      if (response.ok) return response.json();
    } catch (_error) { /* starting */ }
    await new Promise(resolve => setTimeout(resolve, 250));
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
    if (version.app_version !== "0.8.0-alpha.25.15" || version.database_schema_version !== 23) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const created = await post("/api/articles", {
      title: "Translation workflow",
      body: "Evidence helps readers evaluate a public claim.\n\nReliable sources make the reasoning easier to verify.",
      level: "B2",
      source: "manual",
    });
    const articleId = created.article.id;
    const summary = await post("/api/articles", {
      title: "Feed summary quality gate",
      body: "A president has not explained a dismissal, causing concern among civil society and the military.",
      level: "B2",
      source: "manual",
    });
    const summaryId = summary.article.id;
    execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      `c.execute(\"UPDATE articles SET source='BBC World', source_url='https://example.test/original', content_status='summary' WHERE id=?\", (${summaryId},))`,
      "c.commit()",
      "c.close()",
    ].join("; ")], { cwd: root, env: { ...process.env, LANGUAGE_COACH_DB_PATH: database } });

    const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
    browser = await chromium.launch({ headless: true, executablePath: fs.existsSync(edgePath) ? edgePath : undefined });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    if (await page.locator("#assistantDialog[open]").count()) await page.click("#closeAssistantBtn");
    if (await page.locator("#profileEditor[open]").count()) await page.click("#cancelProfileDialogBtn");
    await page.click('[data-view="articles"]');
    await page.click(`[data-select-article="${summaryId}"]`);
    await page.click(`#view-articles [data-open-article="${summaryId}"]`);
    await page.waitForSelector("#view-reader.active");
    if (!(await page.locator("#readerTitle").innerText()).startsWith("来源摘要")) failures.push("summary is presented as original text");
    if (!(await page.locator("#readerContentNotice").innerText()).includes("不是原文")) failures.push("summary boundary notice is missing");
    if (!(await page.locator("#generateQuizBtn").isDisabled())) failures.push("summary can still generate exam questions");
    const rejected = await fetch(`${baseUrl}/api/articles/${summaryId}/quizzes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style: "IELTS", question_type: "tfng" }),
    });
    if (rejected.status !== 422) failures.push(`summary API gate returned ${rejected.status}`);
    await page.screenshot({ path: path.join(root, "artifacts", "content-quality-summary-desktop.png"), fullPage: true });

    await page.click('[data-view="articles"]');
    await page.click(`[data-select-article="${articleId}"]`);
    await page.click(`#view-articles [data-open-article="${articleId}"]`);
    await page.waitForSelector("#view-reader.active");
    await page.click('[data-view="quiz"]');
    await page.waitForSelector("#view-quiz.active");
    if ((await page.locator("#quizTranslationBtn").innerText()) !== "一键翻译") failures.push("missing translation action is not explicit");

    await post(`/api/articles/${articleId}/translation`, { translation_zh: "证据帮助读者评估公共主张。\n\n可靠的来源使推理更容易验证。" });
    const translationResponse = page.waitForResponse(response => response.url().includes(`/api/articles/${articleId}/translate`));
    await page.click("#quizTranslationBtn");
    if (!(await translationResponse).ok()) failures.push("one-click translation request failed");
    await page.waitForFunction(() => document.querySelectorAll("#quizSourceText .paragraph-translation:not(.missing)").length === 2);
    const translatedText = await page.locator("#quizSourceText").innerText();
    if (!translatedText.includes("证据帮助读者") || translatedText.includes("本段暂无译文")) failures.push("aligned Chinese was not rendered");
    const columns = await page.locator(".quiz-workspace").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (columns.split(" ").length < 2) failures.push(`practice layout is not split: ${columns}`);
    await page.screenshot({ path: path.join(root, "artifacts", "practice-translation-desktop.png"), fullPage: true });
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  process.stdout.write("Practice one-click translation workflow passed on schema 23.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
