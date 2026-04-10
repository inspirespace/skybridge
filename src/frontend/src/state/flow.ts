import type { JobRecord, JobStatus } from "@/api/client";

/** Type ReviewStatus. */
export type ReviewStatus = "idle" | "running" | "complete" | "failed";
/** Type ImportStatus. */
export type ImportStatus = "idle" | "running" | "complete" | "failed";

/** Type FlowState. */
export type FlowState = {
  signedIn: boolean;
  connected: boolean;
  reviewStatus: ReviewStatus;
  importStatus: ImportStatus;
};

export const initialFlowState: FlowState = {
  signedIn: false,
  connected: false,
  reviewStatus: "idle",
  importStatus: "idle",
};

const REVIEW_COMPLETE_STATUSES: JobStatus[] = [
  "review_ready",
  "import_queued",
  "import_running",
  "completed",
  "failed",
];

const REVIEW_RUNNING_STATUSES: JobStatus[] = ["review_queued", "review_running"];
const IMPORT_RUNNING_STATUSES: JobStatus[] = ["import_queued", "import_running"];

// Derive step state from the current job status.
/** Handle deriveFlowState. */
export function deriveFlowState(signedIn: boolean, job: JobRecord | null): FlowState {
  if (!signedIn) return initialFlowState;
  if (!job) {
    return {
      signedIn: true,
      connected: false,
      reviewStatus: "idle",
      importStatus: "idle",
    };
  }

  const status = job.status;
  const reviewStatus: ReviewStatus = REVIEW_RUNNING_STATUSES.includes(status)
    ? "running"
    : status === "failed"
      ? job.review_summary
        ? "complete"
        : "failed"
      : REVIEW_COMPLETE_STATUSES.includes(status)
        ? "complete"
        : "idle";

  const hasImportEvents =
    Array.isArray(job.progress_log) &&
    job.progress_log.some((event) => event?.phase === "import");
  const importStatus: ImportStatus = IMPORT_RUNNING_STATUSES.includes(status)
    ? "running"
    : status === "completed"
      ? "complete"
      : status === "failed" && hasImportEvents
        ? "failed"
        : "idle";

  return {
    signedIn: true,
    connected: true,
    reviewStatus,
    importStatus,
  };
}

// Determine which step should be open by default.
/** Get openstep. */
export function getOpenStep(state: FlowState) {
  if (!state.connected) return "connect";
  if (
    state.importStatus === "running" ||
    state.importStatus === "complete" ||
    state.importStatus === "failed"
  ) {
    return "import";
  }
  if (state.reviewStatus !== "complete") return "review";
  return "review";
}

/** Handle canStartOver. */
export function canStartOver(state: FlowState) {
  return state.connected && state.reviewStatus !== "running" && state.importStatus !== "running";
}
