const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const baseUrl = process.env.GRAFANA_URL || "http://127.0.0.1:3000";
const username = process.env.GRAFANA_USER;
const password = process.env.GRAFANA_PASSWORD;
const outputDir = process.env.OUTPUT_DIR ||
  path.resolve(__dirname, "../figures/screenshots");

if (!username || !password) {
  throw new Error("GRAFANA_USER and GRAFANA_PASSWORD are required");
}

const dashboards = [
  {
    name: "grafana-operateur",
    path: "/d/printer-operator/imprimante-operateur",
    range: "now-6h",
  },
  {
    name: "grafana-maintenance",
    path: "/d/printer-maintenance/imprimante-maintenance",
    range: "now-6h",
  },
  {
    name: "grafana-direction",
    path: "/d/printer-management/imprimante-direction",
    range: "now-24h",
  },
];

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
    args: ["--disable-dev-shm-usage", "--hide-scrollbars"],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    locale: "fr-FR",
    timezoneId: "Africa/Casablanca",
    colorScheme: "dark",
  });
  const page = await context.newPage();

  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator('input[name="user"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 20_000,
    }),
    page.locator('button[type="submit"]').click(),
  ]);

  for (const dashboard of dashboards) {
    const url = `${baseUrl}${dashboard.path}` +
      `?orgId=1&from=${dashboard.range}&to=now&timezone=browser`;
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForTimeout(8_000);
    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation-duration: 0s !important;
          transition-duration: 0s !important;
        }
      `,
    });

    const noData = await page.getByText("No data", { exact: true }).count();
    const loading = await page.getByText("Loading", { exact: false }).count();
    if (noData || loading) {
      throw new Error(
        `${dashboard.name}: noData=${noData}, loading=${loading}`,
      );
    }

    const file = path.join(outputDir, `${dashboard.name}.png`);
    await page.screenshot({
      path: file,
      fullPage: true,
      animations: "disabled",
    });
    console.log(`${dashboard.name}: ${file}`);
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
