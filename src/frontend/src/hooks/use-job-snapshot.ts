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

// Subscribe to a job via SSE with polling fallback.
export function useJobSnapshot(jobId: string | null, auth: AuthContext) {
  const [data, setData] = React.useState<JobRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);
  const [streamFailed, setStreamFailed] = React.useState(false);

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
      setStreamFailed(false);
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
          const err = new Error(`Request failed (${response.status})`);
          (err as Error & { status?: number }).status = response.status;
          setError(err);
          throw err;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let receivedAny = false;
        setStreamFailed(false);

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
              .map((line) => line.replace(/^data:\s?/, ""))
              .join("\n")
              .trim();
            if (!dataLine) continue;
            const payload = JSON.parse(dataLine) as JobRecord;
            receivedAny = true;
            setData(payload);
          }
        }
        if (!receivedAny) {
          setStreamFailed(true);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        console.warn("SSE stream failed, falling back to polling.", err);
        setStreamFailed(true);
      }
    };

    startStream();
    return () => controller.abort();
  }, [jobId, data?.status, auth, load]);

  React.useEffect(() => {
    if (!jobId || !data?.status) return;
    if (!POLLABLE_STATUSES.includes(data.status)) return;
    if (!streamFailed) return;
    const interval = window.setInterval(() => {
      load();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [jobId, data?.status, streamFailed, load]);

  return { data, loading, error, refresh: load };
}
