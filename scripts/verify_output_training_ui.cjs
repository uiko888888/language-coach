const fs = require("fs");
const http = require("http");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const port = 8774;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "output-training-e2e.sqlite3");
const aiPort = 8775;

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
  const aiServer = http.createServer((_request, response) => {
    const dimensions = Object.fromEntries(
      ["information", "collocation", "register", "coherence", "naturalness"].map(key => [key, {
        score: 4,
        finding: "The response preserves the intended meaning.",
        suggestion: "Keep the wording concise.",
        evidence_quote: "",
      }]),
    );
    const content = JSON.stringify({
      summary: "Accurate reconstruction with a natural structure.",
      dimensions,
      revised_response: "Independent bookstores create welcoming spaces where readers discover unfamiliar writers.",
    });
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ choices: [{ message: { content } }] }));
  });
  await new Promise(resolve => aiServer.listen(aiPort, "127.0.0.1", resolve));
  const server = spawn("python", ["backend/server.py", String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      LANGUAGE_COACH_DB_PATH: database,
      OUTPUT_AI_PROVIDER: "openai-compatible",
      OUTPUT_AI_API_URL: `http://127.0.0.1:${aiPort}/v1/chat/completions`,
      OUTPUT_AI_API_KEY: "e2e-key",
      OUTPUT_AI_MODEL: "e2e-model",
    },
  });
  let browser;
  const failures = [];
  try {
    const version = await waitForServer();
    if (version.app_version !== "0.8.0-alpha.24.1" || version.database_schema_version !== 15) {
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
    await page.click("[data-request-semantic-feedback]");
    await page.waitForFunction(() => document.querySelectorAll(".semantic-dimensions article").length === 5);
    await page.click('[data-output-feedback-decision="keep"]');
    await page.waitForFunction(() => document.querySelector('[data-output-feedback-decision="keep"]')?.classList.contains("active"));
    await page.fill("#customReviewTerm", "create welcoming spaces");
    await page.fill("#customReviewContext", reconstruction.reference_text);
    await page.click("[data-save-output-custom-review]");
    await page.click('[data-contrast-answer="say-tell-speak-talk"][data-contrast-index="1"]');
    await page.waitForSelector(".contrast-result.correct");
    await page.screenshot({ path: path.join(root, "artifacts", "output-feedback-desktop.png"), fullPage: true });
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
      "print('semantic', c.execute(\"SELECT COUNT(*) FROM output_semantic_feedback\").fetchone()[0])",
      "print('decisions', c.execute(\"SELECT COUNT(*) FROM output_feedback_decisions\").fetchone()[0])",
      "print('contrasts', c.execute(\"SELECT COUNT(*) FROM usage_contrast_attempts\").fetchone()[0])",
      "print('custom', c.execute(\"SELECT COUNT(*) FROM output_review_links WHERE link_type='custom'\").fetchone()[0])",
    ].join("; ")], { cwd: root, env: { ...process.env, LANGUAGE_COACH_DB_PATH: database } }).toString();
    if (!dbState.includes("Review the collocation next week.")) failures.push("self review was not persisted");
    if (!dbState.includes("'reading_words':") || !dbState.includes("'output_sentences':")) failures.push(`daily metrics are incomplete: ${dbState}`);
    if (!/\r?\n2\r?\n/.test(dbState)) failures.push(`output review links were not persisted: ${dbState}`);
    for (const marker of ["semantic 1", "decisions 1", "contrasts 1", "custom 1"]) {
      if (!dbState.includes(marker)) failures.push(`${marker} was not persisted: ${dbState}`);
    }
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise(resolve => aiServer.close(resolve));
  }
  if (failures.length) throw new Error(failures.join("\n"));
  console.log("semantic output feedback desktop E2E passed");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
