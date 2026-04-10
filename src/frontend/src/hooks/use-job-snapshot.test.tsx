import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

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

async function flushUpdates() {
  await act(async () => {
    await Promise.resolve();
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("useJobSnapshot", () => {
  it("loads initial job data", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );

    const auth = { token: "token" };
    const { result } = renderHook(() => useJobSnapshot("job-123", auth));

    await flushUpdates();
    await flushUpdates();

    expect(result.current.data?.status).toBe("review_running");
  });

  it("polls while job is running", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );

    const auth = { token: "token" };
    let intervalCallback: (() => void) | null = null;
    vi.spyOn(window, "setInterval").mockImplementation(
      ((callback: TimerHandler, _delay?: number, ..._args: any[]) => {
        intervalCallback = callback as () => void;
        return 1;
      }) as unknown as typeof window.setInterval
    );
    vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);

    renderHook(() => useJobSnapshot("job-123", auth));
    await flushUpdates();

    expect(getJob).toHaveBeenCalledTimes(1);
    expect(intervalCallback).not.toBeNull();

    if (intervalCallback) {
      await act(async () => {
        (intervalCallback as () => void)();
      });
    }
    await flushUpdates();

    expect(getJob).toHaveBeenCalledTimes(2);
  });

  it("does not poll when job is completed", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("completed")
    );

    const auth = { token: "token" };
    let intervalCallback: TimerHandler | null = null;
    vi.spyOn(window, "setInterval").mockImplementation(
      ((callback: TimerHandler, _delay?: number, ..._args: any[]) => {
        intervalCallback = callback;
        return 1;
      }) as unknown as typeof window.setInterval
    );
    vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);

    renderHook(() => useJobSnapshot("job-123", auth));
    await flushUpdates();
    await flushUpdates();

    expect(getJob).toHaveBeenCalledTimes(1);
    expect(intervalCallback).toBeNull();
  });
});
