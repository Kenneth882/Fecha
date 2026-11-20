import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests, run against a stack that's already up: `docker compose up` from the
 * repo root serves the web app on :3000, with the API, worker, Postgres and Redis behind
 * it. Playwright doesn't start a server itself, since the web app alone can't do anything.
 * Point it elsewhere with E2E_BASE_URL. See https://playwright.dev/docs/test-configuration.
 *
 * Specs live in `e2e/` as `*.spec.ts`, so Vitest (which only picks up `*.test.ts`)
 * never runs them, and Playwright never runs the unit tests.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // Fail CI if a `test.only` was left in.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    // Kept for every failed attempt, so CI's uploaded report always has one to open.
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
