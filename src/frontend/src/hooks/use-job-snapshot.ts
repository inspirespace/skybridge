import * as React from "react";

import {
  apiBaseUrl,
  buildAuthHeaders,
  getJob,
  type AuthContext,
  type JobRecord,
  type JobStatus,
} from "@/api/client";

const POLLABLE_STATUSES: JobStatus[] = [
  "review_queued",
  "review_running",
  "import_queued",
  "import_running",
];

// Poll job updates in serverless mode.
/** Hook for jobsnapshot. */
export function useJobSnapshot(jobId: string | null, auth: AuthContext) {
  const [data, setData] = React.useState<JobRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);

  const load = React.useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const job = await getJob(jobId, auth);
      setData(job);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to load job"));
    } finally {
      setLoading(false);
    }
  }, [jobId, auth]);

  React.useEffect(() => {
    if (!jobId) {
      setData(null);
      setError(null);
      return;
    }
    load();
  }, [jobId, load]);

  React.useEffect(() => {
    if (!jobId || !data?.status) return;
    if (!POLLABLE_STATUSES.includes(data.status)) return;
    const interval = window.setInterval(() => {
      load();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [jobId, data?.status, auth, load]);

  return { data, loading, error, refresh: load };
}
