const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const baseUrl = process.env.NODE_RED_URL || "http://127.0.0.1:1880";
const username = process.env.NODE_RED_USER;
const password = process.env.NODE_RED_PASSWORD;
const outputDir = process.env.OUTPUT_DIR ||
  path.resolve(__dirname, "../figures/screenshots");

if (!username || !password) {
  throw new Error("NODE_RED_USER and NODE_RED_PASSWORD are required");
}

const views = [
  { tab: "01 - Télémétrie", file: "node-red-telemetrie.png" },
  { tab: "04 - Supervision", file: "node-red-supervision.png" },
];

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
    args: ["--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1000 },
    locale: "fr-FR",
    timezoneId: "Africa/Casablanca",
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.locator("#node-dialog-login-username").fill(username);
  await page.locator("#node-dialog-login-password").fill(password);
  await page.locator("#node-dialog-login-submit").click();
  await page.locator(".red-ui-tab-label").first()
    .waitFor({ state: "visible", timeout: 20_000 });

  // Node-RED shows this once per fresh browser profile and keeps a shade over
  // the editor until one of the choices is made.
  const declineUpdates = page.getByText("No, do not enable notifications", {
    exact: true,
  });
  if (await declineUpdates.count()) {
    await declineUpdates.click();
  }

  const welcomeTour = page.getByText("Welcome to Node-RED 4.1!", {
    exact: true,
  });
  if (await welcomeTour.count()) {
    await welcomeTour
      .locator("xpath=ancestor::div[contains(@class,'red-ui-popover-content')]")
      .locator("button")
      .first()
      .click({ force: true });
  }

  // The tour state is stored outside the ephemeral Playwright profile and can
  // reopen on another step even after its popover is closed. It is irrelevant
  // to the flow evidence, so keep it out of deterministic screenshots.
  await page.addStyleTag({
    content: `
      .red-ui-tourGuide-shade,
      .red-ui-popover,
      .red-ui-shade { display: none !important; }
    `,
  });
  await page.waitForTimeout(2_000);

  for (const view of views) {
    await page.locator(".red-ui-tab-label").filter({ hasText: view.tab })
      .first().click({ force: true });
    await page.waitForTimeout(1_500);
    await page.locator("#red-ui-view-zoom-zero").click();
    await page.waitForTimeout(500);

    const visibleNodes = await page.locator(".red-ui-flow-node:visible").count();
    if (!visibleNodes) {
      throw new Error(`${view.tab}: no flow nodes are visible`);
    }

    const file = path.join(outputDir, view.file);
    await page.screenshot({
      path: file,
      fullPage: true,
      animations: "disabled",
    });
    console.log(`${view.tab}: ${file} (${visibleNodes} nodes)`);
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
