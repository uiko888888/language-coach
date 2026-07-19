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
    if (version.app_version !== "0.8.0-alpha.24.0" || version.database_schema_version !== 14) {
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
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise(resolve => server.once("exit", resolve));
    removeDatabase();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  process.stdout.write("Review desktop workflow passed on isolated schema 14.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
