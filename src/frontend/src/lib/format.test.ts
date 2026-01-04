import { describe, expect, it } from "vitest";
import { formatDateRange, formatPhaseElapsed, formatPhaseLastUpdate } from "@/lib/format";
import type { ProgressEvent } from "@/api/client";

describe("formatDateRange", () => {
  it("returns Any date when empty", () => {
    expect(formatDateRange(undefined)).toBe("Any date");
  });

  it("formats from/to", () => {
    const from = new Date("2026-01-05T00:00:00Z");
    const to = new Date("2026-01-10T00:00:00Z");
    expect(formatDateRange({ from, to })).toBe("2026-01-05 - 2026-01-10");
  });
});

describe("formatPhaseElapsed", () => {
  it("returns empty string when no phase events", () => {
    expect(formatPhaseElapsed([], "review", new Date(), false)).toBe("");
  });

  it("computes elapsed from phase events", () => {
    const log: ProgressEvent[] = [
      {
        phase: "review",
        stage: "Queued",
        status: "review_queued",
        created_at: "2026-01-01T10:00:00Z",
      },
      {
        phase: "review",
        stage: "Running",
        status: "review_running",
        created_at: "2026-01-01T10:02:00Z",
      },
    ];
    const now = new Date("2026-01-01T10:05:00Z");
    expect(formatPhaseElapsed(log, "review", now, true)).toBe("5m");
  });
});

describe("formatPhaseLastUpdate", () => {
  it("formats last update relative time", () => {
    const log: ProgressEvent[] = [
      {
        phase: "import",
        stage: "Queued",
        status: "import_queued",
        created_at: "2026-01-01T10:00:00Z",
      },
      {
        phase: "import",
        stage: "Running",
        status: "import_running",
        created_at: "2026-01-01T10:03:00Z",
      },
    ];
    const now = new Date("2026-01-01T10:05:00Z");
    expect(formatPhaseLastUpdate(log, "import", now)).toBe("2m ago");
  });
});
