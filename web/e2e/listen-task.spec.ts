import { expect, test, type Page } from "@playwright/test";

/**
 * Playing a Listen Task against the real stack (`docker compose up`), on its
 * Scenario's hand-written fallback dialogue, so no Anthropic key is needed: a new
 * User opens today's Listen Task from Today, answers its three questions and Today
 * shows it done. Reopening it shows the answers.
 */

const PASSWORD = "e2e-Password-2026!";

test("a new User plays today's Listen Task, and Today shows it done", async ({ page }) => {
  await registerWithAnEvent(page);

  const taskHref = await test.step("open today's Listen Task from Today", async () => {
    const listenTask = page.getByTestId("task-link").filter({ hasText: "Listening" }).first();
    await expect(listenTask.getByTestId("task-status")).toHaveText("To do");
    const href = await listenTask.getAttribute("href");
    expect(href).toMatch(/^\/tasks\/[\w-]+\/listen$/);
    await listenTask.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.getByTestId("listen-lines").getByRole("listitem").first()).toBeVisible();
    return href!;
  });

  await test.step("a double tap sends one answer, and the reply reveals it", async () => {
    await page.getByTestId("option-1-1").dblclick();
    await expect(page.getByTestId("result-1")).toHaveText(/^(Right!|Not quite: the answer is “.+”\.)$/);
    // Inside main: Next.js's route announcer is an alert too.
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    for (const choice of [1, 2, 3]) await expect(page.getByTestId(`option-1-${choice}`)).toBeDisabled();
  });

  await test.step("the third answer completes the Task", async () => {
    await page.getByTestId("option-2-2").click();
    await expect(page.getByTestId("result-2")).not.toBeEmpty();
    await expect(page.getByTestId("listen-complete")).toHaveCount(0);
    await page.getByTestId("option-3-3").click();
    await expect(page.getByTestId("listen-complete")).toBeVisible();
  });

  await test.step("Today shows it done", async () => {
    await page.getByRole("link", { name: "Back to Today" }).click();
    await expect(page).toHaveURL(/\/today$/);
    const task = page.locator(`[data-testid="task-link"][href="${taskHref}"]`);
    await expect(task.getByTestId("task-status")).toHaveText("Done");
  });

  await test.step("reopening shows the answers, read-only", async () => {
    await page.goto(taskHref);
    for (const question of [1, 2, 3]) {
      await expect(page.getByTestId(`result-${question}`)).not.toBeEmpty();
      await expect(page.getByTestId(`option-${question}-1`)).toBeDisabled();
    }
    await expect(page.getByTestId("listen-complete")).toBeVisible();
    await expect(page.getByTestId("task-readonly")).toHaveCount(0);
  });
});

test("a Past Event's Listen Task shows its dialogue, read-only, and says why", async ({ page, baseURL }) => {
  await registerWithAnEvent(page);
  const href = await page.getByTestId("task-link").filter({ hasText: "Listening" }).first().getAttribute("href");
  const [event] = await (await page.request.get("/api/v1/events")).json();
  const abandoned = await page.request.post(`/api/v1/events/${event.id}/abandon`, { headers: { Origin: baseURL! } });
  expect(abandoned.status()).toBe(200);

  await page.goto(href!);

  await expect(page.getByTestId("listen-lines").getByRole("listitem").first()).toBeVisible();
  await expect(page.getByTestId("option-1-1")).toBeDisabled();
  await expect(page.getByTestId("task-readonly")).toHaveText(
    "This Task is part of a past Event, so its questions can't be answered any more.",
  );
});

test("Speak Tasks stay locked", async ({ page }) => {
  await registerWithAnEvent(page);
  await page.goto("/plan");

  const speak = page.getByTestId("task-locked").filter({ hasText: "Speaking" }).first();
  await expect(speak.getByTestId("task-status")).toHaveText("Coming soon");
  await expect(page.getByTestId("task-link").filter({ hasText: "Speaking" })).toHaveCount(0);
});

/** Register a fresh User and set up a job interview 12 days out, landing on Today. */
async function registerWithAnEvent(page: Page): Promise<void> {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);

  await page.getByLabel("Job interview").check();
  const min = await page.getByLabel("When is it?").getAttribute("min");
  expect(min).toBeTruthy();
  const date = new Date(`${min}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 9);
  await page.getByLabel("When is it?").fill(date.toISOString().slice(0, 10));
  await page.getByRole("button", { name: "Build my Plan" }).click();
  await expect(page).toHaveURL(/\/today$/);
}
