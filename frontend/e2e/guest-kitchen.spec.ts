import { expect, test } from "@playwright/test";

// Scenario E through the real UI: guest orders (A), kitchen starts cooking, guest adds a dessert (B),
// kitchen sees a distinct add-on ticket, bill includes both, guest pays (simulated), receipt opens.
test("order, add-on, kitchen, pay, receipt", async ({ page, browser }) => {
  const OUT = process.env.SHOT_DIR ?? "test-results/shots";
  // 1:00 PM IST today (inside kitchen hours and the lunch window)
  await page.addInitScript(() => {
    const now = new Date(); const ist = new Date(now.getTime() + 5.5 * 3600e3);
    const d = new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate(), 13, 0) - 5.5 * 3600e3);
    localStorage.setItem("fm:demo-time", d.toISOString());
  });
  // fresh table per run, created by the owner through the API (own cookie jar, so the guest stays anonymous)
  const owner = await browser.newContext();
  await owner.request.post("/api/v1/auth/login", { data: { email: "owner@spiceroute.demo", password: "demo1234" } });
  const me = await (await owner.request.get("/api/v1/auth/me")).json();
  const label = `E${Date.now() % 100000}`;
  const created = await (await owner.request.post(`/api/v1/restaurants/${me.memberships[0].restaurant_id}/tables`, { data: { label, zone: "Terrace" } })).json();
  const table = { qr_token: created.qr_url.split("/").pop() };
  await page.goto(`/t/${table.qr_token}`);
  await page.waitForURL("**/r/spice-route");
  await expect(page.getByRole("banner").getByText(`Table ${label} · Terrace`)).toBeVisible();

  await page.getByRole("button", { name: "Add Paneer Tikka to order" }).click();
  await page.getByRole("button", { name: /Add Butter Naan to order/ }).click();
  await page.getByRole("button", { name: /Your order · 2 items/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("E2E Guest");
  await page.getByLabel("Mobile number").fill("+919876543210");
  await page.getByRole("checkbox").check();
  await page.screenshot({ path: `${OUT}/10-cart.png` });
  await page.getByRole("button", { name: "Send to kitchen" }).click();
  await expect(page.getByText("Order A")).toBeVisible();
  await page.screenshot({ path: `${OUT}/11-table-order-a.png` });

  // kitchen (separate context, signed in as kitchen staff)
  const kctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const k = await kctx.newPage();
  await k.goto("/admin/login?next=/kitchen");
  await k.getByLabel("Email").fill("kitchen@spiceroute.demo");
  await k.getByLabel("Password").fill("demo1234");
  await k.getByRole("button", { name: "Sign in", exact: true }).click();
  await k.waitForURL("**/kitchen");
  const ticketA = k.locator("li", { hasText: `T${label}` }).first();
  await expect(ticketA).toContainText("Paneer Tikka");
  await ticketA.getByRole("button", { name: "Accept" }).click();
  await k.locator("li", { hasText: `T${label}` }).first().getByRole("button", { name: "Start cooking" }).click();

  // add-on dessert while A is cooking
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("button", { name: "Add Gulab Jamun to order" }).click();
  await page.getByRole("button", { name: /Add-on · 1 item/ }).click();
  await expect(page.getByRole("button", { name: "Send add-on to kitchen" })).toBeVisible();
  await page.getByRole("button", { name: "Send add-on to kitchen" }).click();
  await expect(page.getByText("Add-on B")).toBeVisible();

  await expect(k.locator("li", { hasText: `T${label}` }).filter({ hasText: "ADD-ON B" })).toBeVisible({ timeout: 10_000 });
  await k.screenshot({ path: `${OUT}/12-kitchen.png` });
  await expect(k.locator("li", { hasText: `T${label}` }).filter({ hasText: "Paneer Tikka" })).toContainText("Mark ready"); // A unchanged, still cooking

  // bill + pay
  await page.getByRole("button", { name: "Request bill" }).click();
  await page.screenshot({ path: `${OUT}/13-bill.png`, fullPage: true });
  await page.getByRole("button", { name: /^Pay ₹/ }).click();
  await page.getByRole("button", { name: "Simulate failure" }).click();
  await expect(page.getByText(/didn.t go through/)).toBeVisible();
  await page.getByRole("button", { name: /^Pay ₹/ }).click(); // retry creates a fresh payment
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page.getByText("Payment confirmed.")).toBeVisible();
  await page.getByRole("link", { name: "Open your receipt" }).click();
  await expect(page.getByText("Total paid")).toBeVisible();
  await expect(page.getByText("Gulab Jamun")).toBeVisible();
  await page.screenshot({ path: `${OUT}/14-receipt.png`, fullPage: true });
});

test("owner dashboard pages render without errors", async ({ browser }) => {
  const OUT = process.env.SHOT_DIR ?? "test-results/shots";
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errors: string[] = [];
  p.on("pageerror", (e) => { errors.push(e.message); console.log("PAGEERROR", p.url(), e.message); });
  await p.goto("/admin/login");
  await p.getByLabel("Email").fill("owner@spiceroute.demo");
  await p.getByLabel("Password").fill("demo1234");
  await p.getByRole("button", { name: "Sign in", exact: true }).click();
  await p.waitForURL("**/admin");
  for (const [path, text] of [["/admin", "Tables right now"], ["/admin/orders", "Tickets"], ["/admin/menu", "Starters"], ["/admin/schedules", "Opening hours"], ["/admin/promotions", "Active rules"], ["/admin/tables", "QR codes"], ["/admin/imports", "Drop a menu"], ["/admin/payments", "Receipt messages"], ["/admin/analytics", "Orders per day"], ["/admin/reviews", "What guests said"], ["/admin/settings", "Look & feel"], ["/admin/team", "What each role can do"]] as const) {
    await p.goto(path);
    await expect(p.getByText(text).first()).toBeVisible({ timeout: 15_000 });
    await p.screenshot({ path: `${OUT}/20-${path.replace(/\W+/g, "-")}.png` });
  }
  expect(errors).toEqual([]);
});
