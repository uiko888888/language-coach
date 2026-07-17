const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

async function run() {
  const baseUrl = process.argv[2] || "http://127.0.0.1:8766/";
  const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const failures = [];
  page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
  page.on("response", response => {
    if (response.status() >= 400 && !response.url().endsWith("/favicon.ico")) {
      failures.push(`response ${response.status()}: ${response.url()}`);
    }
  });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.click('[data-view="quiz"]');
  await page.waitForSelector("[data-quiz-card]");
  const columns = await page.locator(".quiz-workspace").evaluate(element => getComputedStyle(element).gridTemplateColumns);
  if (columns.split(" ").length < 2) failures.push(`desktop layout is not split: ${columns}`);

  await page.selectOption("#globalStyle", "KAOYAN");
  await page.waitForFunction(() => document.querySelector("#toast")?.textContent.includes("KAOYAN 来源"));
  await page.waitForFunction(() => document.querySelectorAll("#quizPracticeType option").length >= 5);
  await page.waitForFunction(() => document.querySelector("#examResourceList")?.textContent.includes("CHSI"));
  if ((await page.locator("#quizPracticeType option").count()) < 5) failures.push("KAOYAN specialties are missing");
  if (!(await page.locator('#quizScope option[value="full-paper"]').isDisabled())) failures.push("KAOYAN full-paper option should be disabled");
  if (!(await page.locator("#examResourceList").textContent()).includes("CHSI")) failures.push("KAOYAN official resource is missing");
  await page.selectOption("#globalStyle", "IELTS");
  await page.waitForFunction(() => document.querySelector("#toast")?.textContent.includes("IELTS 来源"));
  await page.waitForFunction(() => document.querySelector('#quizPracticeType option[value="tfng"]'));
  await page.waitForFunction(() => document.querySelector("#examResourceList")?.textContent.includes("British Council"));

  await page.selectOption("#quizScope", "full-paper");
  if (!(await page.locator("#generateFullPaperBtn").isVisible())) failures.push("full-paper action is not visible");
  if ((await page.locator("#examResourceList li").count()) < 1) failures.push("official exam resource catalog is empty");
  await page.selectOption("#quizScope", "specialty");

  await page.selectOption("#quizSessionMode", "mock");
  const firstOption = page.locator("[data-select-quiz-answer]").first();
  await firstOption.click();
  if (!(await firstOption.evaluate(element => element.classList.contains("selected")))) {
    failures.push("mock answer was not retained as selected");
  }
  if (await page.locator(".answer-explanation").count()) {
    failures.push("mock mode exposed an explanation before submission");
  }
  page.once("dialog", dialog => dialog.accept());
  const [submitResponse] = await Promise.all([
    page.waitForResponse(response => response.url().includes("/api/practice-sessions") && response.request().method() === "POST"),
    page.click("#finishQuizSessionBtn"),
  ]);
  const submitBody = await submitResponse.text();
  if (!submitResponse.ok()) failures.push(`session submit failed (${submitResponse.status()}): ${submitBody}`);
  await page.waitForTimeout(500);
  const resultHidden = await page.locator("#quizSessionResult").getAttribute("hidden");
  if (resultHidden !== null) failures.push(`session result stayed hidden after submit: ${submitBody}`);
  const resultText = await page.locator("#quizSessionResult").innerText();
  if (!resultText.includes("正确率") || !resultText.includes("需要复盘")) {
    failures.push("session result is missing score or diagnosis");
  }
  await page.screenshot({ path: path.resolve("artifacts/practice-session-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  await page.click('[data-view="quiz"]');
  await page.waitForSelector("[data-quiz-card]");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  if (overflow) failures.push("mobile page has horizontal overflow");
  await page.screenshot({ path: path.resolve("artifacts/practice-session-mobile.png"), fullPage: true });

  await browser.close();
  if (failures.length) {
    console.error(JSON.stringify({ ok: false, failures }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ ok: true, desktopColumns: columns, result: resultText.split("\n").slice(0, 12) }, null, 2));
}

run().catch(error => {
  console.error(error);
  process.exit(1);
});
