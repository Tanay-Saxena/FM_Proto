import { expect, test } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

// Completion features end to end through the real UI: review a receipt, owner sees it, owner refunds,
// photo upload shows to guests, menu reordering persists, table transfer, bill split calculator.
const LUNCH = () => {
  const ist = new Date(Date.now() + 5.5 * 3600e3);
  return new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate(), 13, 0) - 5.5 * 3600e3).toISOString();
};

test("review → owner sees it → refund; photo upload; reorder; split; transfer", async ({ page, browser }) => {
  await page.addInitScript((t) => localStorage.setItem("fm:demo-time", t), LUNCH());
  const owner = await browser.newContext();
  await owner.request.post("/api/v1/auth/login", { data: { email: "owner@spiceroute.demo", password: "demo1234" } });
  const me = await (await owner.request.get("/api/v1/auth/me")).json();
  const rid = me.memberships[0].restaurant_id;
  const label = `X${Date.now() % 100000}`;
  const t = await (await owner.request.post(`/api/v1/restaurants/${rid}/tables`, { data: { label, zone: "Garden" } })).json();

  // guest: order + split calculator + pay
  await page.goto(`/t/${t.qr_url.split("/").pop()}`);
  await page.waitForURL("**/r/spice-route");
  await page.getByRole("button", { name: /Add Butter Naan to order/ }).click();
  await page.getByRole("button", { name: /Your order · 1 item/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("Review Guest");
  await page.getByLabel("Mobile number").fill("+919876543211");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Send to kitchen" }).click();
  await expect(page.getByText("Order A")).toBeVisible();
  await page.getByRole("button", { name: "More people" }).click();
  await page.getByRole("button", { name: "More people" }).click();
  await expect(page.getByText(/each/).first()).toBeVisible();
  await page.getByRole("button", { name: "Request bill" }).click();
  await page.getByRole("button", { name: /^Pay ₹/ }).click();

  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await page.getByRole("link", { name: "Open your receipt" }).click();

  // review on the receipt
  await expect(page.getByText("How was your visit?")).toBeVisible();
  await page.getByRole("radio", { name: "5 stars" }).click();
  await page.getByLabel("Comment").fill("E2E: lovely naan");
  await page.getByRole("button", { name: "Send review" }).click();
  await expect(page.getByText("Thanks for rating your visit")).toBeVisible();
  const receiptUrl = page.url();

  // owner (desktop) in the dashboard
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const o = await ctx.newPage();
  await o.goto("/admin/login");
  await o.getByLabel("Email").fill("owner@spiceroute.demo");
  await o.getByLabel("Password").fill("demo1234");
  await o.getByRole("button", { name: "Sign in", exact: true }).click();
  await o.waitForURL("**/admin");
  await o.goto("/admin/reviews");
  await expect(o.getByText("E2E: lovely naan")).toBeVisible();

  await o.goto("/admin/payments");
  const row = o.locator("tr", { hasText: `Table ${label}` });
  await row.getByRole("button", { name: "Refund…" }).click();
  await o.getByLabel("Reason").fill("E2E refund");
  await o.getByRole("button", { name: "Refund in full" }).click();
  await expect(row.getByText("refunded", { exact: true }).first()).toBeVisible();
  await page.goto(receiptUrl);
  await expect(page.getByText(/refunded in full/)).toBeVisible();

  // photo upload shows on the guest menu
  const img = path.join(__dirname, "..", "test-results", "dish.png");
  fs.mkdirSync(path.dirname(img), { recursive: true });
  fs.writeFileSync(img, Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8BQz0AEYBxVSF+FABJADveWkH6oAAAAAElFTkSuQmCC", "base64"));
  await o.goto("/admin/menu");
  await o.getByRole("button", { name: "Butter Naan" }).first().click();
  await o.getByLabel("Upload dish photo").setInputFiles(img);
  await expect(o.getByText("Photo saved")).toBeVisible();
  await page.goto("/r/spice-route");
  await expect(page.locator('img[src^="/api/v1/media/dishes/"]').first()).toBeVisible({ timeout: 15_000 });
  const src = await page.locator('img[src^="/api/v1/media/dishes/"]').first().getAttribute("src");
  expect((await page.request.get(src!)).headers()["content-type"]).toBe("image/jpeg");
});

test("owner: reorder categories persists; move a party to another table", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const o = await ctx.newPage();
  await o.goto("/admin/login");
  await o.getByLabel("Email").fill("owner@spiceroute.demo");
  await o.getByLabel("Password").fill("demo1234");
  await o.getByRole("button", { name: "Sign in", exact: true }).click();
  await o.waitForURL("**/admin");

  await o.goto("/admin/menu");
  const heads = () => o.locator("section h2").allInnerTexts();
  await expect(o.getByText("Starters").first()).toBeVisible();
  const before = await heads();
  await o.getByRole("button", { name: `Move ${before[0]} down` }).click();
  await expect.poll(heads).not.toEqual(before);
  const after = await heads();
  expect(after[1]).toBe(before[0]);
  await o.reload();
  await expect(o.getByText(before[0]).first()).toBeVisible();
  expect((await heads())[1]).toBe(before[0]); // persisted
  await o.getByRole("button", { name: `Move ${before[0]} up` }).click(); // restore
  await expect.poll(async () => (await heads())[0]).toBe(before[0]);

  // a fresh party, then move it
  const me = await (await ctx.request.get("/api/v1/auth/me")).json();
  const rid = me.memberships[0].restaurant_id;
  const a = `M${Date.now() % 100000}`, b = `N${Date.now() % 100000}`;
  const ta = await (await ctx.request.post(`/api/v1/restaurants/${rid}/tables`, { data: { label: a } })).json();
  await ctx.request.post(`/api/v1/restaurants/${rid}/tables`, { data: { label: b } });
  const guest = await browser.newContext();
  expect((await guest.request.post(`/api/v1/qr/${ta.qr_url.split("/").pop()}/session`)).ok()).toBeTruthy();
  await o.goto("/admin/orders");
  const li = o.locator("li", { hasText: `Table ${a}` });
  await li.getByRole("button", { name: /Move to another table/ }).click();
  await o.getByLabel("New table").selectOption({ label: `Table ${b}` });
  await o.getByRole("button", { name: "Move party" }).click();
  await expect(o.locator("li", { hasText: `Table ${b}` })).toBeVisible();
  await expect(o.locator("li", { hasText: `Table ${a}` })).toHaveCount(0);
});
