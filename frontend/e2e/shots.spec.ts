import { test } from "@playwright/test";
const OUT = process.env.SHOT_DIR ?? "test-results/shots";

test("capture key screens", async ({ page, browser }) => {
  await page.goto("/");
  await page.waitForSelector("text=Sit at a sample table");
  await page.screenshot({ path: `${OUT}/01-landing-mobile.png`, fullPage: false });
  await page.goto("/r/spice-route");
  await page.waitForSelector("text=Paneer Tikka");
  await page.screenshot({ path: `${OUT}/02-menu-mobile.png` });
  await page.screenshot({ path: `${OUT}/03-menu-full.png`, fullPage: true });
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const d = await desktop.newPage();
  await d.goto("/r/spice-route");
  await d.waitForSelector("text=Paneer Tikka");
  await d.screenshot({ path: `${OUT}/04-menu-desktop.png` });
  await d.goto("/");
  await d.waitForSelector("text=Sit at a sample table");
  await d.screenshot({ path: `${OUT}/05-landing-desktop.png` });
});
