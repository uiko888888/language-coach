const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = 8877;
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
  let serverError = "";
  server.stderr.on("data", chunk => { serverError += chunk.toString(); });
  const failures = [];
  let browser;
  try {
    let version;
    try {
      version = await waitForServer();
    } catch (error) {
      throw new Error(`${error.message}${serverError ? `\nBackend stderr:\n${serverError}` : ""}`);
    }
    if (version.app_version !== "0.8.0-alpha.25.18" || version.database_schema_version !== 24) {
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
    if (await page.locator("#compatibilityBanner").isVisible()) failures.push("frontend/backend compatibility warning is visible");
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
    if (await page.locator("#lexicalComparisonCatalog > button").count() !== 200) failures.push("comparison catalog does not expose all 200 groups");
    const catalogOverflow = await page.locator("#lexicalComparisonCatalog").evaluate(element => element.scrollHeight > element.clientHeight);
    if (!catalogOverflow) failures.push("comparison catalog is not scroll bounded");
    await page.click('[data-comparison-filter="lookalike"]');
    if (await page.locator("#lexicalComparisonCatalog > button").count() !== 44) failures.push("lookalike filter does not expose 44 groups");
    await page.click('[data-comparison-filter="ielts"]');
    if (await page.locator("#lexicalComparisonCatalog > button").count() !== 95) failures.push("IELTS filter does not expose 95 groups");
    await page.click('[data-comparison-filter="lookalike"]');
    await page.click('[data-search-query="compliment, complement"]');
    await page.waitForSelector(".comparison-grid");
    if (await page.locator(".comparison-term-card").count() !== 2) failures.push("lookalike comparison does not show two term cards");
    if (!await page.locator(".comparison-header").getByText("拼写形近", { exact: true }).count()) failures.push("lookalike comparison label is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "lexicon-compliment-complement-desktop.png"), fullPage: true });
    await page.click('[data-comparison-filter="all"]');
    await page.click('[data-search-query="accurate, precise, exact"]');
    await page.waitForFunction(() => document.querySelector(".comparison-header h2")?.textContent.includes("accurate / precise"));
    if (!await page.locator(".comparison-header").getByText("候选组 · 待核对", { exact: true }).count()) failures.push("candidate review status is missing");
    await page.click('[data-search-query="compose, comprise, constitute, consist of"]');
    await page.waitForFunction(() => document.querySelector(".comparison-header h2")?.textContent.includes("compose / comprise"));
    if (await page.locator(".comparison-term-card").count() !== 4) failures.push("composition comparison does not show four term cards");
    if (!await page.locator(".comparison-header").getByText("人工整理基础组", { exact: true }).count()) failures.push("curated comparison label is missing");
    if (await page.locator(".comparison-patterns button").count() < 8) failures.push("curated syntax and collocations are incomplete");
    if (!await page.locator(".comparison-memory-rule").getByText(/整体 comprises/).count()) failures.push("whole-part memory rule is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "lexicon-compose-comprise-desktop.png"), fullPage: true });
    const phraseCatalog = await fetch(`${baseUrl}/api/lexicon/academic-phrases?category=evidence&exam=IELTS`).then(response => response.json());
    if (phraseCatalog.count !== 10 || phraseCatalog.categories?.length !== 10) failures.push("academic phrase catalog filters are incomplete");
    await page.goto(`${baseUrl}/?view=lexicon&q=provide%20evidence%20for`, { waitUntil: "networkidle" });
    await page.waitForSelector(".academic-phrase-summary");
    if (!await page.locator("#lexiconDetail").getByText("为……提供证据", { exact: true }).count()) failures.push("academic phrase Chinese meaning is missing");
    if (!await page.locator("#lexiconDetail").getByText("provide evidence for + noun", { exact: true }).count()) failures.push("academic phrase grammar frame is missing");
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith("/api/cards") && response.request().method() === "POST"),
      page.click('[data-save-lookup="provide evidence for"]'),
    ]);
    const savedPhraseCards = await fetch(`${baseUrl}/api/cards`).then(response => response.json());
    const savedAcademicPhrase = savedPhraseCards.cards?.find(card => card.term === "provide evidence for");
    if (!savedAcademicPhrase || savedAcademicPhrase.kind !== "phrase" || !savedAcademicPhrase.meaning_zh || !savedAcademicPhrase.concept_en || !savedAcademicPhrase.grammar_frame) failures.push("academic phrase did not save rich card metadata");
    const phraseReviews = await fetch(`${baseUrl}/api/reviews?kind=phrase&limit=100`).then(response => response.json());
    if (!phraseReviews.items?.some(item => item.item_id === savedAcademicPhrase?.id)) failures.push("academic phrase did not enter the phrase review queue");
    const phraseTraining = await fetch(`${baseUrl}/api/academic-phrase-training?q=provide%20evidence%20for&limit=1`).then(response => response.json());
    if (phraseTraining.count !== 3 || !phraseTraining.items.some(item => item.task_type === "cloze")) failures.push("academic phrase active training tasks are incomplete");
    await page.click('[data-start-academic-training="provide evidence for"]');
    await page.waitForSelector("#academicTrainingResponse");
    await page.fill("#academicTrainingResponse", "provide evidence");
    await page.click('[data-submit-academic-training]');
    await page.waitForSelector("#academicPhrasePractice .output-feedback");
    if (!await page.locator("#academicPhrasePractice").getByText("需要复习", { exact: true }).count()) failures.push("academic phrase active training feedback is missing");
    await page.screenshot({ path: path.join(root, "artifacts", "academic-phrase-desktop.png"), fullPage: true });
    const training = await fetch(`${baseUrl}/api/lexicon/comparison-training?topic=charts&task_type=choice&limit=100`).then(response => response.json());
    const correctionTraining = await fetch(`${baseUrl}/api/lexicon/comparison-training?task_type=correction&limit=100`).then(response => response.json());
    if (correctionTraining.quality?.reviewed !== 100 || correctionTraining.quality?.published !== 68 || correctionTraining.quality?.rejected !== 32) failures.push("comparison correction quality gate is not active");
    const firstTask = training.items.find(item => item.task_id.endsWith(":choice:amount"));
    if ("answer" in firstTask) failures.push("comparison training queue leaks the correct answer");
    const wrongOption = "number";
    await page.click('[data-view="cards"]');
    await page.waitForSelector("#view-cards.active");
    await page.click('[data-review-mode="comparison"]');
    await page.waitForSelector("#comparisonTrainingPane:not([hidden])");
    await Promise.all([
      page.waitForResponse(response => response.url().includes("/api/lexicon/comparison-training?topic=charts")),
      page.locator("#comparisonTrainingTopic").selectOption("charts"),
    ]);
    await page.locator(`[data-select-comparison-task="${firstTask.task_id}"]`).click();
    if (await page.locator("#comparisonTrainingSummary strong").count() !== 4) failures.push("comparison training summary is incomplete");
    const trainingColumns = await page.locator(".comparison-training-workspace").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (trainingColumns.split(" ").length < 2) failures.push(`comparison training layout is not split: ${trainingColumns}`);
    await page.locator("[data-comparison-option]").evaluateAll((buttons, answer) => buttons.find(button => button.dataset.comparisonOption === answer)?.click(), wrongOption);
    await page.click("#submitComparisonTrainingBtn");
    await page.waitForSelector(".comparison-training-result.wrong");
    if (!await page.locator(".comparison-training-result").getByText("已加入 FSRS", { exact: true }).count()) failures.push("wrong boundary did not enter FSRS");
    const trainingOverflow = await page.locator(".comparison-training-workspace").evaluate(element => element.scrollWidth > element.clientWidth + 1);
    if (trainingOverflow) failures.push("comparison training workspace overflows horizontally");
    await page.screenshot({ path: path.join(root, "artifacts", "comparison-training-desktop.png"), fullPage: true });
    await page.click('[data-view="profile"]');
    await page.waitForSelector("#view-profile.active");
    const profileColumns = await page.locator(".user-center-layout").evaluate(element => getComputedStyle(element).gridTemplateColumns);
    if (profileColumns.split(" ").length < 2) failures.push(`profile layout is not split: ${profileColumns}`);
    if (await page.locator("#comparisonReviewSummary strong").count() !== 4) failures.push("comparison review summary is incomplete");
    if (await page.locator("#comparisonReviewList .comparison-review-row").count() < 1) failures.push("comparison review queue is empty");
    const firstReview = page.locator("#comparisonReviewList .comparison-review-row").first();
    await firstReview.locator("[data-review-workflow-status]").selectOption("reviewing");
    await firstReview.locator("[data-review-priority]").fill("99");
    await firstReview.locator("[data-save-comparison-review]").click();
    await page.waitForFunction(() => [...document.querySelectorAll("#comparisonReviewList .badge")].some(element => element.textContent.includes("审核中")));
    const reviewOverflow = await page.locator(".comparison-review-manager").evaluate(element => element.scrollWidth > element.clientWidth + 1);
    if (reviewOverflow) failures.push("comparison review manager overflows horizontally");
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
  process.stdout.write("Lexicon private/open bilingual desktop workflow passed on schema 24.\n");
}

run().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
