import { test, expect, type Page } from "@playwright/test";

async function enableBypassAuth(page: Page, options?: { jobId?: string }) {
  await page.addInitScript((payload) => {
    window.sessionStorage.setItem("skybridge_e2e_access_token", "e2e-token");
    window.sessionStorage.setItem("skybridge_e2e_user_id", "e2e-user");
    window.sessionStorage.removeItem("skybridge_e2e_is_anonymous");
    if (payload.jobId) {
      window.sessionStorage.setItem("skybridge_job_id", payload.jobId);
    } else {
      window.sessionStorage.removeItem("skybridge_job_id");
    }
  }, { jobId: options?.jobId ?? null });
}

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

test("restore loading falls back when latest-job lookup stalls", async ({ page }) => {
  await enableBypassAuth(page);
  await page.route("http://localhost:8000/api/jobs", async (route) => {
    await route.continue({
      url: "http://10.255.255.1:8000/api/jobs",
    });
  });

  await page.goto("/app/");

  await expect(page.getByText(/^loading\.\.\.$/i)).toBeVisible();
  await expect(page.getByText(/^loading\.\.\.$/i)).not.toBeVisible({ timeout: 4000 });
  await expect(page.getByText("1. Connect Accounts")).toBeVisible();
});

test("restore loading falls back when saved-job fetch stalls", async ({ page }) => {
  await enableBypassAuth(page, { jobId: "job-123" });
  await page.route("http://localhost:8000/api/jobs/job-123", async (route) => {
    await route.continue({
      url: "http://10.255.255.1:8000/api/jobs/job-123",
    });
  });

  await page.goto("/app/");

  await expect(page.getByText(/^loading\.\.\.$/i)).toBeVisible();
  await expect(page.getByText(/^loading\.\.\.$/i)).not.toBeVisible({ timeout: 4000 });
  await expect(page.getByText("1. Connect Accounts")).toBeVisible();
});
