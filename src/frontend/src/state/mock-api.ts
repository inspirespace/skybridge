import type { ImportStatus, ReviewStatus } from "@/state/flow";

export type ReviewProgress = {
  status: ReviewStatus;
  progress: number;
};

export type ImportProgress = {
  status: ImportStatus;
  progress: number;
};

/** Handle simulateReviewProgress. */
export function simulateReviewProgress(
  onTick: (state: ReviewProgress) => void
) {
  let progress = 0;
  const interval = window.setInterval(() => {
    progress = Math.min(100, progress + 15);
    if (progress >= 100) {
      onTick({ status: "complete", progress: 100 });
      window.clearInterval(interval);
      return;
    }
    onTick({ status: "running", progress });
  }, 350);

  return () => window.clearInterval(interval);
}

/** Handle simulateImportProgress. */
export function simulateImportProgress(
  onTick: (state: ImportProgress) => void
) {
  let progress = 0;
  const interval = window.setInterval(() => {
    progress = Math.min(100, progress + 12);
    if (progress >= 100) {
      onTick({ status: "complete", progress: 100 });
      window.clearInterval(interval);
      return;
    }
    onTick({ status: "running", progress });
  }, 400);

  return () => window.clearInterval(interval);
}
