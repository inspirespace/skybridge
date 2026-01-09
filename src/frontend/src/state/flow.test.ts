import { describe, expect, it } from "vitest";
import { canStartOver, deriveFlowState, getOpenStep } from "@/state/flow";
import type { JobRecord } from "@/api/client";

/** Handle baseJob. */
function baseJob(status: JobRecord["status"]): JobRecord {
  return {
    job_id: "00000000-0000-0000-0000-000000000000",
    user_id: "user",
    status,
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:10:00Z",
    progress_log: [],
    review_summary: null,
    import_report: null,
  };
}

describe("deriveFlowState", () => {
  it("returns initial state when signed out", () => {
    const state = deriveFlowState(false, null);
    expect(state.signedIn).toBe(false);
  });

  it("marks review complete when review ready", () => {
    const state = deriveFlowState(true, baseJob("review_ready"));
    expect(state.reviewStatus).toBe("complete");
    expect(state.importStatus).toBe("idle");
  });

  it("marks import running when import queued", () => {
    const state = deriveFlowState(true, baseJob("import_queued"));
    expect(state.importStatus).toBe("running");
  });

  it("keeps review complete when failed after review", () => {
    const job = baseJob("failed");
    job.review_summary = {
      flight_count: 1,
      total_hours: 1,
      missing_tail_numbers: 0,
      flights: [],
    };
    const state = deriveFlowState(true, job);
    expect(state.reviewStatus).toBe("complete");
    expect(state.importStatus).toBe("idle");
  });

  it("marks import failed when import events exist", () => {
    const job = baseJob("failed");
    job.review_summary = {
      flight_count: 1,
      total_hours: 1,
      missing_tail_numbers: 0,
      flights: [],
    };
    job.progress_log = [
      {
        phase: "import",
        stage: "Uploading",
        status: "import_running",
        created_at: "2026-01-01T10:05:00Z",
      },
    ];
    const state = deriveFlowState(true, job);
    expect(state.reviewStatus).toBe("complete");
    expect(state.importStatus).toBe("failed");
  });
});

describe("getOpenStep", () => {
  it("opens connect when signed out", () => {
    expect(
      getOpenStep({ signedIn: false, connected: false, reviewStatus: "idle", importStatus: "idle" })
    ).toBe("connect");
  });

  it("opens import when import running", () => {
    expect(
      getOpenStep({ signedIn: true, connected: true, reviewStatus: "complete", importStatus: "running" })
    ).toBe("import");
  });
});

describe("canStartOver", () => {
  it("blocks start over while running", () => {
    expect(canStartOver({ signedIn: true, connected: true, reviewStatus: "running", importStatus: "idle" })).toBe(
      false
    );
  });
});
