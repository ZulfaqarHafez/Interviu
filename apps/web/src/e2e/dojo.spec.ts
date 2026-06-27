import { expect, test } from "@playwright/test";

test("renders the Interviu evaluation workspace", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Interviu" })).toBeVisible();
  await expect(page.getByRole("button", { name: /run evaluation/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Run setup" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Score" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Proof" })).toBeVisible();
  await expect(page.getByText("Add HTTP candidate")).toBeVisible();
  await expect(page.getByText("Exam export")).toBeVisible();
});
