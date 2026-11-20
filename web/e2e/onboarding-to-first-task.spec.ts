import { expect, test, type Page } from "@playwright/test";

/**
 * The main path, against the real stack (`docker compose up`): a new User registers,
 * sets up an Event, opens their first Vocab Task from Today and completes it.
 */

// Meets the password rules: at least 8 characters, with a digit and a symbol.
const PASSWORD = "e2e-Password-2026!";
// A compact JWT is three base64url parts; its header always starts with `eyJ` (`{"`).
const JWT = /eyJ[\w-]+\.[\w-]+\.[\w-]+/;

test("a new User registers, sets up an Event and completes their first Vocab Task", async ({ page }) => {
  // A fresh User every run, so the test needs no cleanup and can re-run on one stack.
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

  await test.step("register", async () => {
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
  });

  await test.step("no token is readable from the page", async () => {
    await expectNoReadableToken(page);
  });

  await test.step("onboarding", async () => {
    await page.getByLabel("Job interview").check();
    // 12 days out, like the demo. The input's `min` is 3 days after the User's today.
    const min = await page.getByLabel("When is it?").getAttribute("min");
    expect(min).toBeTruthy();
    await page.getByLabel("When is it?").fill(addDays(min!, 9));
    await page.getByRole("button", { name: "Build my Plan" }).click();
    await expect(page).toHaveURL(/\/today$/);
  });

  const taskHref = await test.step("open the first Vocab Task from Today", async () => {
    await expect(page.getByTestId("today-title")).toHaveText("Day 1 of 12");
    // Only Vocab Tasks are open today, but pick by kind so unlocking Listen or Speak can't change the path.
    const firstTask = page.getByTestId("task-link").filter({ hasText: "Vocabulary" }).first();
    await expect(firstTask.getByTestId("task-status")).toHaveText("To do");
    const href = await firstTask.getAttribute("href");
    expect(href).toMatch(/^\/tasks\/[\w-]+$/);
    await firstTask.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.getByTestId("vocab-items").getByRole("listitem").first()).toBeVisible();
    return href!;
  });

  await test.step("Done completes it, and Today shows it completed", async () => {
    await page.getByTestId("task-done").click();
    await expect(page).toHaveURL(/\/today$/);
    const task = page.locator(`[data-testid="task-link"][href="${taskHref}"]`);
    await expect(task.getByTestId("task-status")).toHaveText("Done");
    // Completing introduced its phrases, so it survives a reload: it's saved, not just shown.
    await page.reload();
    await expect(task.getByTestId("task-status")).toHaveText("Done");
  });

  await test.step("still no token is readable from the page", async () => {
    await expectNoReadableToken(page);
  });
});

/** ADR 0007: the session lives in HttpOnly cookies, so page scripts can't read any token. */
async function expectNoReadableToken(page: Page): Promise<void> {
  const readable = await page.evaluate(() => ({
    cookie: document.cookie,
    localStorage: Object.entries(localStorage),
    sessionStorage: Object.entries(sessionStorage),
  }));
  expect(readable.cookie).not.toMatch(JWT);
  expect(readable.cookie).not.toContain("cramplan_");
  expect(JSON.stringify(readable.localStorage)).not.toMatch(JWT);
  expect(JSON.stringify(readable.sessionStorage)).not.toMatch(JWT);

  // The session does exist, just out of the page's reach.
  const access = (await page.context().cookies()).find(({ name }) => name === "cramplan_access");
  expect(access?.value).toMatch(JWT);
  expect(access?.httpOnly).toBe(true);
}

/** `isoDate` (`YYYY-MM-DD`) plus `days`, as an `<input type="date">` takes it. */
function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
