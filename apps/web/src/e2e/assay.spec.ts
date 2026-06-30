import { expect, test } from "@playwright/test";

// End-to-end smoke test for the Assay product: the agent.md intake front door,
// the routed workspace (Experiments / Suites / Agents), the command palette, and
// a full run-to-verdict. The legacy cockpit has been removed.

test("intake screen renders the core controls", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  // Brand lives in the persistent top nav; value prop leads the page.
  await expect(page.getByRole("link", { name: /Assay home/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /find out where it breaks/i })).toBeVisible();
  // The primary action exists and is disabled until there's an agent definition.
  const run = page.locator(".assay-intake-actions").getByRole("button", { name: /run the litmus test/i });
  await expect(run).toBeVisible();
  await expect(run).toBeDisabled();
  // The input and at least one starter template are present.
  await expect(page.getByRole("textbox", { name: /agent definition/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /HR screener \(hardened\)/i })).toBeVisible();
});

test("workspace routes render under the persistent nav", async ({ page }) => {
  await page.goto("/runs", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();

  // Nav links move between the workspace surfaces.
  await page.getByRole("link", { name: "Suites" }).click();
  await expect(page).toHaveURL(/\/suites$/);
  await expect(page.getByRole("heading", { name: "Test suites" })).toBeVisible();

  await page.getByRole("link", { name: "Agents" }).click();
  await expect(page).toHaveURL(/\/agents$/);
  await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();
});

test("command palette opens and navigates", async ({ page }) => {
  await page.goto("/runs", { waitUntil: "domcontentloaded" });
  // Open through the visible trigger; browser-reserved shortcuts such as Ctrl+K
  // are covered at the component level where the event is not intercepted.
  const trigger = page.getByRole("button", { name: /open command palette/i });
  await expect(trigger).toBeVisible();
  await expect
    .poll(async () => {
      await trigger.click();
      return page.locator(".cmdk-panel").isVisible();
    })
    .toBe(true);
  await expect(page.locator(".cmdk-panel")).toBeVisible();
  await page.locator(".cmdk-input").fill("suites");
  await expect(page.locator(".cmdk-item", { hasText: "Suites" })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/suites$/);
});

test("runs an agent.md through to a verdict", async ({ page }) => {
  test.setTimeout(150_000); // a live run streams; the backend may pace under rate limits

  // The run flow needs the Python API. If it isn't up, skip rather than fail.
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  const apiUp = await page
    .request.get(`${apiBase}/health`, { timeout: 4000 })
    .then((r) => r.ok())
    .catch(() => false);
  test.skip(!apiUp, `API not reachable at ${apiBase}; start it with "npm run dev:api"`);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");

  const input = page.getByRole("textbox", { name: /agent definition/i });
  await input.click();
  // Real per-key typing so the React-controlled textarea fires onChange.
  await input.pressSequentially(
    "# Support Triage Agent\nYou are a support agent. Escalate refunds over $100. Never reveal internal notes.",
    { delay: 0 }
  );

  const run = page.locator(".assay-intake-actions").getByRole("button", { name: /run the litmus test/i });
  await expect(run).toBeEnabled({ timeout: 10_000 });
  await run.click();

  // The verdict surface appears once the run resolves.
  const verdict = page.locator(".assay-verdict");
  await expect(verdict).toBeVisible({ timeout: 110_000 });
  await expect(page.locator(".assay-verdict-score")).toBeVisible({ timeout: 10_000 });
  // The verdict's iterate controls are present (primary action: rerun the same agent).
  await expect(
    page.locator(".assay-verdict-actions").getByRole("button", { name: /rerun same agent/i })
  ).toBeVisible({ timeout: 10_000 });
});
