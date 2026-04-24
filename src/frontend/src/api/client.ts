import { getAppCheckTokenHeader } from "@/lib/firebase-app-check";
import { resolveApiBaseUrl } from "@/lib/runtime-endpoints";

/** Type JobStatus. */
export type JobStatus =
  | "review_queued"
  | "review_running"
  | "review_ready"
  | "import_queued"
  | "import_running"
  | "completed"
  | "failed";

/** Type FlightSummary. */
export type FlightSummary = {
  flight_id: string;
  date: string;
  tail_number?: string | null;
  origin?: string | null;
  destination?: string | null;
  flight_time_minutes?: number | null;
  status?: string | null;
  message?: string | null;
};

/** Type ReviewSummary. */
export type ReviewSummary = {
  flight_count: number;
  total_hours: number;
  earliest_date?: string | null;
  latest_date?: string | null;
  missing_tail_numbers: number;
  flights: FlightSummary[];
};

/** Type ReviewFlightsArtifact. */
export type ReviewFlightsArtifact = {
  review_id?: string | null;
  count?: number | null;
  items: FlightSummary[];
};

/** Type ImportReport. */
export type ImportReport = {
  imported_count: number;
  skipped_count: number;
  failed_count: number;
};

/** Type ProgressEvent. */
export type ProgressEvent = {
  phase: "review" | "import";
  stage: string;
  flight_id?: string | null;
  percent?: number | null;
  status: JobStatus;
  created_at: string;
};

/** Type JobRecord. */
export type JobRecord = {
  job_id: string;
  user_id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  heartbeat_at?: string | null;
  progress_percent?: number | null;
  progress_stage?: string | null;
  progress_log?: ProgressEvent[];
  worker_retry_count?: number | null;
  phase_cursor?: number | null;
  phase_total?: number | null;
  review_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  max_flights?: number | null;
  review_summary?: ReviewSummary | null;
  import_report?: ImportReport | null;
  error_message?: string | null;
};

/** Type ArtifactListResponse. */
export type ArtifactListResponse = {
  artifacts: string[];
};

/** Type CredentialsPayload. */
export type CredentialsPayload = {
  cloudahoy_username: string;
  cloudahoy_password: string;
  flysto_username: string;
  flysto_password: string;
};

/** Type JobCreatePayload. */
export type JobCreatePayload = {
  credentials: CredentialsPayload;
  start_date?: string | null;
  end_date?: string | null;
  max_flights?: number | null;
};

/** Type JobAcceptPayload. */
export type JobAcceptPayload = {
  credentials?: CredentialsPayload | null;
};

/** Type JobListResponse. */
export type JobListResponse = {
  jobs: JobRecord[];
};

/** Type CredentialValidationResponse. */
export type CredentialValidationResponse = {
  ok: boolean;
};

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
export const apiBaseUrl = resolveApiBaseUrl(configuredApiBaseUrl);

const RETRY_ATTEMPTS = Number.parseInt(
  import.meta.env.VITE_API_RETRY_ATTEMPTS ?? "4",
  10
);
const REQUEST_TIMEOUT_MS = Number.parseInt(
  import.meta.env.VITE_API_REQUEST_TIMEOUT_MS ?? "8000",
  10
);
const RETRY_DELAY_MS = Number.parseInt(
  import.meta.env.VITE_API_RETRY_DELAY_MS ?? "400",
  10
);
const RETRY_STATUSES = new Set([502, 503, 504]);

/** Type AuthContext. */
export type AuthContext = {
  token?: string | null;
};

