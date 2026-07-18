const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = 8770;
const baseUrl = `http://127.0.0.1:${port}`;
const database = path.join(root, "artifacts", "article-extraction-e2e.sqlite");

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
    if (version.app_version !== "0.8.0-alpha.23.0.4" || version.database_schema_version !== 10) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const body = [
      "President Donald Trump's obsession with election rules has returned to Congress.",
      "The proposal faces procedural and political obstacles in the Senate.",
    ].join("\n\n");
    const created = await post("/api/articles", {
      title: "Republicans control Congress",
      body,
      level: "B2",
      source: "manual",
    });
    const articleId = created.article.id;
    execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      `c.execute(\"UPDATE articles SET source='The Conversation Politics', author='SoRelle Wyckoff Gaynor', image_caption='The act is stuck between the U.S. House and Senate. J. Scott Applewhite/AP Photo', disclosure='The author reports no relevant financial relationships.', extraction_version='conversation-rules-v2', extraction_confidence=0.98 WHERE id=?\", (${articleId},))`,
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
    await page.click(`[data-select-article="${articleId}"]`);

    const sidebarPosition = await page.locator(".sidebar").evaluate(node => getComputedStyle(node).position);
    if (sidebarPosition !== "fixed") failures.push(`sidebar position is ${sidebarPosition}`);
    const columns = await page.locator("#articlePoolLayout").evaluate(node => getComputedStyle(node).gridTemplateColumns);
    if (!columns || columns.split(" ").length < 2) failures.push(`article workspace is not split: ${columns}`);
    const detailText = await page.locator("#articleDetail").innerText();
    if (detailText.includes("AP Photo") && !detailText.includes("来源信息")) failures.push("caption is not isolated as source metadata");
    if ((await page.locator("#articleDetail .article-detail-body").innerText()).includes("AP Photo")) failures.push("caption leaked into article body");

    await page.locator("#articleDetail .source-metadata summary").click();
    const metadata = await page.locator("#articleDetail .source-metadata").innerText();
    for (const expected of ["SoRelle Wyckoff Gaynor", "J. Scott Applewhite/AP Photo", "conversation-rules-v2", "98%"] ) {
      if (!metadata.includes(expected)) failures.push(`missing source metadata: ${expected}`);
    }
    await page.click(`#articleDetail [data-extraction-feedback="correct"][data-article-id="${articleId}"]`);
    await page.waitForTimeout(200);
    const feedback = execFileSync("python", ["-c", [
      "import os, sqlite3",
      "c=sqlite3.connect(os.environ['LANGUAGE_COACH_DB_PATH'])",
      "print(c.execute(\"SELECT verdict FROM article_extraction_feedback ORDER BY id DESC LIMIT 1\").fetchone()[0])",
    ].join("; ")], { cwd: root, env: { ...process.env, LANGUAGE_COACH_DB_PATH: database } }).toString().trim();
    if (feedback !== "correct") failures.push(`feedback was not stored: ${feedback}`);
    await page.screenshot({ path: path.join(root, "artifacts", "article-extraction-desktop.png"), fullPage: true });
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  console.log("article extraction desktop E2E passed");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
