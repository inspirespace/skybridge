from __future__ import annotations

import json
import os

from fastapi.responses import HTMLResponse


def landing_page() -> HTMLResponse:
"""Handle landing page."""
    auth_mode = (os.getenv("AUTH_MODE") or "header").lower()
    auth_enabled = auth_mode == "oidc"
    issuer = os.getenv("AUTH_BROWSER_ISSUER_URL") or os.getenv("AUTH_ISSUER_URL") or ""
    if auth_enabled and not issuer:
        issuer = "https://auth.skybridge.localhost/realms/skybridge-dev"
    client_id = os.getenv("AUTH_CLIENT_ID") or "skybridge-dev"
    scope = os.getenv("AUTH_SCOPE") or "openid profile email"
    redirect_path = os.getenv("AUTH_REDIRECT_PATH") or "/auth/callback"

    prefill_enabled = (os.getenv("DEV_PREFILL_CREDENTIALS") or "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    prefill = {
        "cloudahoy_username": os.getenv("CLOUD_AHOY_EMAIL") or "",
        "cloudahoy_password": os.getenv("CLOUD_AHOY_PASSWORD") or "",
        "flysto_username": os.getenv("FLYSTO_EMAIL") or "",
        "flysto_password": os.getenv("FLYSTO_PASSWORD") or "",
    }

    config = {
        "enabled": auth_enabled,
        "issuer": issuer,
        "clientId": client_id,
        "scope": scope,
        "redirectPath": redirect_path,
        "tokenProxy": (os.getenv("AUTH_TOKEN_PROXY") or "false").lower() in {"1", "true", "yes", "on"},
        "prefillEnabled": prefill_enabled,
        "prefill": prefill if prefill_enabled else {},
    }

    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Skybridge Dev Web</title>
        <style>
          :root {
            --text: #121212;
            --muted: #5f6368;
            --border: #d6d6d6;
            --panel: #ffffff;
            --bg: #f6f6f4;
            --accent: #0f62fe;
          }

          * { box-sizing: border-box; }
          body {
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            margin: 2rem auto;
            padding: 0 1.25rem 3rem;
            max-width: 960px;
            background: var(--bg);
            color: var(--text);
          }
          h1 { margin-bottom: 0.25rem; }
          p { margin-top: 0; color: var(--muted); }
          fieldset {
            margin: 0;
            border: 1px solid var(--border);
            padding: 1rem;
            border-radius: 10px;
            background: var(--panel);
          }
          legend { padding: 0 0.5rem; font-weight: 600; }
          label { display: block; margin: 0.65rem 0; font-weight: 600; }
          input {
            width: 100%;
            padding: 0.6rem 0.7rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 0.95rem;
          }
          button {
            padding: 0.65rem 1.1rem;
            margin-top: 0.5rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--accent);
            color: #fff;
            font-weight: 600;
            cursor: pointer;
          }
          button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }
          button.secondary {
            background: #fff;
            color: var(--text);
          }
          .card {
            border: 1px solid var(--border);
            padding: 1rem;
            margin-top: 1rem;
            border-radius: 12px;
            background: var(--panel);
          }
          .hidden { display: none; }
          .status { font-weight: 600; }
          .error { color: #b00020; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid var(--border); padding: 0.45rem; text-align: left; }

          .layout {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
          }
          .actions { margin-top: 1rem; display: flex; gap: 0.75rem; flex-wrap: wrap; }
          .flow {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
          }
          .step {
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            background: var(--panel);
          }
          .step h3 { margin: 0 0 0.25rem; font-size: 1rem; }
          .step .meta { color: var(--muted); font-size: 0.9rem; }
          .step.active { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(15, 98, 254, 0.12); }
          .step.done { border-color: #2e7d32; }
          .pill {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 999px;
            font-size: 0.75rem;
            background: #e8f0fe;
            color: #174ea6;
            margin-left: 0.35rem;
          }
          .toolbar {
            position: sticky;
            top: 0;
            background: var(--bg);
            padding: 0.5rem 0;
            z-index: 2;
          }
          .toast {
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            background: #1f1f1f;
            color: #fff;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            opacity: 0;
            pointer-events: none;
            transform: translateY(8px);
            transition: opacity 0.2s ease, transform 0.2s ease;
          }
          .toast.show { opacity: 1; transform: translateY(0); }
          .spinner {
            width: 14px;
            height: 14px;
            border: 2px solid #cfd8dc;
            border-top-color: var(--accent);
            border-radius: 50%;
            display: inline-block;
            animation: spin 0.8s linear infinite;
            margin-right: 0.4rem;
            vertical-align: -2px;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
          details summary { cursor: pointer; font-weight: 600; }

          @media (max-width: 720px) {
            body { margin-top: 1.5rem; }
            button { width: 100%; }
          }
        </style>
      </head>
      <body>
        <h1>Skybridge Dev Web</h1>
        <p>Create a migration job, review the summary, then approve the import.</p>

        <div id="authCard" class="card hidden">
          <h2>Authentication</h2>
          <div class="status" id="authStatus"></div>
          <div class="actions">
            <button id="loginBtn">Sign in</button>
            <button id="logoutBtn" class="secondary hidden">Sign out</button>
          </div>
        </div>

        <div id="devIdentity" class="card hidden">
          <h2>Local dev identity</h2>
          <label>User ID
            <input id="userId" placeholder="demo-user" />
          </label>
        </div>
        <div class="toolbar">
          <div class="flow">
            <div class="step" id="stepAuth">
              <h3>1) Sign in</h3>
              <div class="meta">Authenticate to start a migration.</div>
            </div>
            <div class="step" id="stepReview">
              <h3>2) Review</h3>
              <div class="meta">Generate review summary.</div>
            </div>
            <div class="step" id="stepImport">
              <h3>3) Import</h3>
              <div class="meta">Upload flights + assign metadata.</div>
            </div>
          </div>
        </div>

        <div class="layout">
          <fieldset>
            <legend>CloudAhoy credentials</legend>
            <label>Username <input id="cloudahoyUser" /></label>
            <label>Password <input id="cloudahoyPass" type="password" /></label>
          </fieldset>

          <fieldset>
            <legend>FlySto credentials</legend>
            <label>Username <input id="flystoUser" /></label>
            <label>Password <input id="flystoPass" type="password" /></label>
          </fieldset>

          <fieldset>
            <legend>Filters</legend>
            <label>Start date (YYYY-MM-DD)
              <input id="startDate" placeholder="2025-01-01" />
            </label>
            <label>End date (YYYY-MM-DD)
              <input id="endDate" placeholder="2025-12-31" />
            </label>
            <label>Max flights
              <input id="maxFlights" type="number" min="1" placeholder="50" />
            </label>
          </fieldset>
        </div>

        <div class="actions">
          <button id="createJob">Create job + run review</button>
        </div>

        <div id="jobCard" class="card hidden">
          <h2>Job</h2>
          <div class="status" id="jobStatus"></div>
          <div class="error" id="jobError"></div>
          <div id="jobHint"></div>
          <details>
            <summary>Job details</summary>
            <pre id="jobJson"></pre>
          </details>
          <div class="actions">
            <button id="acceptReview" disabled>Accept review + start import</button>
            <button id="resetJob" class="secondary">Clear saved job</button>
          </div>
        </div>

        <div id="reviewCard" class="card hidden">
          <h2>Review summary</h2>
          <div id="reviewSummary"></div>
          <table id="flightTable"></table>
        </div>

        <div id="reportCard" class="card hidden">
          <h2>Import report</h2>
          <details open>
            <summary>Report details</summary>
            <pre id="reportJson"></pre>
          </details>
        </div>
        <div id="toast" class="toast"></div>

        <script>
          const authConfig = __AUTH_CONFIG__;
          let pollHandle = null;
          let authError = null;
          let currentJob = null;

          const show = (id) => document.getElementById(id).classList.remove("hidden");
          const hide = (id) => document.getElementById(id).classList.add("hidden");

          const setText = (id, value) => {
            document.getElementById(id).textContent = value;
          };

          const toast = (message) => {
            const el = document.getElementById("toast");
            el.textContent = message;
            el.classList.add("show");
            setTimeout(() => el.classList.remove("show"), 2200);
          };

          const setButtonState = (id, enabled, label, showSpinner) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.disabled = !enabled;
            const text = label || btn.textContent;
            btn.innerHTML = showSpinner ? `<span class="spinner"></span>${text}` : text;
          };

          const parseJwt = (token) => {
            try {
              const payload = token.split(".")[1];
              const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
              return JSON.parse(decodeURIComponent(escape(json)));
            } catch (err) {
              return null;
            }
          };

          const isTokenExpired = (token) => {
            const payload = parseJwt(token) || {};
            const exp = payload.exp;
            if (!exp) return false;
            return Date.now() >= exp * 1000;
          };

          const ensureFreshToken = () => {
            const token = localStorage.getItem("access_token");
            if (token && !isTokenExpired(token)) return true;
            localStorage.removeItem("access_token");
            localStorage.removeItem("id_token");
            authError = "Session expired. Please sign in again.";
            updateAuthUI();
            return false;
          };

          const resetJobState = (message) => {
            localStorage.removeItem("lastJobId");
            currentJob = null;
            if (pollHandle) {
              clearInterval(pollHandle);
              pollHandle = null;
            }
            setText("jobJson", "");
            setText("jobStatus", message || "No active job.");
            setText("jobError", "");
            hide("reviewCard");
            hide("reportCard");
            updateFlowButtons();
          };

          const updateFlowButtons = () => {
            const signedIn = !!localStorage.getItem("access_token") || !authConfig.enabled;
            const status = currentJob ? currentJob.status : null;
            if (!signedIn) {
              setButtonState("createJob", false, "Create job + run review", false);
              setButtonState("acceptReview", false, "Accept review + start import", false);
              return;
            }
            if (status === "review_running" || status === "review_queued") {
              setButtonState("createJob", false, "Review running...", true);
            } else if (status === "import_running" || status === "import_queued") {
              setButtonState("createJob", false, "Import running...", true);
            } else {
              setButtonState("createJob", true, "Create job + run review", false);
            }
            if (status === "import_running" || status === "import_queued") {
              setButtonState("acceptReview", false, "Import running...", true);
            } else {
              setButtonState("acceptReview", status === "review_ready", "Accept review + start import", false);
            }
          };

          const authHeaders = () => {
            const headers = { "Content-Type": "application/json" };
            if (authConfig.enabled) {
              const token = localStorage.getItem("access_token");
              if (token) headers.Authorization = `Bearer ${token}`;
            } else {
              headers["X-User-Id"] = document.getElementById("userId").value || "demo-user";
            }
            return headers;
          };

          const authEndpoints = () => {
            const issuer = authConfig.issuer.replace(/\\/$/, "");
            return {
              authorize: `${issuer}/protocol/openid-connect/auth`,
              token: `${issuer}/protocol/openid-connect/token`,
              logout: `${issuer}/protocol/openid-connect/logout`,
            };
          };

          const base64UrlEncode = (buffer) => {
            const bytes = new Uint8Array(buffer);
            let binary = "";
            for (const byte of bytes) binary += String.fromCharCode(byte);
            return btoa(binary).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");
          };

          const sha256 = async (value) => {
            const encoded = new TextEncoder().encode(value);
            const digest = await crypto.subtle.digest("SHA-256", encoded);
            return base64UrlEncode(digest);
          };

          const beginLogin = async () => {
            const { authorize } = authEndpoints();
            const verifier = base64UrlEncode(crypto.getRandomValues(new Uint8Array(32)));
            const challenge = await sha256(verifier);
            const state = base64UrlEncode(crypto.getRandomValues(new Uint8Array(12)));
            sessionStorage.setItem("pkce_verifier", verifier);
            sessionStorage.setItem("auth_state", state);
            const redirectUri = window.location.origin + authConfig.redirectPath;
            const params = new URLSearchParams({
              response_type: "code",
              client_id: authConfig.clientId,
              redirect_uri: redirectUri,
              scope: authConfig.scope,
              code_challenge: challenge,
              code_challenge_method: "S256",
              state,
            });
            window.location.href = `${authorize}?${params.toString()}`;
          };

          const finishLogin = async (code, state) => {
            const expectedState = sessionStorage.getItem("auth_state");
            if (expectedState && state !== expectedState) {
              throw new Error("Auth state mismatch");
            }
            const verifier = sessionStorage.getItem("pkce_verifier");
            if (!verifier) throw new Error("Missing PKCE verifier");
            const redirectUri = window.location.origin + authConfig.redirectPath;
            let response = null;
            if (authConfig.tokenProxy) {
              response = await fetch("/auth/token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  code,
                  code_verifier: verifier,
                  redirect_uri: redirectUri,
                }),
              });
            } else {
              const { token } = authEndpoints();
              const body = new URLSearchParams({
                grant_type: "authorization_code",
                client_id: authConfig.clientId,
                code,
                redirect_uri: redirectUri,
                code_verifier: verifier,
              });
              response = await fetch(token, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body,
              });
            }
            if (!response.ok) {
              const text = await response.text();
              throw new Error(text || "Token exchange failed");
            }
            const payload = await response.json();
            localStorage.setItem("access_token", payload.access_token);
            localStorage.setItem("id_token", payload.id_token || "");
            sessionStorage.removeItem("pkce_verifier");
            sessionStorage.removeItem("auth_state");
          };

          const logout = () => {
            localStorage.removeItem("access_token");
            localStorage.removeItem("id_token");
            localStorage.removeItem("lastJobId");
            window.location.href = window.location.origin + "/";
          };

          const updateAuthUI = () => {
            if (!authConfig.enabled) {
              show("devIdentity");
              updateFlowButtons();
              return;
            }
            show("authCard");
            if (authError) {
              setText("authStatus", authError);
              show("loginBtn");
              hide("logoutBtn");
              updateFlowButtons();
              return;
            }
            const token = localStorage.getItem("access_token");
            if (token && isTokenExpired(token)) {
              localStorage.removeItem("access_token");
              localStorage.removeItem("id_token");
            }
            if (token) {
              document.getElementById("stepAuth").classList.add("done");
              const payload = parseJwt(token) || {};
              const name = payload.preferred_username || payload.email || payload.sub || "signed in";
              setText("authStatus", `Signed in as ${name}`);
              show("logoutBtn");
              hide("loginBtn");
            } else {
              document.getElementById("stepAuth").classList.remove("done");
              setText("authStatus", "Not signed in");
              show("loginBtn");
              hide("logoutBtn");
            }
            updateFlowButtons();
          };

          const renderReview = (summary) => {
            if (!summary) return;
            const summaryHtml = `
              <p><strong>Flights:</strong> ${summary.flight_count}</p>
              <p><strong>Total hours:</strong> ${summary.total_hours}</p>
              <p><strong>Earliest:</strong> ${summary.earliest_date || "-"}</p>
              <p><strong>Latest:</strong> ${summary.latest_date || "-"}</p>
              <p><strong>Missing tails:</strong> ${summary.missing_tail_numbers}</p>
            `;
            document.getElementById("reviewSummary").innerHTML = summaryHtml;

            const rows = [
              "<tr><th>ID</th><th>Date</th><th>Tail</th><th>Origin</th><th>Destination</th><th>Minutes</th><th>Status</th></tr>",
              ...summary.flights.map(
                (flight) =>
                  `<tr><td>${flight.flight_id}</td><td>${flight.date || "-"}</td><td>${flight.tail_number || "-"}</td><td>${flight.origin || "-"}</td><td>${flight.destination || "-"}</td><td>${flight.flight_time_minutes || "-"}</td><td>${flight.status || "-"}</td></tr>`
              ),
            ];
            document.getElementById("flightTable").innerHTML = rows.join("");
            show("reviewCard");
          };

          const readCredentials = () => ({
            cloudahoy_username: document.getElementById("cloudahoyUser").value,
            cloudahoy_password: document.getElementById("cloudahoyPass").value,
            flysto_username: document.getElementById("flystoUser").value,
            flysto_password: document.getElementById("flystoPass").value,
          });

          const formatElapsed = (startIso) => {
            if (!startIso) return "";
            const started = Date.parse(startIso);
            if (Number.isNaN(started)) return "";
            const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
            if (seconds < 60) return `${seconds}s`;
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `${minutes}m`;
            const hours = Math.floor(minutes / 60);
            return `${hours}h`;
          };

          const updateJobHint = (job) => {
            const hint = document.getElementById("jobHint");
            if (!job) {
              hint.textContent = "";
              currentJob = null;
              updateFlowButtons();
              return;
            }
            currentJob = job;
            updateFlowButtons();
            if (job.status === "review_running") {
              const elapsed = formatElapsed(job.created_at);
              hint.textContent = `Review running${elapsed ? ` · elapsed ${elapsed}` : ""}. This can take several minutes.`;
              document.getElementById("stepReview").classList.add("active");
              document.getElementById("stepImport").classList.remove("active");
              return;
            }
            if (job.status === "review_queued") {
              hint.textContent = "Review queued. Worker will start shortly.";
              document.getElementById("stepReview").classList.add("active");
              document.getElementById("stepImport").classList.remove("active");
              return;
            }
            if (job.status === "import_running") {
              const elapsed = formatElapsed(job.updated_at || job.created_at);
              hint.textContent = `Import running${elapsed ? ` · elapsed ${elapsed}` : ""}. This can take several minutes.`;
              document.getElementById("stepReview").classList.add("done");
              document.getElementById("stepImport").classList.add("active");
              return;
            }
            if (job.status === "import_queued") {
              hint.textContent = "Import queued. Worker will start shortly.";
              document.getElementById("stepReview").classList.add("done");
              document.getElementById("stepImport").classList.add("active");
              return;
            }
            if (job.status === "review_ready") {
              document.getElementById("stepReview").classList.add("done");
              document.getElementById("stepImport").classList.remove("active");
              hint.textContent = "Review ready. Approve to start import.";
              return;
            }
            if (job.status === "completed") {
              document.getElementById("stepImport").classList.add("done");
              hint.textContent = "Import completed.";
              return;
            }
            hint.textContent = "";
          };

          const refreshJob = async (jobId) => {
            if (!ensureFreshToken() && authConfig.enabled) {
              return null;
            }
            if (!jobId || jobId === "undefined") {
              setText("jobStatus", "Waiting for job id...");
              setText("jobError", "");
              return null;
            }
            const response = await fetch(`/jobs/${jobId}`, { headers: authHeaders() });
            if (!response.ok) {
              const detail = await response.text();
              if (response.status === 404 || response.status === 422) {
                resetJobState("Saved job no longer exists. Create a new job.");
                return null;
              }
              setText("jobStatus", "Failed to load job");
              setText("jobError", detail || "");
              updateFlowButtons();
              return null;
            }
            const job = await response.json();
            setText("jobJson", JSON.stringify(job, null, 2));
            setText("jobStatus", `Status: ${job.status}`);
            setText("jobError", job.error_message || "");
            currentJob = job;
            if (job.job_id) {
              localStorage.setItem("lastJobId", job.job_id);
            }
            updateJobHint(job);
            if (job.review_summary) {
              renderReview(job.review_summary);
            }
            if (job.import_report) {
              setText("reportJson", JSON.stringify(job.import_report, null, 2));
              show("reportCard");
            }
            return job;
          };

          const startPolling = (jobId) => {
            if (pollHandle) clearInterval(pollHandle);
            if (!jobId || jobId === "undefined") {
              setText("jobStatus", "Waiting for job id...");
              setText("jobError", "");
              updateFlowButtons();
              return;
            }
            pollHandle = setInterval(async () => {
              const job = await refreshJob(jobId);
              if (!job) return;
              if (job.status === "review_ready" || job.status === "completed" || job.status === "failed") {
                clearInterval(pollHandle);
              }
            }, 2000);
          };

          document.getElementById("loginBtn").addEventListener("click", beginLogin);
          document.getElementById("logoutBtn").addEventListener("click", logout);

          document.getElementById("createJob").addEventListener("click", async () => {
            if (!ensureFreshToken() && authConfig.enabled) return;
            setButtonState("createJob", false, "Running review...", true);
            hide("reviewCard");
            hide("reportCard");
            setText("jobError", "");

            const payload = {
              credentials: readCredentials(),
              start_date: document.getElementById("startDate").value || null,
              end_date: document.getElementById("endDate").value || null,
              max_flights: document.getElementById("maxFlights").value
                ? parseInt(document.getElementById("maxFlights").value, 10)
                : null,
            };

            const response = await fetch("/jobs", {
              method: "POST",
              headers: authHeaders(),
              body: JSON.stringify(payload),
            });
            const job = await response.json();
            setText("jobJson", JSON.stringify(job, null, 2));
            setText("jobStatus", `Status: ${job.status}`);
            show("jobCard");
            document.getElementById("jobCard").scrollIntoView({ behavior: "smooth", block: "start" });
            toast("Review started");
            if (job && job.job_id) {
              localStorage.setItem("lastJobId", job.job_id);
              startPolling(job.job_id);
            }
            currentJob = job;
            updateFlowButtons();
          });

          document.getElementById("acceptReview").addEventListener("click", async () => {
            if (!ensureFreshToken() && authConfig.enabled) return;
            const raw = document.getElementById("jobJson").textContent || "";
            let job = null;
            try {
              job = JSON.parse(raw);
            } catch (err) {
              setText("jobError", "Invalid job details. Try reloading.");
              return;
            }
            if (!job || !job.job_id) {
              setText("jobError", "Job id missing. Create a job first.");
              return;
            }
            setButtonState("acceptReview", false, "Starting import...", true);
            const payload = { credentials: readCredentials() };
            const response = await fetch(`/jobs/${job.job_id}/review/accept`, {
              method: "POST",
              headers: authHeaders(),
              body: JSON.stringify(payload),
            });
            if (!response.ok) {
              const detail = await response.text();
              setText("jobError", detail || "Failed to start import.");
              updateFlowButtons();
              return;
            }
            const updated = await response.json();
            setText("jobJson", JSON.stringify(updated, null, 2));
            setText("jobStatus", `Status: ${updated.status}`);
            if (updated && updated.job_id) {
              localStorage.setItem("lastJobId", updated.job_id);
              startPolling(updated.job_id);
            }
            toast("Import started");
            currentJob = updated;
            updateFlowButtons();
          });

          window.addEventListener("load", async () => {
            updateAuthUI();
            if (authConfig.prefillEnabled) {
              document.getElementById("cloudahoyUser").value = authConfig.prefill.cloudahoy_username || "";
              document.getElementById("cloudahoyPass").value = authConfig.prefill.cloudahoy_password || "";
              document.getElementById("flystoUser").value = authConfig.prefill.flysto_username || "";
              document.getElementById("flystoPass").value = authConfig.prefill.flysto_password || "";
            }
            const lastJobId = localStorage.getItem("lastJobId");
            if (lastJobId) {
              show("jobCard");
              startPolling(lastJobId);
            } else {
              resetJobState();
            }
            updateFlowButtons();
            if (!authConfig.enabled) return;
            const params = new URLSearchParams(window.location.search);
            const code = params.get("code");
            const state = params.get("state");
            if (code) {
              try {
                await finishLogin(code, state);
                window.history.replaceState({}, document.title, "/");
                authError = null;
              } catch (err) {
                authError = `Sign-in failed: ${err}`;
                console.error(err);
              }
            }
            updateAuthUI();
          });

          document.getElementById("resetJob").addEventListener("click", () => {
            resetJobState("Cleared saved job.");
            toast("Cleared saved job");
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html.replace("__AUTH_CONFIG__", json.dumps(config)))
