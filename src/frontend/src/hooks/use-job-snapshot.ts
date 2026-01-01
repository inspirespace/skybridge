import * as React from "react";

import { getJob, type JobRecord, type JobStatus } from "@/api/client";

const POLLABLE_STATUSES: JobStatus[] = [
  "review_queued",
  "review_running",
  "import_queued",
  "import_running",
];

export function useJobSnapshot(jobId: string | null, userId: string | null) {
  const [data, setData] = React.useState<JobRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    if (!jobId || !userId) return;
    setLoading(true);
    try {
      const job = await getJob(jobId, userId);
      setData(job);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
    } finally {
      setLoading(false);
    }
  }, [jobId, userId]);

  React.useEffect(() => {
    if (!jobId || !userId) {
      setData(null);
      setError(null);
      return;
    }
    load();
  }, [jobId, userId, load]);

  React.useEffect(() => {
    if (!jobId || !userId || !data?.status) return;
    if (!POLLABLE_STATUSES.includes(data.status)) return;
    const interval = window.setInterval(() => {
      load();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [jobId, userId, data?.status, load]);

  return { data, loading, error, refresh: load };
}
