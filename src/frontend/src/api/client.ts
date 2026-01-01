export type JobStatus =
  | "review_queued"
  | "review_running"
  | "review_ready"
  | "import_queued"
  | "import_running"
  | "completed"
  | "failed";

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

export type ReviewSummary = {
  flight_count: number;
  total_hours: number;
  earliest_date?: string | null;
  latest_date?: string | null;
  missing_tail_numbers: number;
  flights: FlightSummary[];
};

export type ImportReport = {
  imported_count: number;
  skipped_count: number;
  failed_count: number;
};

export type JobRecord = {
  job_id: string;
  user_id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  review_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  max_flights?: number | null;
  review_summary?: ReviewSummary | null;
  import_report?: ImportReport | null;
  error_message?: string | null;
};

export type ArtifactListResponse = {
  artifacts: string[];
};

export type CredentialsPayload = {
  cloudahoy_username: string;
  cloudahoy_password: string;
  flysto_username: string;
  flysto_password: string;
};

export type JobCreatePayload = {
  credentials: CredentialsPayload;
  start_date?: string | null;
  end_date?: string | null;
  max_flights?: number | null;
};

export type JobAcceptPayload = {
  credentials: CredentialsPayload;
};

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? "https://skybridge.localhost/api";

const authMode = import.meta.env.VITE_AUTH_MODE ?? "header";

export type AuthContext = {
  userId?: string | null;
  token?: string | null;
};

async function requestJson<T>(
  path: string,
  {
    method = "GET",
    body,
    auth,
  }: {
    method?: string;
    body?: unknown;
    auth?: AuthContext;
  } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
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

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Request failed");
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

export async function deleteJob(jobId: string, auth: AuthContext) {
  return requestJson<{ deleted: boolean }>(`/jobs/${jobId}`, {
    method: "DELETE",
    auth,
  });
}

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
  });
}
