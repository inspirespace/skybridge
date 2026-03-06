import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/firebase-app-check", () => ({
  getAppCheckTokenHeader: vi.fn(async () => ({})),
}));

const okResponse = (payload: unknown) =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: async () => payload,
    headers: { get: () => "application/json" },
  });

const errorResponse = (status: number, body: string, contentType = "application/json") =>
  Promise.resolve({
    ok: false,
    status,
    text: async () => body,
    headers: { get: () => contentType },
  });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("buildAuthHeaders", () => {
  it("requires an access token", async () => {
    const { buildAuthHeaders } = await import("@/api/client");
    expect(() => buildAuthHeaders({})).toThrow(/missing access token/i);
  });

  it("uses bearer token", async () => {
    const { buildAuthHeaders } = await import("@/api/client");
    expect(buildAuthHeaders({ token: "token" })).toEqual({
      Authorization: "Bearer token",
    });
  });
});

describe("api base URL", () => {
  it("defaults to same-origin /api when unset", async () => {
    const { apiBaseUrl } = await import("@/api/client");
    expect(apiBaseUrl).toBe("/api");
  });
});

describe("request helpers", () => {
  it("propagates json error details and status", async () => {
    const { listJobs } = await import("@/api/client");

    const fetchMock = vi.fn(() =>
      errorResponse(401, JSON.stringify({ detail: "Not authorized" }))
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listJobs({ token: "token" })).rejects.toThrow(/not authorized/i);
    try {
      await listJobs({ token: "token" });
    } catch (err) {
      expect((err as Error & { status?: number }).status).toBe(401);
    }
  });

  it("sends JSON body and auth headers for createJob", async () => {
    const { createJob } = await import("@/api/client");

    const payload = {
      credentials: {
        cloudahoy_username: "user",
        cloudahoy_password: "pass",
        flysto_username: "user",
        flysto_password: "pass",
      },
    };
    const responsePayload = {
      job_id: "00000000-0000-0000-0000-000000000000",
      user_id: "pilot",
      status: "review_running",
      created_at: "2026-01-01T10:00:00Z",
      updated_at: "2026-01-01T10:00:00Z",
      progress_log: [],
    };

    const fetchMock = vi.fn(() => okResponse(responsePayload));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createJob(payload, { token: "token" });
    expect(result.job_id).toBe(responsePayload.job_id);

    const [url, options] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/jobs");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBe(JSON.stringify(payload));
    expect((options?.headers as Record<string, string>)?.Authorization).toBe("Bearer token");
  });

  it("returns JSON payload for listJobs", async () => {
    const { listJobs } = await import("@/api/client");

    const payload = { jobs: [] };
    const fetchMock = vi.fn(() => okResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listJobs({ token: "token" });
    expect(result.jobs).toEqual([]);
  });

  it("adds App Check header when token is available", async () => {
    const appCheck = await import("@/lib/firebase-app-check");
    vi.mocked(appCheck.getAppCheckTokenHeader).mockResolvedValue({
      "X-Firebase-AppCheck": "app-check-token",
    });
    const { listJobs } = await import("@/api/client");

    const payload = { jobs: [] };
    const fetchMock = vi.fn(() => okResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    await listJobs({ token: "token" });
    const [, options] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((options?.headers as Record<string, string>)?.["X-Firebase-AppCheck"]).toBe(
      "app-check-token"
    );
  });

  it("retries transient errors for GET requests", async () => {
    vi.stubEnv("VITE_API_RETRY_ATTEMPTS", "2");
    vi.stubEnv("VITE_API_RETRY_DELAY_MS", "1");
    const { listJobs } = await import("@/api/client");

    const payload = { jobs: [] };
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => errorResponse(502, "Bad gateway", "text/plain"))
      .mockImplementationOnce(() => okResponse(payload));
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();

    const promise = listJobs({ token: "token" });
    await vi.advanceTimersByTimeAsync(5);
    const result = await promise;

    expect(result.jobs).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
