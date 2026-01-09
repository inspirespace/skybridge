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

function sseStream(payload: object) {
  const encoder = new TextEncoder();
  const body = `data: ${JSON.stringify(payload)}\n\n`;
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body));
      controller.close();
    },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("useJobSnapshot", () => {
  it("updates data from SSE payload", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );

    const updated = makeJob("review_ready");
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve(
        new Response(sseStream(updated), {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        })
      )
    );

    const auth = { userId: "pilot" };
    const { result } = renderHook(() => useJobSnapshot("job-123", auth));

    await Promise.resolve();
    await Promise.resolve();

    await waitFor(() => {
      expect(result.current.data?.status).toBe("review_ready");
    });
  });

  it("falls back to polling after silent SSE", async () => {
    const { getJob, useJobSnapshot } = await load();
    (getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeJob("review_running")
    );
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("stream failed")
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
});
