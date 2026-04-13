import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/hooks/use-job-snapshot", () => ({
  useJobSnapshot: vi.fn(),
}));

vi.mock("@/hooks/use-firebase-auth", () => ({
  useFirebaseAuth: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  listJobs: vi.fn(),
  listJobsWithOptions: vi.fn(),
  createJob: vi.fn(),
  acceptReview: vi.fn(),
  fetchArtifact: vi.fn(),
  validateCredentials: vi.fn(),
  deleteJob: vi.fn(),
  downloadArtifactsZip: vi.fn(),
}));

import App from "@/App";
import { listJobs, listJobsWithOptions } from "@/api/client";
import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import { useFirebaseAuth } from "@/hooks/use-firebase-auth";
import type { JobRecord } from "@/api/client";

const JOB_ID_KEY = "skybridge_job_id";

function firebaseAuthState(overrides: Record<string, unknown> = {}) {
  return {
    accessToken: null,
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

function jobRecord(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    job_id: "job-latest",
    user_id: "pilot",
    status: "review_ready",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
  sessionStorage.clear();
});

describe("App", () => {
  it("loads latest job when signed in without job id", async () => {
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());
    vi.mocked(listJobsWithOptions).mockResolvedValue({
      jobs: [jobRecord()],
    });

    render(<App />);

    await waitFor(() => {
      expect(listJobsWithOptions).toHaveBeenCalledWith({ token: "token" }, { retryAttempts: 1 });
    });
    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBe("job-latest");
    });
  });

  it("shows a restore loading state while looking up the latest job after sign-in", () => {
    const pendingLookup = new Promise<never>(() => {});
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());
    vi.mocked(listJobsWithOptions).mockReturnValue(pendingLookup);

    render(<App />);

    expect(screen.getByText(/^loading\.\.\.$/i)).toBeInTheDocument();
    expect(screen.queryByText(/connect accounts/i)).not.toBeInTheDocument();
  });

  it("shows a restore loading state while reloading a saved job", () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState({ loading: true }));

    render(<App />);

    expect(screen.getByText(/^loading\.\.\.$/i)).toBeInTheDocument();
    expect(screen.queryByText(/connect accounts/i)).not.toBeInTheDocument();
    expect(listJobsWithOptions).not.toHaveBeenCalled();
    expect(listJobs).not.toHaveBeenCalled();
  });

  it("retries latest job restore after a transient lookup failure", async () => {
    const transientError = new Error("Service unavailable") as Error & { status?: number };
    transientError.status = 503;

    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());
    vi.mocked(listJobsWithOptions)
      .mockRejectedValueOnce(transientError)
      .mockResolvedValueOnce({
        jobs: [jobRecord()],
      });

    render(<App />);

    await waitFor(() => {
      expect(listJobsWithOptions).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(listJobsWithOptions).toHaveBeenCalledTimes(2);
    }, { timeout: 3000 });
    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBe("job-latest");
    });
  }, 10000);

  it("keeps the main app visible while polling an already restored job", () => {
    sessionStorage.setItem(JOB_ID_KEY, "job-123");
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(
      jobSnapshotState({
        data: jobRecord({ job_id: "job-123", status: "review_running" }),
        loading: true,
      })
    );

    render(<App />);

    expect(screen.queryByText(/^loading\.\.\.$/i)).not.toBeInTheDocument();
    expect(screen.getByText(/verify your flight data/i)).toBeInTheDocument();
  });

  it("clears local job state on auth expired error", async () => {
    const signOut = vi.fn();
    sessionStorage.setItem(JOB_ID_KEY, "job-123");

    const authError = new Error("Token expired") as Error & { status?: number };
    authError.status = 401;

    vi.mocked(useFirebaseAuth).mockReturnValue(
      firebaseAuthState({
        accessToken: "token",
        signOut,
      })
    );
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState({ error: authError }));
    vi.mocked(listJobsWithOptions).mockResolvedValue({ jobs: [] });

    render(<App />);

    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBeNull();
      expect(signOut).toHaveBeenCalled();
    });
  });
});
