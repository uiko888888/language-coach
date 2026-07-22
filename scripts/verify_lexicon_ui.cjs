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
    if (version.app_version !== "0.8.0-alpha.25.6" || version.database_schema_version !== 21) {
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
    if (await page.locator(".private-dictionary-entry").count() < 1) failures.push("private dictionary entry is missing");
    if (!await page.locator("#lexiconDetail").getByText("仅本机", { exact: true }).count()) failures.push("private local-only label is missing");
    await page.click('button[data-lexical-type="wordnet"]');
    if (await page.locator(".dictionary-section-nav button").count() < 2) failures.push("section navigation is missing");
    if (await page.locator(".external-dictionaries a").count() < 4) failures.push("external dictionary links are incomplete");
    if (await page.locator('[data-voice="en-GB"]').count() < 1) failures.push("UK speech control is missing");
    if (await page.locator('[data-voice="en-US"]').count() < 1) failures.push("US speech control is missing");
    if (await page.locator(".sense-meaning").count() < 1) failures.push("Chinese sense meanings are missing");
    if (await page.locator(".sense-examples .example-zh").count() < 1) failures.push("Chinese example translation is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "lexicon-cast-desktop.png"), fullPage: true });
    await page.locator(".lexical-comparison-library summary").click();
    if (await page.locator("#lexicalComparisonCatalog > button").count() !== 31) failures.push("comparison catalog does not expose all 31 groups");
    const catalogOverflow = await page.locator("#lexicalComparisonCatalog").evaluate(element => element.scrollHeight > element.clientHeight);
    if (!catalogOverflow) failures.push("comparison catalog is not scroll bounded");
    await page.click('[data-search-query="compose, comprise, constitute, consist of"]');
    await page.waitForSelector(".comparison-grid");
    if (await page.locator(".comparison-term-card").count() !== 4) failures.push("composition comparison does not show four term cards");
    if (!await page.locator(".comparison-header").getByText("人工整理基础组", { exact: true }).count()) failures.push("curated comparison label is missing");
    if (await page.locator(".comparison-patterns button").count() < 8) failures.push("curated syntax and collocations are incomplete");
    if (!await page.locator(".comparison-memory-rule").getByText(/整体 comprises/).count()) failures.push("whole-part memory rule is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "lexicon-compose-comprise-desktop.png"), fullPage: true });
    await page.click('[data-view="profile"]');
    await page.waitForSelector("#view-profile.active");
    const profileColumns = await page.locator(".user-center-layout").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (profileColumns.split(" ").length < 2) failures.push(`profile layout is not split: ${profileColumns}`);
    if (await page.locator("#privateDictionaryList .private-dictionary-row").count() < 4) failures.push("registered private dictionary sources are missing");
    if (!await page.locator("#stardictImportForm").isVisible()) failures.push("StarDict import form is missing");
    const managerOverflow = await page.locator(".private-dictionary-manager").evaluate(element => element.scrollWidth > element.clientWidth + 1);
    if (managerOverflow) failures.push("private dictionary manager overflows horizontally");
    await page.screenshot({ path: path.join(root, "artifacts", "private-dictionaries-desktop.png"), fullPage: true });
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  if (failures.length) throw new Error(failures.join("\n"));
  process.stdout.write("Lexicon private/open bilingual desktop workflow passed on schema 21.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
