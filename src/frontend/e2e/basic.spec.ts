import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/jobs", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [] }),
      });
      return;
    }
    await route.continue();
  });
});

test("home page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("SKYBRIDGE").first()).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("button", { name: /sign up \/ sign in/i })
  ).toBeVisible();
});

test("imprint page loads", async ({ page }) => {
  await page.goto("/imprint");
  await expect(page.getByRole("heading", { name: /imprint/i })).toBeVisible();
  await expect(page.getByText("Inspirespace e.U.", { exact: true }).first()).toBeVisible();
});

test("privacy page loads", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: /privacy/i })).toBeVisible();
});

test("sign in updates status", async ({ page }) => {
  await page.goto("/");
  const button = page
    .getByRole("main")
    .getByRole("button", { name: /sign up \/ sign in/i });
  await button.click();
  await expect(page.getByText("Connect accounts").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /connect and review/i })).toBeVisible();
});

test("edit import filters returns to connect step", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000123"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000123",
    user_id: "pilot@skybridge.dev",
    status: "review_ready",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [
      {
        phase: "review",
        stage: "Ready",
        status: "review_ready",
        created_at: "2026-01-01T10:05:00Z",
      },
    ],
    review_summary: {
      flight_count: 2,
      total_hours: 1.5,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: null,
  };

  let jobs = [jobPayload];
  await page.route("**/api/jobs", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/api/jobs/00000000-0000-0000-0000-000000000123", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jobPayload),
      });
      return;
    }
    if (route.request().method() === "DELETE") {
      jobs = [];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deleted: true }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/");
  await expect(page.getByText("Review ready").first()).toBeVisible();
  const editButton = page.getByRole("button", { name: /edit import filters/i });
  if (!(await editButton.isVisible())) {
    await page.getByRole("button", { name: /review ready/i }).click();
  }
  await page.getByRole("button", { name: /edit import filters/i }).click();
  await expect(page.getByText("Connect accounts").first()).toBeVisible();
  await expect(page.getByLabel("Email").first()).toBeEnabled();
});
