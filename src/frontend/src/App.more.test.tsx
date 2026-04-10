import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/hooks/use-job-snapshot", () => ({
  useJobSnapshot: vi.fn(),
}));

vi.mock("@/hooks/use-firebase-auth", () => ({
  useFirebaseAuth: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  listJobs: vi.fn(),
  createJob: vi.fn(),
  acceptReview: vi.fn(),
  fetchArtifact: vi.fn(),
  validateCredentials: vi.fn(),
  deleteJob: vi.fn(),
  downloadArtifactsZip: vi.fn(async () => new Blob(["zip"])),
}));

import App from "@/App";
import { acceptReview, deleteJob, downloadArtifactsZip, fetchArtifact } from "@/api/client";
import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import { useFirebaseAuth } from "@/hooks/use-firebase-auth";
import type { JobRecord } from "@/api/client";

const JOB_ID_KEY = "skybridge_job_id";

function firebaseAuthState(overrides: Record<string, unknown> = {}) {
  return {
    accessToken: "token",
    idToken: null,
    startLogin: vi.fn(),
    startEmailLink: vi.fn(async () => ({ sent: true, linkUrl: null })),
    completeEmailLink: vi.fn(),
    isAnonymous: false,
    emulatorProvider: null,
    emulatorReady: true,
    authReady: true,
    userId: null,
    emailLinkPending: false,
    signOut: vi.fn(),
    clearAuth: vi.fn(),
    ...overrides,
  };
}

function jobSnapshotState(overrides: Record<string, unknown> = {}) {
  return {
    data: null,
    loading: false,
    error: null,
    refresh: vi.fn(async () => undefined),
    listenerFailed: false,
    listenerActive: false,
    lastSnapshotAt: null,
    ...overrides,
  };
}

function baseJob(overrides: Partial<JobRecord>): JobRecord {
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

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("App UI flows", () => {
  it("shows inbox guidance only after the email-link request succeeds", async () => {
    const startEmailLink = vi.fn(async () => ({ sent: true, linkUrl: null }));
    vi.mocked(useFirebaseAuth).mockReturnValue(
      firebaseAuthState({
        accessToken: null,
        startEmailLink,
      })
    );
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());

    render(<App />);

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/passwordless email link/i), {
        target: { value: "pilot@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /send link/i }));
    });

    expect(startEmailLink).toHaveBeenCalledWith("pilot@example.com");
    expect(
      await screen.findByText(/check pilot@example.com for your sign-in link/i)
    ).toBeInTheDocument();
  });

  it("still sends the email link when browser storage writes are blocked", async () => {
    const startEmailLink = vi.fn(async () => ({ sent: true, linkUrl: null }));
    const setItemSpy = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("Storage blocked", "SecurityError");
      });
    vi.mocked(useFirebaseAuth).mockReturnValue(
      firebaseAuthState({
        accessToken: null,
        startEmailLink,
      })
    );
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());

    render(<App />);

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/passwordless email link/i), {
        target: { value: "pilot@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /send link/i }));
    });

    expect(startEmailLink).toHaveBeenCalledWith("pilot@example.com");
    expect(
      await screen.findByText(/check pilot@example.com for your sign-in link/i)
    ).toBeInTheDocument();
    setItemSpy.mockRestore();
  });

  it("does not show a success notice when Firebase rejects the email-link request", async () => {
    const startEmailLink = vi.fn(async () => ({ sent: false, linkUrl: null }));
    vi.mocked(useFirebaseAuth).mockReturnValue(
      firebaseAuthState({
        accessToken: null,
        startEmailLink,
      })
    );
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());

    render(<App />);

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/passwordless email link/i), {
        target: { value: "pilot@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /send link/i }));
    });

    expect(startEmailLink).toHaveBeenCalledWith("pilot@example.com");
    expect(
      screen.queryByText(/check pilot@example.com for your sign-in link/i)
    ).not.toBeInTheDocument();
  });

  it("returns to connect step immediately while edit-filter delete is in flight", async () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");

    const neverSettles = new Promise<never>(() => {});
    vi.mocked(deleteJob).mockReturnValue(neverSettles);
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState());
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({ data: baseJob({ status: "review_ready" }) })
    );

    render(<App />);

    const editFilters = await screen.findByRole("button", { name: /edit import filters/i });
    await act(async () => {
      fireEvent.click(editFilters);
    });

    expect(await screen.findByText(/connect accounts/i)).toBeInTheDocument();
  });

  it("renders import results and allows download", async () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState());
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({
        data: baseJob({
          status: "completed",
          import_report: { imported_count: 1, skipped_count: 0, failed_count: 0 },
        }),
      })
    );

    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
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
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState());
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({
        data: baseJob({ status: "failed", error_message: "Review failed" }),
      })
    );

    render(<App />);

    expect(await screen.findByText(/review failed/i)).toBeInTheDocument();
  });

  it("loads review rows from the artifact when the job summary is slim", async () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(fetchArtifact).mockResolvedValue({
      review_id: "review-1",
      items: [
        {
          flight_id: "flight-1",
          date: "2026-01-05T09:00:00Z",
          tail_number: "N123",
          origin: "KSEA",
          destination: "KLAX",
        },
      ],
    });
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState());
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({
        data: baseJob({
          status: "review_ready",
          review_summary: {
            flight_count: 1,
            total_hours: 1.0,
            missing_tail_numbers: 0,
            flights: [],
          },
        }),
      })
    );

    render(<App />);

    expect(await screen.findByText("KSEA")).toBeInTheDocument();
    expect(fetchArtifact).toHaveBeenCalledWith("job-123", "review-flights.json", { token: "token" });
  });

  it("shows retry import action after a failed import", async () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState());
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({
        data: baseJob({
          status: "failed",
          error_message: "Import failed",
          review_summary: {
            flight_count: 1,
            total_hours: 1.0,
            missing_tail_numbers: 0,
            flights: [],
          },
          progress_log: [
            {
              phase: "import",
              stage: "Uploading",
              status: "import_running",
              created_at: "2026-01-01T10:05:00Z",
            },
          ],
        }),
      })
    );

    render(<App />);

    const retryImport = await screen.findByRole("button", { name: /retry import/i });
    await act(async () => {
      fireEvent.click(retryImport);
    });

    expect(acceptReview).toHaveBeenCalledWith("job-123", {}, { token: "token" });
  });
});
