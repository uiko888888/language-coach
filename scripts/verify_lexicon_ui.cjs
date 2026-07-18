const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = 8767;
const baseUrl = `http://127.0.0.1:${port}`;

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/version`);
      if (response.ok) return response.json();
    } catch (_error) {
      // The temporary server is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error("Temporary Language Coach server did not start");
}

async function run() {
  const server = spawn("python", ["backend/server.py", String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const failures = [];
  let browser;
  try {
    const version = await waitForServer();
    if (version.app_version !== "0.8.0-alpha.23.0.2" || version.database_schema_version !== 8) {
      failures.push(`unexpected runtime version: ${JSON.stringify(version)}`);
    }
    const lexicalPayload = await fetch(`${baseUrl}/api/lexicon/search?q=cast`).then(response => response.json());
    const wordnet = lexicalPayload.results.find(item => item.type === "wordnet");
    if (!wordnet?.senses?.some(sense => sense.definition_translations?.some(Boolean))) failures.push("cast has no Chinese sense translation");
    if (!wordnet?.senses?.some(sense => sense.examples?.length && sense.example_translations?.some(Boolean))) failures.push("cast has no bilingual sense example");
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
    await page.goto(`${baseUrl}/?view=lexicon&q=cast`, { waitUntil: "networkidle" });
    if (await page.locator("#assistantDialog[open]").count()) await page.click("#closeAssistantBtn");
    if (await page.locator("#profileEditor[open]").count()) await page.click("#cancelProfileDialogBtn");
    await page.waitForSelector("#view-lexicon.active");
    const sidebarPosition = await page.locator(".sidebar").evaluate(element => getComputedStyle(element).position);
    if (sidebarPosition !== "fixed") failures.push(`sidebar is not fixed: ${sidebarPosition}`);
    const columns = await page.locator(".lexicon-layout").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (columns.split(" ").length < 2) failures.push(`lexicon layout is not split: ${columns}`);
    if (await page.locator(".dictionary-section-nav button").count() < 2) failures.push("section navigation is missing");
    if (await page.locator(".external-dictionaries a").count() < 4) failures.push("external dictionary links are incomplete");
    if (await page.locator('[data-voice="en-GB"]').count() < 1) failures.push("UK speech control is missing");
    if (await page.locator('[data-voice="en-US"]').count() < 1) failures.push("US speech control is missing");
    if (await page.locator(".sense-meaning").count() < 1) failures.push("Chinese sense meanings are missing");
    if (await page.locator(".sense-examples .example-zh").count() < 1) failures.push("Chinese example translation is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "lexicon-cast-desktop.png"), fullPage: true });
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  process.stdout.write("Lexicon bilingual desktop workflow passed on schema 8.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
