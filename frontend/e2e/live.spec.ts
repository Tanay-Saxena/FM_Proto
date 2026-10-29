import { expect, test, type Page, type Browser } from "@playwright/test";

const AT = (h: number) => {
  const ist = new Date(Date.now() + 5.5 * 3600e3);
  return new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate(), h, 0) - 5.5 * 3600e3).toISOString();
};
const LUNCH = () => AT(13);
const EVENING = () => AT(19); // the gastropub only opens later in the day
async function signIn(browser: Browser, email: string, next = "/admin") {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`/admin/login?next=${next}`);
  await p.getByLabel("Email").fill(email);
  await p.getByLabel("Password").fill("demo1234");
  await p.getByRole("button", { name: "Sign in", exact: true }).click();
  await p.waitForURL(`**${next}`);
  return { ctx, p };
}

// A brand-new order placed by a guest must appear on the kitchen screen AND the manager's orders page of that
// restaurant without anyone reloading, and the kitchen's action must reach the guest live.
test("new order appears live for kitchen + manager (Copper Tap), and status flows back to the guest", async ({ page, browser }) => {
  await page.addInitScript((t) => localStorage.setItem("fm:demo-time", t), EVENING());
  const owner = { ctx: await browser.newContext() };
  await owner.ctx.request.post("/api/v1/auth/login", { data: { email: "owner@coppertap.demo", password: "demo1234" } });
  const me = await (await owner.ctx.request.get("/api/v1/auth/me")).json();
  const rid = me.memberships[0].restaurant_id;
  const label = `L${Date.now() % 100000}`;
  const t = await (await owner.ctx.request.post(`/api/v1/restaurants/${rid}/tables`, { data: { label, zone: "Patio" } })).json();

  // kitchen + manager are already open and watching BEFORE the guest orders
  const kitchen = await signIn(browser, "kitchen@coppertap.demo", "/kitchen");
  const manager = await signIn(browser, "manager@coppertap.demo", "/admin/orders");
  await expect(kitchen.p.getByText(/Live · updated/)).toBeVisible();
  await expect(kitchen.p.locator("li", { hasText: `T${label}` })).toHaveCount(0);

  await page.goto(`/t/${t.qr_url.split("/").pop()}`);
  await page.waitForURL("**/r/copper-tap");
  const firstAdd = page.getByRole("button", { name: /^Add .* to order$/ }).first();
  await firstAdd.click();
  await page.getByRole("button", { name: /Your order/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("Live Guest");
  await page.getByLabel("Mobile number").fill("+919876543299");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Send to kitchen" }).click();
  await expect(page.getByText("Order A")).toBeVisible();

  // no reload on either screen
  const ticket = kitchen.p.locator("li", { hasText: `T${label}` }).first();
  await expect(ticket).toBeVisible({ timeout: 8_000 });
  await expect(manager.p.getByText(`Table ${label}`).first()).toBeVisible({ timeout: 8_000 });

  await ticket.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByText(/Accepted/).first()).toBeVisible({ timeout: 8_000 });
  await kitchen.p.locator("li", { hasText: `T${label}` }).first().getByRole("button", { name: "Start cooking" }).click();
  await expect(page.getByText(/Being cooked right now/)).toBeVisible({ timeout: 8_000 });
});

// Fails on ANY uncaught error or console.error while exercising every page, sheet and editor.
test("no runtime errors across pages, sheets and editors", async ({ page, browser }) => {
  const errors: string[] = [];
  const watch = (p: Page, tag: string) => {
    p.on("pageerror", (e) => errors.push(`${tag} pageerror: ${e.message}`));
    p.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errors.push(`${tag} console: ${m.text()}`); });
  };
  await page.addInitScript((t) => localStorage.setItem("fm:demo-time", t), LUNCH());
  watch(page, "guest");

  // guest: landing, every restaurant, dish sheet, discover, filters
  await page.goto("/");
  await page.waitForSelector("text=Sit at a sample table");
  for (const slug of ["spice-route", "kettle-crumb", "copper-tap"]) {
    await page.goto(`/r/${slug}`);
    await page.locator("li button[aria-label*='Open details']").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Discover", exact: true }).click();
    await page.getByRole("button", { name: "My table", exact: true }).click();
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page.getByRole("button", { name: /Filters/ }).click();
    await page.keyboard.press("Escape");
  }

  // owner: every admin page, the dish editor for an existing dish and for a new one, category modals
  const o = await signIn(browser, "owner@spiceroute.demo");
  watch(o.p, "owner");
  for (const path of ["/admin", "/admin/orders", "/admin/menu", "/admin/schedules", "/admin/promotions", "/admin/tables", "/admin/imports", "/admin/payments", "/admin/analytics", "/admin/reviews", "/admin/settings", "/admin/team"]) {
    await o.p.goto(path);
    await o.p.waitForTimeout(900); // dashboards poll, so "network idle" never arrives
  }
  await o.p.goto("/admin/menu");
  await o.p.getByRole("button", { name: "Butter Naan" }).first().click();
  await expect(o.p.getByText("Picture")).toBeVisible();
  await o.p.keyboard.press("Escape");
  await o.p.getByRole("button", { name: /Add dish/ }).click();
  await expect(o.p.getByText("Picture")).toBeVisible();
  await o.p.keyboard.press("Escape");
  await o.p.getByRole("button", { name: "Add category" }).click();
  await o.p.keyboard.press("Escape");

  // every role's landing page
  for (const [email, next] of [["kitchen@spiceroute.demo", "/kitchen"], ["manager@kettle.demo", "/admin"], ["staff@spiceroute.demo", "/admin/orders"], ["platform@foodmania.demo", "/admin/platform"]] as const) {
    const r = await signIn(browser, email, next);
    watch(r.p, email);
    await r.p.waitForTimeout(1200);
  }
  expect(errors).toEqual([]);
});
