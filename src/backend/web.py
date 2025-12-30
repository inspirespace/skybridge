from __future__ import annotations

import json
import os

from fastapi.responses import HTMLResponse


def landing_page() -> HTMLResponse:
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
          body { font-family: sans-serif; margin: 2rem; max-width: 900px; }
          fieldset { margin-bottom: 1rem; }
          label { display: block; margin: 0.5rem 0; }
          input { width: 100%; padding: 0.5rem; }
          button { padding: 0.6rem 1rem; margin-top: 0.5rem; }
          .card { border: 1px solid #ddd; padding: 1rem; margin-top: 1rem; }
          .hidden { display: none; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #ddd; padding: 0.4rem; text-align: left; }
          .status { font-weight: 600; }
          .error { color: #b00020; }
        </style>
      </head>
      <body>
        <h1>Skybridge Dev Web</h1>
        <p>Create a migration job, review the summary, then approve the import.</p>

        <div id="authCard" class="card hidden">
          <h2>Authentication</h2>
          <div class="status" id="authStatus"></div>
          <button id="loginBtn">Sign in</button>
          <button id="logoutBtn" class="hidden">Sign out</button>
        </div>

        <div id="devIdentity" class="card hidden">
          <h2>Local dev identity</h2>
          <label>User ID
            <input id="userId" placeholder="demo-user" />
          </label>
        </div>

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

        <button id="createJob">Create job + run review</button>

        <div id="jobCard" class="card hidden">
          <h2>Job</h2>
          <div class="status" id="jobStatus"></div>
          <div class="error" id="jobError"></div>
          <pre id="jobJson"></pre>
          <button id="acceptReview">Accept review + start import</button>
        </div>

        <div id="reviewCard" class="card hidden">
          <h2>Review summary</h2>
          <div id="reviewSummary"></div>
          <table id="flightTable"></table>
        </div>

        <div id="reportCard" class="card hidden">
          <h2>Import report</h2>
          <pre id="reportJson"></pre>
        </div>

        <script>
          const authConfig = __AUTH_CONFIG__;
          let pollHandle = null;
          let authError = null;

          const show = (id) => document.getElementById(id).classList.remove("hidden");
          const hide = (id) => document.getElementById(id).classList.add("hidden");

          const setText = (id, value) => {
            document.getElementById(id).textContent = value;
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
            const issuer = authConfig.issuer.replace(/\/$/, "");
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
            return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
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
            window.location.href = window.location.origin + "/";
          };

          const updateAuthUI = () => {
            if (!authConfig.enabled) {
              show("devIdentity");
              return;
            }
            show("authCard");
            if (authError) {
              setText("authStatus", authError);
              show("loginBtn");
              hide("logoutBtn");
              return;
            }
            const token = localStorage.getItem("access_token");
            if (token) {
              const payload = parseJwt(token) || {};
              const name = payload.preferred_username || payload.email || payload.sub || "signed in";
              setText("authStatus", `Signed in as ${name}`);
              show("logoutBtn");
              hide("loginBtn");
            } else {
              setText("authStatus", "Not signed in");
              show("loginBtn");
              hide("logoutBtn");
            }
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

          const refreshJob = async (jobId) => {
            const response = await fetch(`/jobs/${jobId}`, { headers: authHeaders() });
            if (!response.ok) {
              setText("jobStatus", "Failed to load job");
              return null;
            }
            const job = await response.json();
            setText("jobJson", JSON.stringify(job, null, 2));
            setText("jobStatus", `Status: ${job.status}`);
            setText("jobError", job.error_message || "");
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
            startPolling(job.job_id);
          });

          document.getElementById("acceptReview").addEventListener("click", async () => {
            const job = JSON.parse(document.getElementById("jobJson").textContent);
            const payload = { credentials: readCredentials() };
            const response = await fetch(`/jobs/${job.job_id}/review/accept`, {
              method: "POST",
              headers: authHeaders(),
              body: JSON.stringify(payload),
            });
            const updated = await response.json();
            setText("jobJson", JSON.stringify(updated, null, 2));
            setText("jobStatus", `Status: ${updated.status}`);
            startPolling(updated.job_id);
          });

          window.addEventListener("load", async () => {
            updateAuthUI();
            if (authConfig.prefillEnabled) {
              document.getElementById("cloudahoyUser").value = authConfig.prefill.cloudahoy_username || "";
              document.getElementById("cloudahoyPass").value = authConfig.prefill.cloudahoy_password || "";
              document.getElementById("flystoUser").value = authConfig.prefill.flysto_username || "";
              document.getElementById("flystoPass").value = authConfig.prefill.flysto_password || "";
            }
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
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html.replace("__AUTH_CONFIG__", json.dumps(config)))
