import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

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
  validateCredentials: vi.fn(),
  deleteJob: vi.fn(),
  downloadArtifactsZip: vi.fn(),
}));

import App from "@/App";
import { listJobs } from "@/api/client";
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
  vi.resetAllMocks();
  sessionStorage.clear();
});

describe("App", () => {
  it("loads latest job when signed in without job id", async () => {
    vi.mocked(useFirebaseAuth).mockReturnValue(firebaseAuthState({ accessToken: "token" }));
    vi.mocked(useJobSnapshot).mockReturnValue(jobSnapshotState());
    vi.mocked(listJobs).mockResolvedValue({
      jobs: [jobRecord()],
    });

    render(<App />);

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith({ token: "token" });
    });
    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBe("job-latest");
    });
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
    vi.mocked(listJobs).mockResolvedValue({ jobs: [] });

    render(<App />);

    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBeNull();
      expect(signOut).toHaveBeenCalled();
    });
  });
});
