import { test, expect } from "@playwright/test";

test("home page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("SKYBRIDGE").first()).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("link", { name: /sign up \/ sign in/i })
  ).toBeVisible();
});

test("imprint page loads", async ({ page }) => {
  await page.goto("/imprint/");
  await expect(page.getByRole("heading", { name: /imprint/i })).toBeVisible();
  await expect(page.getByText("Inspirespace e.U.", { exact: true }).first()).toBeVisible();
});

test("privacy page loads", async ({ page }) => {
  await page.goto("/privacy/");
  await expect(page.getByRole("heading", { name: /privacy/i })).toBeVisible();
});

test("sign in link opens the Firebase auth card", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("main")
    .getByRole("link", { name: /sign up \/ sign in/i })
    .click();

  await expect(page).toHaveURL(/\/app\/?\?signin=1/);
  await expect(page.getByText(/sign in to start your import/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /send link/i })).toBeVisible();
});
