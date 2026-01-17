import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/hooks/use-job-snapshot", () => ({
  useJobSnapshot: vi.fn(),
}));

vi.mock("@/hooks/use-oidc-auth", () => ({
  useOidcAuth: vi.fn(() => ({
    accessToken: null,
    idToken: null,
    userId: null,
    setUserId: vi.fn(),
    setAccessToken: vi.fn(),
    setIdToken: vi.fn(),
    startLogin: vi.fn(),
    signOut: vi.fn(),
    clearAuth: vi.fn(),
  })),
}));

vi.mock("@/hooks/use-firebase-auth", () => ({
  useFirebaseAuth: vi.fn(() => ({
    accessToken: null,
    startLogin: vi.fn(),
    startEmailLink: vi.fn(),
    completeEmailLink: vi.fn(),
    isAnonymous: false,
    emulatorProvider: null,
    emulatorReady: true,
    emailLinkPending: false,
    signOut: vi.fn(),
    clearAuth: vi.fn(),
  })),
}));

vi.mock("@/api/client", () => ({
  listJobs: vi.fn(),
  createJob: vi.fn(),
  acceptReview: vi.fn(),
  validateCredentials: vi.fn(),
  deleteJob: vi.fn(),
  downloadArtifactsZip: vi.fn(async () => new Blob(["zip"])),
}));

import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import { downloadArtifactsZip } from "@/api/client";
import App from "@/App";

const USER_ID_KEY = "skybridge_user_id";
const JOB_ID_KEY = "skybridge_job_id";

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function baseJob(overrides: Record<string, unknown>) {
  return {
    job_id: "job-123",
    user_id: "pilot",
    status: "review_ready",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
    review_summary: {
      flight_count: 1,
      total_hours: 1.0,
      missing_tail_numbers: 0,
      flights: [],
    },
    import_report: null,
    ...overrides,
  };
}

describe("App UI flows", () => {
  it("renders import results and allows download", async () => {
    sessionStorage.setItem(USER_ID_KEY, "pilot");
    sessionStorage.setItem(JOB_ID_KEY, "job-123");

    (useJobSnapshot as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: baseJob({
        status: "completed",
        import_report: { imported_count: 1, skipped_count: 0, failed_count: 0 },
      }),
      error: null,
      refresh: vi.fn(),
    });

    const clickMock = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const createObjectURL = vi.fn(() => "blob:download");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(window.URL, "createObjectURL", {
      value: createObjectURL,
      writable: true,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      value: revokeObjectURL,
      writable: true,
    });

    render(<App />);

    expect(await screen.findByText(/import results/i)).toBeInTheDocument();
    const download = screen.getByRole("button", { name: /download files/i });
    await act(async () => {
      fireEvent.click(download);
    });

    expect(downloadArtifactsZip).toHaveBeenCalled();
    clickMock.mockRestore();
  });

  it("shows review failure message when job failed before import", async () => {
    sessionStorage.setItem(USER_ID_KEY, "pilot");
    sessionStorage.setItem(JOB_ID_KEY, "job-123");

    (useJobSnapshot as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: baseJob({ status: "failed", error_message: "Review failed" }),
      error: null,
      refresh: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByText(/review failed/i)).toBeInTheDocument();
  });
});
