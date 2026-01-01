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

export function useJobSnapshot(jobId: string | null, auth: AuthContext) {
  const [data, setData] = React.useState<JobRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const job = await getJob(jobId, auth);
      setData(job);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
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

    const controller = new AbortController();
    const startStream = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/jobs/${jobId}/events`, {
          method: "GET",
          headers: {
            Accept: "text/event-stream",
            ...buildAuthHeaders(auth),
          },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error("Failed to open progress stream");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const dataLine = part
              .split("\n")
              .filter((line) => line.startsWith("data:"))
              .map((line) => line.replace(/^data:\\s?/, ""))
              .join("\n")
              .trim();
            if (!dataLine) continue;
            const payload = JSON.parse(dataLine) as JobRecord;
            setData(payload);
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(
          err instanceof Error ? err.message : "Failed to stream job updates"
        );
      }
    };

    startStream();
    return () => controller.abort();
  }, [jobId, data?.status, auth, load]);

  return { data, loading, error, refresh: load };
}
