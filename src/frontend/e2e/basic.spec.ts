import { test, expect } from "@playwright/test";

test("home page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Skybridge")).toBeVisible();
  await expect(page.getByRole("button", { name: /sign up \/ sign in/i })).toBeVisible();
});

test("imprint page loads", async ({ page }) => {
  await page.goto("/imprint");
  await expect(page.getByRole("heading", { name: /imprint/i })).toBeVisible();
  await expect(page.getByText("Inspirespace e.U.")).toBeVisible();
});

test("privacy page loads", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: /privacy/i })).toBeVisible();
});
