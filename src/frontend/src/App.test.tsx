import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

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
  downloadArtifactsZip: vi.fn(),
}));

import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import { listJobs } from "@/api/client";
import App from "@/App";

const USER_ID_KEY = "skybridge_user_id";
const JOB_ID_KEY = "skybridge_job_id";

afterEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
});

describe("App", () => {
  it("loads latest job when signed in without job id", async () => {
    sessionStorage.setItem(USER_ID_KEY, "pilot");

    (useJobSnapshot as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: null,
      error: null,
      refresh: vi.fn(),
    });

    (listJobs as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      jobs: [{ job_id: "job-latest" }],
    });

    render(<App />);

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBe("job-latest");
    });
  });

  it("clears local session on auth expired error", async () => {
    sessionStorage.setItem(USER_ID_KEY, "pilot");
    sessionStorage.setItem(JOB_ID_KEY, "job-123");

    const authError = new Error("Token expired") as Error & { status?: number };
    authError.status = 401;

    (useJobSnapshot as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: null,
      error: authError,
      refresh: vi.fn(),
    });

    render(<App />);

    await waitFor(() => {
      expect(sessionStorage.getItem(USER_ID_KEY)).toBeNull();
      expect(sessionStorage.getItem(JOB_ID_KEY)).toBeNull();
    });
  });
});
