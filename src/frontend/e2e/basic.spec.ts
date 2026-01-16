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

test("sign in updates status", async ({ page }) => {
  await page.goto("/");
  const button = page
    .getByRole("main")
    .getByRole("link", { name: /sign up \/ sign in/i });
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

  await page.goto("/app/");
  await expect(page.getByText("Review ready").first()).toBeVisible();
  const editButton = page.getByRole("button", { name: /edit import filters/i });
  if (!(await editButton.isVisible())) {
    await page.getByRole("button", { name: /review ready/i }).click();
  }
  await page.getByRole("button", { name: /edit import filters/i }).click();
  await expect(page.getByText("Connect accounts").first()).toBeVisible();
  await expect(page.getByLabel("Email").first()).toBeEnabled();
});

test("import completed shows results summary", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000456"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000456",
    user_id: "pilot@skybridge.dev",
    status: "completed",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:15:00Z",
    progress_log: [
      {
        phase: "import",
        stage: "Import complete",
        status: "completed",
        created_at: "2026-01-01T10:15:00Z",
      },
    ],
    review_summary: {
      flight_count: 1,
      total_hours: 1.0,
      missing_tail_numbers: 1,
      flights: [],
    },
    import_report: {
      imported_count: 1,
      skipped_count: 0,
      failed_count: 0,
    },
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000456",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.goto("/app/");
  await expect(page.getByText("Import results")).toBeVisible();
  await expect(page.getByText("Total processed")).toBeVisible();
  await expect(page.getByRole("button", { name: /download files/i })).toBeVisible();
});

test("review running shows progress and disables approval", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000789"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000789",
    user_id: "pilot@skybridge.dev",
    status: "review_running",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_percent: 35,
    progress_stage: "Fetching flights",
    progress_log: [],
    review_summary: null,
    import_report: null,
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000789",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.goto("/app/");
  await expect(page.getByText("Review running").first()).toBeVisible();
  await expect(page.getByText("Fetching flights").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /accept and start import/i })).toBeDisabled();
});

test("review failure shows retry option", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000999"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000999",
    user_id: "pilot@skybridge.dev",
    status: "failed",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
    review_summary: null,
    import_report: null,
    error_message: "Review failed",
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000999",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.goto("/app/");
  await expect(page.getByText("Something went wrong")).toBeVisible();
  await expect(page.getByRole("button", { name: /retry/i })).toBeVisible();
});

test("download files shows expired message on 404", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000456"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000456",
    user_id: "pilot@skybridge.dev",
    status: "completed",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:15:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 1,
      total_hours: 1.0,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: {
      imported_count: 1,
      skipped_count: 0,
      failed_count: 0,
    },
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000456",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.route("**/api/jobs/00000000-0000-0000-0000-000000000456/artifacts.zip", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "text/plain",
      body: "Not found",
    });
  });

  await page.goto("/app/");
  await page.getByRole("button", { name: /download files/i }).click();
  await expect(
    page.getByText(/Files are no longer available/i)
  ).toBeVisible();
});

test("delete results shows success notice", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000777"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000777",
    user_id: "pilot@skybridge.dev",
    status: "completed",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:15:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 1,
      total_hours: 1.0,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: {
      imported_count: 1,
      skipped_count: 0,
      failed_count: 0,
    },
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000777",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      if (route.request().method() === "DELETE") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ deleted: true }),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.goto("/app/");
  await page.getByRole("button", { name: /delete results now/i }).click();
  await page.getByRole("button", { name: /delete results/i }).click();
  await expect(page.getByText("Results deleted")).toBeVisible();
});

test("download files succeeds and triggers download", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000888"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000888",
    user_id: "pilot@skybridge.dev",
    status: "completed",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:15:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 1,
      total_hours: 1.0,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: {
      imported_count: 1,
      skipped_count: 0,
      failed_count: 0,
    },
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000888",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.route("**/api/jobs/00000000-0000-0000-0000-000000000888/artifacts.zip", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/zip",
      body: "PK\u0005\u0006\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000",
    });
  });

  await page.goto("/app/");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /download files/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("skybridge-run-");
});

