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

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? "https://skybridge.localhost/api";

const authMode = import.meta.env.VITE_AUTH_MODE ?? "header";

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

  if (authMode === "oidc") {
    if (!token) {
      throw new Error("Missing access token. Please sign in again.");
    }
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

async function requestJson<T>(
  path: string,
  {
    method = "GET",
    body,
    auth,
    skipAuth = false,
  }: {
    method?: string;
    body?: unknown;
    auth?: AuthContext;
    skipAuth?: boolean;
  } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...buildAuthHeaders(auth, skipAuth),
  };

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const message = await response.text();
    const errorMessage =
      message?.trim() || `Request failed (${response.status})`;
    const error = new Error(errorMessage);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }

  return response.json() as Promise<T>;
}

export async function createJob(payload: JobCreatePayload, auth: AuthContext) {
  return requestJson<JobRecord>("/jobs", {
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
  const response = await fetch(`${apiBaseUrl}/jobs/${jobId}/artifacts.zip`, {
    headers: {
      ...buildAuthHeaders(auth),
    },
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