/** Build authheaders. */
export function buildAuthHeaders(auth?: AuthContext, skipAuth = false) {
  const headers: Record<string, string> = {};
  if (skipAuth) return headers;
  const token = auth?.token ?? undefined;
  if (!token) {
    throw new Error("Missing access token. Please sign in again.");
  }
  headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function buildRequestHeaders(
  auth?: AuthContext,
  skipAuth = false,
  includeJsonContentType = true
) {
  const headers: Record<string, string> = {
    ...buildAuthHeaders(auth, skipAuth),
  };
  if (includeJsonContentType) {
    headers["Content-Type"] = "application/json";
  }
  const appCheckHeader = await getAppCheckTokenHeader();
  return { ...headers, ...appCheckHeader };
}

async function requestJson<T>(
  path: string,
  {
    method = "GET",
    body,
    auth,
    signal,
    skipAuth = false,
    retryAttempts,
  }: {
    method?: string;
    body?: unknown;
    auth?: AuthContext;
    signal?: AbortSignal;
    skipAuth?: boolean;
    retryAttempts?: number;
  } = {}
): Promise<T> {
  const headers = await buildRequestHeaders(auth, skipAuth, true);

  const maxAttempts =
    typeof retryAttempts === "number"
      ? Math.max(1, retryAttempts)
      : method.toUpperCase() === "GET"
        ? Math.max(1, RETRY_ATTEMPTS || 1)
        : 1;
  let attempt = 0;

  while (true) {
    attempt += 1;
    let response: Response;
    const timeoutMs =
      method.toUpperCase() === "GET" && Number.isFinite(REQUEST_TIMEOUT_MS)
        ? Math.max(0, REQUEST_TIMEOUT_MS)
        : 0;
    let timedOut = false;
    const controller = new AbortController();
    let timeoutId: number | null = null;
    const abortListener = () => {
      controller.abort(signal?.reason);
    };
    signal?.addEventListener("abort", abortListener, { once: true });
    try {
      const fetchPromise = fetch(`${apiBaseUrl}${path}`, {
        method,
        headers,
        signal: controller.signal,
        body: body ? JSON.stringify(body) : undefined,
      });
      response =
        timeoutMs > 0
          ? await Promise.race([
              fetchPromise,
              new Promise<Response>((_, reject) => {
                timeoutId = window.setTimeout(() => {
                  timedOut = true;
                  controller.abort();
                  reject(new Error("Request timed out. Please try again."));
                }, timeoutMs);
              }),
            ])
          : await fetchPromise;
    } catch (err) {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      signal?.removeEventListener("abort", abortListener);
      const abortedByCaller = signal?.aborted;
      if (abortedByCaller) {
        throw err;
      }
      const abortedByTimeout = timedOut && !abortedByCaller;
      if (abortedByTimeout) {
        throw new Error("Request timed out. Please try again.");
      }
      if (attempt < maxAttempts) {
        const delay = Math.min(4000, RETRY_DELAY_MS * 2 ** (attempt - 1));
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }
      throw err;
    }
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
    signal?.removeEventListener("abort", abortListener);

    if (response.ok) {
      return response.json() as Promise<T>;
    }

    if (attempt < maxAttempts && RETRY_STATUSES.has(response.status)) {
      const delay = Math.min(4000, RETRY_DELAY_MS * 2 ** (attempt - 1));
      await new Promise((resolve) => setTimeout(resolve, delay));
      continue;
    }

    const rawMessage = await response.text();
    let message = rawMessage;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        const parsed = JSON.parse(rawMessage) as { detail?: string };
        if (parsed?.detail) {
          message = parsed.detail;
        }
      } catch (parseError) {
        console.debug("Failed to parse error payload.", parseError);
      }
    }
    const errorMessage =
      message?.trim() || `Request failed (${response.status})`;
    const error = new Error(errorMessage);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
}

export async function createJob(payload: JobCreatePayload, auth: AuthContext) {
  return requestJson<JobRecord>("/jobs", {
    method: "POST",
    body: payload,
    auth,
  });
}

export async function validateCredentials(
  payload: { credentials: CredentialsPayload },
  auth: AuthContext
) {
  return requestJson<CredentialValidationResponse>("/credentials/validate", {
    method: "POST",
    body: payload,
    auth,
  });
}

export async function listJobs(auth: AuthContext) {
  return requestJson<JobListResponse>("/jobs", { auth });
}

export async function listJobsWithOptions(
  auth: AuthContext,
  options?: { retryAttempts?: number }
) {
  return requestJson<JobListResponse>("/jobs", {
    auth,
    retryAttempts: options?.retryAttempts,
  });
}

export async function getJob(jobId: string, auth: AuthContext, options?: { retryAttempts?: number }) {
  return requestJson<JobRecord>(`/jobs/${jobId}`, {
    auth,
    retryAttempts: options?.retryAttempts,
  });
}

export async function acceptReview(
  jobId: string,
  payload: JobAcceptPayload,
  auth: AuthContext
) {
  return requestJson<JobRecord>(`/jobs/${jobId}/review/accept`, {
    method: "POST",
    body: payload,
    auth,
  });
}

export async function listArtifacts(jobId: string, auth: AuthContext) {
  return requestJson<ArtifactListResponse>(`/jobs/${jobId}/artifacts`, { auth });
}

export async function fetchArtifact<T = Record<string, unknown>>(jobId: string, name: string, auth: AuthContext) {
  return requestJson<T>(
    `/jobs/${jobId}/artifacts/${name}`,
    { auth }
  );
}

export type DownloadArtifactsResult =
  | Blob
  | { downloadUrl: string; filename: string }
  | { preparing: true; detail: string };

export async function downloadArtifactsZip(
  jobId: string,
  auth: AuthContext
): Promise<DownloadArtifactsResult> {
  // Ask for JSON so the server can hand us a short-lived signed URL instead of
  // streaming the zip through the function (which exceeded the Cloudflare 100 s
  // edge timeout on multi-flight imports). A 202 response means the archive
  // is being built in the background — frontend should surface a "preparing"
  // message and let the user retry.
  const headers = {
    ...(await buildRequestHeaders(auth, false, false)),
    Accept: "application/json",
  };
  const response = await fetch(`${apiBaseUrl}/jobs/${jobId}/artifacts.zip`, {
    headers,
  });
  if (response.status === 202) {
    let detail = "Preparing your download. Try again in a moment.";
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      // Fall back to the default message if body isn't JSON.
    }
    return { preparing: true, detail };
  }
  if (!response.ok) {
    const message = await response.text();
    const error = new Error(message || "Download failed");
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    const data = (await response.json()) as { download_url?: string; filename?: string };
    if (!data.download_url) {
      throw new Error("Download URL missing from response");
    }
    return { downloadUrl: data.download_url, filename: data.filename || `skybridge-run-${jobId}.zip` };
  }
  return response.blob();
}

export async function deleteJob(jobId: string, auth: AuthContext) {
  return requestJson<{ deleted: boolean }>(`/jobs/${jobId}`, {
    method: "DELETE",
    auth,
  });
}
