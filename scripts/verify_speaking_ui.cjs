const fs = require("fs");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const port = 8776;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "speaking-e2e.sqlite3");
const audioDirectory = path.join(root, "artifacts", "speaking-e2e-audio");

function removeArtifacts() {
  for (const suffix of ["", "-shm", "-wal"]) {
    const target = `${database}${suffix}`;
    if (fs.existsSync(target)) fs.rmSync(target);
  }
  if (fs.existsSync(audioDirectory)) fs.rmSync(audioDirectory, { recursive: true, force: true });
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
  removeArtifacts();
  const server = spawn("python", ["backend/server.py", String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      LANGUAGE_COACH_DB_PATH: database,
      LANGUAGE_COACH_AUDIO_DIR: audioDirectory,
      SPEECH_TRANSCRIPTION_PROVIDER: "",
    },
  });
  let browser;
  const failures = [];
  try {
    const version = await waitForServer();
    if (version.app_version !== "0.8.0-alpha.24.2" || version.database_schema_version !== 16) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const body = [
      "Independent bookstores give readers a place to discover unfamiliar writers and discuss new ideas with neighbors.",
      "Online recommendations are convenient, but they can repeat familiar choices instead of widening a reader's attention.",
      "Local booksellers understand community interests and connect books with conversations already happening nearby.",
      "Supporting these shops therefore protects cultural discovery as well as ordinary retail activity.",
    ].join("\n\n");
    const created = await post("/api/articles", {
      title: "Why independent bookstores matter",
      body,
      level: "B2",
      source: "manual",
    });
    const articleId = created.article.id;
    const taskSet = await post(`/api/articles/${articleId}/speaking-tasks`, {
      duration_target: 30,
      prep_seconds: 0,
    });
    if (taskSet.tasks.length !== 3) failures.push("three speaking task types were not created");
    if (!taskSet.tasks.find(task => task.task_type === "retell")?.evidence_eligible) failures.push("retelling is not evidence eligible");
    if (taskSet.tasks.find(task => task.task_type === "chunk")?.evidence_eligible) failures.push("chunk drill incorrectly counts as profile evidence");

    const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
    browser = await chromium.launch({
      headless: true,
      executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
      args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
    });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["microphone"] });
    const page = await context.newPage();
    page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    if (await page.locator("#assistantDialog[open]").count()) await page.click("#closeAssistantBtn");
    if (await page.locator("#profileEditor[open]").count()) await page.click("#cancelProfileDialogBtn");
    await page.click('[data-view="articles"]');
    await page.click(`[data-select-article="${articleId}"]`);
    await page.click(`[data-speaking-article="${articleId}"]`);
    await page.waitForSelector("#view-speaking.active");
    await page.click('[data-speaking-duration="30"]');
    await page.waitForFunction(() => document.querySelectorAll("#speakingTaskList button").length === 3);

    const sidebarPosition = await page.locator(".sidebar").evaluate(node => getComputedStyle(node).position);
    if (sidebarPosition !== "fixed") failures.push(`sidebar position is ${sidebarPosition}`);
    const columns = await page.locator(".speaking-workspace").evaluate(node => getComputedStyle(node).gridTemplateColumns);
    if (!columns || columns.split(" ").length < 2) failures.push(`speaking workspace is not split: ${columns}`);

    await page.click("[data-begin-speaking]");
    await page.waitForSelector("[data-pause-speaking]", { timeout: 25000 });
    await page.click("[data-pause-speaking]");
    await page.waitForTimeout(250);
    await page.click("[data-pause-speaking]");
    await page.waitForTimeout(1200);
    await page.click("[data-stop-speaking]");
    await page.waitForSelector(".speaking-preview audio", { timeout: 10000 });
    await page.click("[data-save-speaking]");
    await page.waitForSelector(".saved-speaking-audio", { timeout: 10000 });

    const transcript = "Independent bookstores help readers discover unfamiliar writers and discuss ideas with their local community.";
    await page.fill("#speakingTranscript", transcript);
    await page.click("[data-save-speaking-transcript]");
    await page.waitForSelector(".speaking-analysis");
    await page.selectOption("#speakingReviewContent", "3");
    await page.selectOption("#speakingReviewCoherence", "3");
    await page.selectOption("#speakingReviewFluency", "2");
    await page.selectOption("#speakingReviewChunk", "2");
    await page.selectOption("#speakingReviewGrammar", "3");
    await page.fill("#speakingReviewNote", "The main idea was complete, but one transition paused.");
    await page.fill("#speakingStuckExpression", "widen a reader's attention");
    await page.click("[data-save-speaking-review]");
    await page.click("[data-save-speaking-stuck]");
    await page.screenshot({ path: path.join(root, "artifacts", "speaking-desktop.png"), fullPage: true });

    const beforeDelete = execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      "a=c.execute(\"SELECT id, audio_filename, transcript_text, self_review_json FROM speaking_attempts WHERE status != 'deleted'\").fetchone()",
      "print(a[0]); print(a[1]); print(a[2]); print(a[3])",
      "print('links', c.execute(\"SELECT COUNT(*) FROM speaking_review_links\").fetchone()[0])",
      "print('seconds', c.execute(\"SELECT value FROM daily_learning_metrics WHERE metric='speaking_seconds'\").fetchone()[0])",
    ].join("; ")], {
      cwd: root,
      env: { ...process.env, LANGUAGE_COACH_DB_PATH: database },
    }).toString();
    if (!beforeDelete.includes(transcript)) failures.push("manual transcript was not persisted");
    if (!beforeDelete.includes("The main idea was complete")) failures.push("structured self review was not persisted");
    if (!beforeDelete.includes("links 1")) failures.push(`stuck expression was not linked to review: ${beforeDelete}`);
    if (!/seconds [1-9]/.test(beforeDelete)) failures.push(`speaking time was not counted: ${beforeDelete}`);
    const audioFiles = fs.existsSync(audioDirectory) ? fs.readdirSync(audioDirectory) : [];
    if (audioFiles.length !== 1 || fs.statSync(path.join(audioDirectory, audioFiles[0])).size < 1) failures.push("local audio file was not persisted");

    page.once("dialog", dialog => dialog.accept());
    await page.click("[data-delete-speaking]");
    await page.waitForFunction(() => !document.querySelector(".saved-speaking-audio"));
    const afterDelete = execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      "print(c.execute(\"SELECT status FROM speaking_attempts ORDER BY id DESC LIMIT 1\").fetchone()[0])",
    ].join("; ")], { env: { ...process.env, LANGUAGE_COACH_DB_PATH: database } }).toString();
    if (!afterDelete.includes("deleted")) failures.push("speaking attempt was not soft deleted");
    if (fs.existsSync(audioDirectory) && fs.readdirSync(audioDirectory).length) failures.push("deleted audio remained on disk");
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  console.log("local speaking desktop E2E passed");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
