import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/api/client", () => ({
  apiBaseUrl: "http://test.local/api",
  buildAuthHeaders: vi.fn(() => ({})),
  getJob: vi.fn(),
}));

async function load() {
  const client = await import("@/api/client");
  const hook = await import("@/hooks/use-job-snapshot");
  return { getJob: client.getJob, useJobSnapshot: hook.useJobSnapshot };
}

function makeJob(status: string) {
  return {
    job_id: "job-123",
    user_id: "pilot",
    status,
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:05:00Z",
    progress_log: [],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("useJobSnapshot", () => {
  it("loads initial job data", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );

    const auth = { userId: "pilot" };
    const { result } = renderHook(() => useJobSnapshot("job-123", auth));

    await waitFor(() => {
      expect(result.current.data?.status).toBe("review_running");
    });
  });

  it("polls while job is running", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );

    const auth = { userId: "pilot" };
    const intervalSpy = vi.spyOn(window, "setInterval");
    const { unmount } = renderHook(() => useJobSnapshot("job-123", auth));

    await waitFor(() => {
      expect(intervalSpy).toHaveBeenCalled();
    });

    unmount();
    intervalSpy.mockRestore();
  });

  it("does not poll when job is completed", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("completed")
    );

    const auth = { userId: "pilot" };
    const intervalSpy = vi.spyOn(window, "setInterval");
    renderHook(() => useJobSnapshot("job-123", auth));

    await waitFor(() => {
      expect(intervalSpy).not.toHaveBeenCalled();
    });

    intervalSpy.mockRestore();
  });
});
