const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = 8767;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "review-e2e.sqlite");

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/version`);
      if (response.ok) return response.json();
    } catch (_error) {
      // The isolated server is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error("Temporary Language Coach server did not start");
}

function removeDatabase() {
  for (const suffix of ["", "-wal", "-shm"]) {
    try { fs.unlinkSync(database + suffix); } catch (_error) { /* already absent */ }
  }
}

async function run() {
  removeDatabase();
  const server = spawn("python", ["backend/server.py", String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, LANGUAGE_COACH_DB_PATH: database },
  });
  const failures = [];
  let browser;
  try {
    const version = await waitForServer();
    if (version.app_version !== "0.8.0-alpha.24.5" || version.database_schema_version !== 18) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const cardResponse = await fetch(`${baseUrl}/api/cards`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        term: "evidence-based practice",
        kind: "phrase",
        context: "Evidence-based practice connects a claim to reliable research.",
      }),
    });
    if (!cardResponse.ok) failures.push(`failed to seed review card: ${await cardResponse.text()}`);
    const articleResponse = await fetch(`${baseUrl}/api/articles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Complete the Words review contract",
        source: "manual",
        body: "Smart devices promise convenience, but they also create a quiet record of daily life. A speaker can learn when a family is at home, a watch can reveal health patterns, and a doorbell camera can capture people who never agreed to be recorded. Supporters argue that these tools save time and improve safety. However, critics point out that privacy policies are often difficult to read, and users may not understand how much information is stored or shared. The central challenge is whether companies can design useful products while giving people meaningful control over their own data. Clearer consent, shorter privacy notices, and stronger limits on data sharing would make smart devices easier to trust. Without those safeguards, convenience may gradually become a form of surveillance.",
      }),
    });
    const articleData = await articleResponse.json();
    if (!articleResponse.ok) failures.push(`failed to seed article: ${JSON.stringify(articleData)}`);
    const quizResponse = await fetch(`${baseUrl}/api/articles/${articleData.article.id}/quizzes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "cloze", style: "TOEFL", question_type: "complete-words" }),
    });
    const quizData = await quizResponse.json();
    if (!quizResponse.ok || !quizData.quizzes?.length) failures.push(`failed to seed complete-word quiz: ${JSON.stringify(quizData)}`);
    const completeWordQuiz = quizData.quizzes[0];
    const attemptResponse = await fetch(`${baseUrl}/api/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_id: completeWordQuiz.id, answer: completeWordQuiz.answer.slice(0, 2), confidence: 2 }),
    });
    if (!attemptResponse.ok) failures.push(`failed to seed complete-word attempt: ${await attemptResponse.text()}`);

    const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
    browser = await chromium.launch({
      headless: true,
      executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
    page.on("response", response => {
      if (response.status() >= 400 && !response.url().endsWith("/favicon.ico")) {
        failures.push(`response ${response.status()}: ${response.url()}`);
      }
    });
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    if (await page.locator("#profileEditor[open]").count()) await page.click("#cancelProfileDialogBtn");
    if (await page.locator("#assistantDialog[open]").count()) await page.click("#closeAssistantBtn");
    await page.click('[data-view="cards"]');
    await page.waitForSelector("#view-cards.active");

    const sidebarPosition = await page.locator(".sidebar").evaluate(element => getComputedStyle(element).position);
    if (sidebarPosition !== "fixed") failures.push(`sidebar is not fixed: ${sidebarPosition}`);
    const columns = await page.locator(".review-workspace").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (columns.split(" ").length < 2) failures.push(`review workspace is not split: ${columns}`);
    const initialDueCount = Number(await page.locator("#reviewDueCount").innerText());
    if (initialDueCount < 1) failures.push("due review count is empty");
    if (!(await page.locator("#reviewQueue").innerText()).includes("evidence-based practice")) failures.push("seed phrase is missing from queue");
    if (!(await page.locator("#reviewDetail h2").innerText()).includes("evidence-based practice")) failures.push("seed phrase is not selected");

    await page.click("#revealReviewAnswerBtn");
    if (await page.locator("[data-rate-review]").count() !== 4) failures.push("four review ratings are not visible");
    const intervals = await page.locator("[data-rate-review] small").allTextContents();
    if (new Set(intervals).size !== 4) failures.push(`rating intervals are not distinct: ${intervals.join(", ")}`);
    await page.screenshot({ path: path.join(root, "artifacts", "review-workspace-desktop.png"), fullPage: true });

    await page.click('[data-rate-review="good"]');
    await page.waitForFunction(expected => Number(document.querySelector("#reviewDueCount")?.textContent.trim()) === expected, initialDueCount - 1);
    if (await page.locator("#undoReviewBtn").isDisabled()) failures.push("undo did not become available");
    await page.click("#undoReviewBtn");
    await page.waitForFunction(expected => Number(document.querySelector("#reviewDueCount")?.textContent.trim()) === expected, initialDueCount);

    await page.click('[data-review-mode="complete-words"]');
    await page.waitForSelector("#completeWordReviewPane:not([hidden])");
    const completeColumns = await page.locator(".complete-word-workspace").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (completeColumns.split(" ").length < 2) failures.push(`complete-word workspace is not split: ${completeColumns}`);
    if (Number(await page.locator("#completeWordCount").innerText()) !== 1) failures.push("attempted complete-word item is missing");
    await page.fill("#completeWordAnswer", completeWordQuiz.answer);
    await page.press("#completeWordAnswer", "Enter");
    await page.waitForSelector(".complete-word-result.correct");
    if (await page.locator("[data-rate-complete-word]").count() !== 4) failures.push("complete-word FSRS ratings are missing");
    await page.screenshot({ path: path.join(root, "artifacts", "complete-word-review-desktop.png"), fullPage: true });
    await page.click('[data-rate-complete-word="good"]');
    if (await page.locator("#completeWordUndoBtn").isDisabled()) failures.push("complete-word undo did not become available");
    await page.click("#completeWordUndoBtn");
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise(resolve => server.once("exit", resolve));
    removeDatabase();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  process.stdout.write("Memory and Complete the Words review workflows passed on isolated schema 18.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
