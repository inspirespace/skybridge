import { getAppCheckTokenHeader } from "@/lib/firebase-app-check";

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
  progress_percent?: number | null;
  progress_stage?: string | null;
  progress_log?: ProgressEvent[];
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
  credentials: CredentialsPayload;
};

/** Type JobListResponse. */
export type JobListResponse = {
  jobs: JobRecord[];
};

/** Type CredentialValidationResponse. */
export type CredentialValidationResponse = {
  ok: boolean;
};

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? "https://skybridge.localhost/api";

const authMode = import.meta.env.VITE_AUTH_MODE ?? "header";
const RETRY_ATTEMPTS = Number.parseInt(
  import.meta.env.VITE_API_RETRY_ATTEMPTS ?? "4",
  10
);
const RETRY_DELAY_MS = Number.parseInt(
  import.meta.env.VITE_API_RETRY_DELAY_MS ?? "400",
  10
);
const RETRY_STATUSES = new Set([502, 503, 504]);

/** Type AuthContext. */
export type AuthContext = {
  userId?: string | null;
  token?: string | null;
};

/** Build authheaders. */
export function buildAuthHeaders(auth?: AuthContext, skipAuth = false) {
  const headers: Record<string, string> = {};
  if (skipAuth) return headers;
  const userId = auth?.userId ?? undefined;
  const token = auth?.token ?? undefined;

  if (authMode === "header") {
    if (!userId) {
      throw new Error("Missing user session. Please sign in again.");
    }
    headers["X-User-Id"] = userId;
  }

  if (authMode === "oidc" || authMode === "firebase") {
    if (!token) {
      throw new Error("Missing access token. Please sign in again.");
    }
    headers.Authorization = `Bearer ${token}`;
  }

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
    try {
      response = await fetch(`${apiBaseUrl}${path}`, {
        method,
        headers,
        signal,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      if (attempt < maxAttempts) {
        const delay = Math.min(4000, RETRY_DELAY_MS * 2 ** (attempt - 1));
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }
      throw err;
    }

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

export async function getJob(jobId: string, auth: AuthContext) {
  return requestJson<JobRecord>(`/jobs/${jobId}`, { auth });
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

export async function fetchArtifact(jobId: string, name: string, auth: AuthContext) {
  return requestJson<Record<string, unknown>>(
    `/jobs/${jobId}/artifacts/${name}`,
    { auth }
  );
}

export async function downloadArtifactsZip(jobId: string, auth: AuthContext) {
  const headers = await buildRequestHeaders(auth, false, false);
  const response = await fetch(`${apiBaseUrl}/jobs/${jobId}/artifacts.zip`, {
    headers,
  });
  if (!response.ok) {
    const message = await response.text();
    const error = new Error(message || "Download failed");
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  return response.blob();
}

export async function deleteJob(jobId: string, auth: AuthContext) {
  return requestJson<{ deleted: boolean }>(`/jobs/${jobId}`, {
    method: "DELETE",
    auth,
  });
}

/** Type TokenExchangeResponse. */
export type TokenExchangeResponse = {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  scope?: string;
};

export async function exchangeToken(payload: {
  code: string;
  code_verifier: string;
  redirect_uri: string;
}) {
  return requestJson<TokenExchangeResponse>("/auth/token", {
    method: "POST",
    body: payload,
    skipAuth: true,
  });
}

export async function refreshToken(payload: { refresh_token: string }, signal?: AbortSignal) {
  return requestJson<TokenExchangeResponse>("/auth/token", {
    method: "POST",
    body: payload,
    signal,
    skipAuth: true,
  });
}
