export type ReviewStatus = "idle" | "running" | "complete";
export type ImportStatus = "idle" | "running" | "complete";

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

export function getOpenStep(state: FlowState) {
  if (!state.signedIn) return "sign-in";
  if (!state.connected) return "connect";
  if (state.reviewStatus !== "complete") return "review";
  return "import";
}

export function canApproveImport(state: FlowState) {
  return state.reviewStatus === "complete" && state.importStatus === "idle";
}

export function canEditFilters(state: FlowState) {
  return state.reviewStatus === "complete" && state.importStatus === "idle";
}

export function canStartOver(state: FlowState) {
  return state.connected && state.reviewStatus !== "running";
}