test("show more flights expands review table", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000999"
    );
  });

  const jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000999",
    user_id: "pilot@skybridge.dev",
    status: "review_ready",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 4,
      total_hours: 2.0,
      missing_tail_numbers: 0,
      flights: [
        { flight_id: "F1", date: "2026-01-01" },
        { flight_id: "F2", date: "2026-01-02" },
        { flight_id: "F3", date: "2026-01-03" },
        { flight_id: "F4", date: "2026-01-04" },
      ],
    },
    import_report: null,
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000999",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.goto("/app/");
  await expect(page.getByText("Show more flights")).toBeVisible();
  await page.getByRole("button", { name: /show more flights/i }).click();
  await expect(page.getByText("All flights shown")).toBeVisible();
});

test("connect review enables after credentials are filled", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
  });

  await page.goto("/app/");
  const connectButton = page.getByRole("button", { name: /connect and review/i });
  await expect(connectButton).toBeDisabled();

  await page.getByLabel("Email").first().fill("cloud@pilot.dev");
  await page.getByLabel("Password").first().fill("cloud-pass");
  await page.getByLabel("Email").nth(1).fill("flysto@pilot.dev");
  await page.getByLabel("Password").nth(1).fill("flysto-pass");

  await expect(connectButton).toBeEnabled();
});

test("connect review surfaces credential validation errors", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
  });

  await page.route("**/api/credentials/validate", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "text/plain",
      body: "Invalid credentials",
    });
  });

  await page.goto("/app/");
  const signInButton = page.getByRole("button", { name: /sign up \/ sign in/i });
  if (await signInButton.count()) {
    await signInButton.click();
  }
  const connectTrigger = page.getByRole("button", { name: /connect accounts/i }).first();
  if (await connectTrigger.isVisible()) {
    await connectTrigger.click();
  }
  await page.getByLabel("Email").first().fill("cloud@pilot.dev");
  await page.getByLabel("Password").first().fill("cloud-pass");
  await page.getByLabel("Email").nth(1).fill("flysto@pilot.dev");
  await page.getByLabel("Password").nth(1).fill("flysto-pass");

  await page.getByRole("button", { name: /connect and review/i }).click();
  await expect(page.getByText("Something went wrong")).toBeVisible();
  await expect(page.getByText("Invalid credentials")).toBeVisible();
  await expect(page.getByRole("button", { name: /retry/i })).toBeVisible();
});

test("accept review requires confirmation before starting import", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("skybridge_user_id", "pilot@skybridge.dev");
    window.localStorage.setItem(
      "skybridge_job_id",
      "00000000-0000-0000-0000-000000000555"
    );
  });

  let jobPayload = {
    job_id: "00000000-0000-0000-0000-000000000555",
    user_id: "pilot@skybridge.dev",
    status: "review_ready",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 2,
      total_hours: 1.2,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: null,
  };

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000555",
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(jobPayload),
        });
        return;
      }
      await route.continue();
    }
  );

  await page.route(
    "**/api/jobs/00000000-0000-0000-0000-000000000555/review/accept",
    async (route) => {
      jobPayload = {
        ...jobPayload,
        status: "import_running",
        progress_stage: "Import running",
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jobPayload),
      });
    }
  );

  await page.goto("/app/");
  const acceptButton = page.getByRole("button", { name: /accept and start import/i });
  if (!(await acceptButton.isVisible())) {
    await page.getByRole("button", { name: /review ready/i }).click();
  }

  await acceptButton.click();
  const startImport = page.getByRole("button", { name: /start import/i });
  await expect(startImport).toBeDisabled();
  await page.getByText("I understand and want to proceed with the import.").click();
  await expect(startImport).toBeEnabled();

  const requestPromise = page.waitForRequest(
    "**/api/jobs/00000000-0000-0000-0000-000000000555/review/accept"
  );
  await startImport.click();
  await requestPromise;
  await expect(page.getByText("Import running").first()).toBeVisible();
});
