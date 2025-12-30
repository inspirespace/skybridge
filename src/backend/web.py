from __future__ import annotations

from fastapi.responses import HTMLResponse


def landing_page() -> HTMLResponse:
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
        </style>
      </head>
      <body>
        <h1>Skybridge Dev Web</h1>
        <p>Create a migration job, review the summary, then approve the import.</p>

        <fieldset>
          <legend>Local dev identity</legend>
          <label>User ID
            <input id="userId" placeholder="demo-user" />
          </label>
        </fieldset>

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

        <button id="createJob">Create job + run review</button>

        <div id="jobCard" class="card hidden">
          <h2>Job</h2>
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
          const headers = () => ({
            "Content-Type": "application/json",
            "X-User-Id": document.getElementById("userId").value || "demo-user",
          });

          const setText = (id, value) => {
            document.getElementById(id).textContent = value;
          };

          const show = (id) => document.getElementById(id).classList.remove("hidden");

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
              "<tr><th>ID</th><th>Date</th><th>Tail</th><th>Origin</th><th>Destination</th><th>Minutes</th></tr>",
              ...summary.flights.map(
                (flight) =>
                  `<tr><td>${flight.flight_id}</td><td>${flight.date}</td><td>${flight.tail_number || "-"}</td><td>${flight.origin || "-"}</td><td>${flight.destination || "-"}</td><td>${flight.flight_time_minutes || "-"}</td></tr>`
              ),
            ];
            document.getElementById("flightTable").innerHTML = rows.join("");
            show("reviewCard");
          };

          document.getElementById("createJob").addEventListener("click", async () => {
            const payload = {
              credentials: {
                cloudahoy_username: document.getElementById("cloudahoyUser").value,
                cloudahoy_password: document.getElementById("cloudahoyPass").value,
                flysto_username: document.getElementById("flystoUser").value,
                flysto_password: document.getElementById("flystoPass").value,
              },
            };

            const response = await fetch("/jobs", {
              method: "POST",
              headers: headers(),
              body: JSON.stringify(payload),
            });
            const job = await response.json();
            setText("jobJson", JSON.stringify(job, null, 2));
            show("jobCard");
            renderReview(job.review_summary);
          });

          document.getElementById("acceptReview").addEventListener("click", async () => {
            const job = JSON.parse(document.getElementById("jobJson").textContent);
            const response = await fetch(`/jobs/${job.job_id}/review/accept`, {
              method: "POST",
              headers: headers(),
            });
            const updated = await response.json();
            setText("jobJson", JSON.stringify(updated, null, 2));
            setText("reportJson", JSON.stringify(updated.import_report, null, 2));
            show("reportCard");
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)
