import * as React from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ImportResults } from "@/components/import-results";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  acceptReview,
  createJob,
  deleteJob,
  exchangeToken,
  fetchArtifact,
  listArtifacts,
  type FlightSummary,
  type AuthContext,
} from "@/api/client";
import {
  canApproveImport,
  canEditFilters,
  canStartOver,
  deriveFlowState,
  getOpenStep,
} from "@/state/flow";
import { useJobSnapshot } from "@/hooks/use-job-snapshot";

const USER_ID_KEY = "skybridge_user_id";
const JOB_ID_KEY = "skybridge_job_id";
const TOKEN_KEY = "skybridge_access_token";
const ID_TOKEN_KEY = "skybridge_id_token";
const CODE_VERIFIER_KEY = "skybridge_code_verifier";
const AUTH_STATE_KEY = "skybridge_auth_state";

const AUTH_MODE = import.meta.env.VITE_AUTH_MODE ?? "header";
const AUTH_ISSUER =
  import.meta.env.VITE_AUTH_ISSUER_URL ??
  import.meta.env.VITE_AUTH_BROWSER_ISSUER_URL ??
  "";
const AUTH_CLIENT_ID = import.meta.env.VITE_AUTH_CLIENT_ID ?? "skybridge-dev";
const AUTH_SCOPE = import.meta.env.VITE_AUTH_SCOPE ?? "openid profile email";
const AUTH_REDIRECT_PATH = import.meta.env.VITE_AUTH_REDIRECT_PATH ?? "/auth/callback";
const AUTH_PROVIDER_PARAM = import.meta.env.VITE_AUTH_PROVIDER_PARAM ?? "idp_hint";
const AUTH_LOGOUT_URL = import.meta.env.VITE_AUTH_LOGOUT_URL ?? "";

export default function App() {
  const [userId, setUserId] = React.useState<string | null>(() =>
    localStorage.getItem(USER_ID_KEY)
  );
  const [jobId, setJobId] = React.useState<string | null>(() =>
    localStorage.getItem(JOB_ID_KEY)
  );
  const [accessToken, setAccessToken] = React.useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [idToken, setIdToken] = React.useState<string | null>(() =>
    localStorage.getItem(ID_TOKEN_KEY)
  );
  const [showAllFlights, setShowAllFlights] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [actionLoading, setActionLoading] = React.useState(false);

  const [cloudahoyEmail, setCloudahoyEmail] = React.useState("");
  const [cloudahoyPassword, setCloudahoyPassword] = React.useState("");
  const [flystoEmail, setFlystoEmail] = React.useState("");
  const [flystoPassword, setFlystoPassword] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [maxFlights, setMaxFlights] = React.useState("");

  const isSignedIn = AUTH_MODE === "oidc" ? Boolean(accessToken) : Boolean(userId);
  const auth = React.useMemo<AuthContext>(
    () => (AUTH_MODE === "oidc" ? { token: accessToken } : { userId }),
    [accessToken, userId]
  );

  const { data: job, error: jobError, refresh } = useJobSnapshot(
    isSignedIn ? jobId : null,
    auth
  );

  const flow = React.useMemo(
    () => deriveFlowState(isSignedIn, job ?? null),
    [isSignedIn, job]
  );
  const openStep = React.useMemo(() => getOpenStep(flow), [flow]);

  const reviewSummary = job?.review_summary ?? null;
  const flights = reviewSummary?.flights ?? [];

  const reviewComplete = flow.reviewStatus === "complete";
  const reviewRunning = flow.reviewStatus === "running";
  const importRunning = flow.importStatus === "running";
  const importComplete = flow.importStatus === "complete";
  const reviewApproved = importRunning || importComplete;
  const errorMessage = actionError || jobError;

  React.useEffect(() => {
    if (AUTH_MODE !== "oidc") return;
    const url = new URL(window.location.href);
    if (!url.pathname.endsWith(AUTH_REDIRECT_PATH)) return;
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    if (!code || !state) return;
    const expectedState = sessionStorage.getItem(AUTH_STATE_KEY);
    const verifier = sessionStorage.getItem(CODE_VERIFIER_KEY);
    if (!verifier || !expectedState || expectedState !== state) {
      setActionError("Auth session expired. Please sign in again.");
      return;
    }
    const redirectUri = `${window.location.origin}${AUTH_REDIRECT_PATH}`;
    (async () => {
      setActionLoading(true);
      setActionError(null);
      try {
        const token = await exchangeToken({
          code,
          code_verifier: verifier,
          redirect_uri: redirectUri,
        });
        localStorage.setItem(TOKEN_KEY, token.access_token);
        setAccessToken(token.access_token);
        if (token.id_token) {
          localStorage.setItem(ID_TOKEN_KEY, token.id_token);
          setIdToken(token.id_token);
          const claims = parseJwt(token.id_token);
          if (claims?.email) {
            localStorage.setItem(USER_ID_KEY, claims.email);
            setUserId(claims.email);
          }
        }
        sessionStorage.removeItem(CODE_VERIFIER_KEY);
        sessionStorage.removeItem(AUTH_STATE_KEY);
        window.history.replaceState({}, document.title, "/");
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Auth failed");
      } finally {
        setActionLoading(false);
      }
    })();
  }, []);

  const connectLocked = flow.connected && flow.reviewStatus !== "idle";

  const startOidcLogin = async (provider?: string) => {
    if (!AUTH_ISSUER) {
      setActionError("Auth issuer is not configured.");
      return;
    }
    const redirectUri = `${window.location.origin}${AUTH_REDIRECT_PATH}`;
    const verifier = generateCodeVerifier();
    sessionStorage.setItem(CODE_VERIFIER_KEY, verifier);
    const challenge = await generateCodeChallenge(verifier);
    const state = generateState();
    sessionStorage.setItem(AUTH_STATE_KEY, state);
    const authUrl = new URL(`${AUTH_ISSUER.replace(/\\/$/, "")}/protocol/openid-connect/auth`);
    authUrl.searchParams.set("client_id", AUTH_CLIENT_ID);
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("scope", AUTH_SCOPE);
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("code_challenge", challenge);
    authUrl.searchParams.set("code_challenge_method", "S256");
    authUrl.searchParams.set("state", state);
    if (provider) {
      authUrl.searchParams.set(AUTH_PROVIDER_PARAM, provider);
    }
    window.location.assign(authUrl.toString());
  };

  const handleSignIn = () => {
    if (AUTH_MODE === "oidc") {
      startOidcLogin();
      return;
    }
    const nextUserId = "pilot@skybridge.dev";
    localStorage.setItem(USER_ID_KEY, nextUserId);
    setUserId(nextUserId);
    setActionError(null);
  };

  const handleConnectReview = async () => {
    if (!isSignedIn) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const payload = {
        credentials: {
          cloudahoy_username: cloudahoyEmail,
          cloudahoy_password: cloudahoyPassword,
          flysto_username: flystoEmail,
          flysto_password: flystoPassword,
        },
        start_date: startDate || null,
        end_date: endDate || null,
        max_flights: maxFlights ? Number(maxFlights) : null,
      };
      const createdJob = await createJob(payload, auth);
      localStorage.setItem(JOB_ID_KEY, createdJob.job_id);
      setJobId(createdJob.job_id);
      setShowAllFlights(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to start review");
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveImport = async () => {
    if (!isSignedIn || !jobId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await acceptReview(jobId, {
        credentials: {
          cloudahoy_username: cloudahoyEmail,
          cloudahoy_password: cloudahoyPassword,
          flysto_username: flystoEmail,
          flysto_password: flystoPassword,
        },
      }, auth);
      refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to start import");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEditFilters = () => {
    localStorage.removeItem(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
  };

  const handleStartOver = () => {
    localStorage.removeItem(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
  };

  const handleSignOut = () => {
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(JOB_ID_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ID_TOKEN_KEY);
    setUserId(null);
    setJobId(null);
    setAccessToken(null);
    setIdToken(null);
    setShowAllFlights(false);
    setActionError(null);
    if (AUTH_MODE === "oidc" && AUTH_LOGOUT_URL) {
      const url = new URL(AUTH_LOGOUT_URL);
      url.searchParams.set(
        "post_logout_redirect_uri",
        window.location.origin + "/"
      );
      window.location.assign(url.toString());
    }
  };

  const handleDownloadReport = async () => {
    if (!jobId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const artifacts = await listArtifacts(jobId, auth);
      const reportName = artifacts.artifacts.find((artifact) =>
        artifact.includes("import-report")
      );
      if (!reportName) {
        throw new Error("Import report not found yet.");
      }
      const payload = await fetchArtifact(jobId, reportName, auth);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = reportName;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to download report");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteResults = async () => {
    if (!jobId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await deleteJob(jobId, auth);
      localStorage.removeItem(JOB_ID_KEY);
      setJobId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to delete results");
    } finally {
      setActionLoading(false);
    }
  };

  const canConnect =
    Boolean(cloudahoyEmail) &&
    Boolean(cloudahoyPassword) &&
    Boolean(flystoEmail) &&
    Boolean(flystoPassword);

  const visibleFlights = showAllFlights ? flights : flights.slice(0, 3);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="text-sm font-semibold tracking-[0.3em]">SKYBRIDGE</div>
          <div className="flex items-center gap-4">
            {flow.connected && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleStartOver}
                disabled={!canStartOver(flow)}
              >
                Start over
              </Button>
            )}
            {flow.signedIn && (
              <Button variant="outline" size="sm" onClick={handleSignOut}>
                Sign out
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="container py-8">
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-[0.25em] text-muted-foreground">
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <StepStatus
                  label="1 · Sign in"
                  active={!flow.signedIn}
                  done={flow.signedIn}
                />
                <StepStatus
                  label="2 · Connect"
                  active={flow.signedIn && !flow.connected}
                  done={flow.connected}
                />
                <StepStatus
                  label="3 · Review"
                  active={flow.connected && !reviewComplete}
                  done={reviewComplete}
                />
                <StepStatus
                  label="4 · Import"
                  active={reviewComplete && !importComplete}
                  done={importComplete}
                />
              </CardContent>
            </Card>
          </aside>

          <section className="space-y-4">
            <Accordion type="single" collapsible value={openStep}>
              <AccordionItem value="sign-in">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>1 · Sign in</span>
                    <Badge variant="secondary">Required</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Sign in</CardTitle>
                      <CardDescription>
                        Skybridge imports your CloudAhoy flights into FlySto. You’ll
                        connect both accounts, review the summary, and approve the
                        import.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <Alert>
                        <AlertTitle>What you can expect</AlertTitle>
                        <AlertDescription>
                          <ul className="list-disc space-y-1 pl-5">
                            <li>
                              We import flights, times, routes, aircraft details, and
                              remarks.
                            </li>
                            <li>You can review everything before approving the import.</li>
                            <li>
                              Credentials are used only for this job and never stored.
                            </li>
                          </ul>
                        </AlertDescription>
                      </Alert>
                      <div className="flex flex-wrap gap-3">
                        <Button onClick={handleSignIn} disabled={flow.signedIn}>
                          Sign in with email
                        </Button>
                        <Button
                          variant="outline"
                          disabled={flow.signedIn}
                          onClick={() =>
                            AUTH_MODE === "oidc" ? startOidcLogin("google") : undefined
                          }
                        >
                          Continue with Google
                        </Button>
                        <Button
                          variant="outline"
                          disabled={flow.signedIn}
                          onClick={() =>
                            AUTH_MODE === "oidc" ? startOidcLogin("apple") : undefined
                          }
                        >
                          Continue with Apple
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="connect">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>2 · Connect accounts</span>
                    <Badge variant="outline">
                      {flow.signedIn ? "Required" : "Sign in required"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Connect accounts</CardTitle>
                      <CardDescription>
                        Enter CloudAhoy and FlySto credentials, then run the review.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <Alert variant="default">
                        <AlertTitle>Credentials</AlertTitle>
                        <AlertDescription>
                          Credentials are used only for this job and not stored.
                        </AlertDescription>
                      </Alert>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <div className="text-sm font-medium">CloudAhoy</div>
                          <div className="space-y-2">
                            <Label htmlFor="cloudahoy-email">Email</Label>
                            <Input
                              id="cloudahoy-email"
                              placeholder="Email"
                              disabled={connectLocked}
                              value={cloudahoyEmail}
                              onChange={(event) =>
                                setCloudahoyEmail(event.target.value)
                              }
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="cloudahoy-password">Password</Label>
                            <Input
                              id="cloudahoy-password"
                              type="password"
                              placeholder="Password"
                              disabled={connectLocked}
                              value={cloudahoyPassword}
                              onChange={(event) =>
                                setCloudahoyPassword(event.target.value)
                              }
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="text-sm font-medium">FlySto</div>
                          <div className="space-y-2">
                            <Label htmlFor="flysto-email">Email</Label>
                            <Input
                              id="flysto-email"
                              placeholder="Email"
                              disabled={connectLocked}
                              value={flystoEmail}
                              onChange={(event) => setFlystoEmail(event.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="flysto-password">Password</Label>
                            <Input
                              id="flysto-password"
                              type="password"
                              placeholder="Password"
                              disabled={connectLocked}
                              value={flystoPassword}
                              onChange={(event) => setFlystoPassword(event.target.value)}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="space-y-2">
                          <Label htmlFor="start-date">Start date</Label>
                          <Input
                            id="start-date"
                            placeholder="YYYY-MM-DD"
                            disabled={connectLocked}
                            value={startDate}
                            onChange={(event) => setStartDate(event.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="end-date">End date</Label>
                          <Input
                            id="end-date"
                            placeholder="YYYY-MM-DD"
                            disabled={connectLocked}
                            value={endDate}
                            onChange={(event) => setEndDate(event.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="max-flights">Max flights to import</Label>
                          <Input
                            id="max-flights"
                            placeholder="50"
                            disabled={connectLocked}
                            value={maxFlights}
                            onChange={(event) => setMaxFlights(event.target.value)}
                          />
                        </div>
                      </div>

                      <p className="text-xs text-muted-foreground">
                        Leave empty to import all available flights. Caps the total number
                        of flights that will be imported.
                      </p>

                      {errorMessage && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{errorMessage}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}

                      <Button
                        onClick={handleConnectReview}
                        disabled={connectLocked || !canConnect || actionLoading}
                      >
                        Connect and review
                      </Button>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="review">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>3 · Review</span>
                    <Badge
                      variant={reviewApproved ? "success" : reviewComplete ? "secondary" : "outline"}
                    >
                      {reviewApproved
                        ? "Approved"
                        : reviewComplete
                          ? "Review ready"
                          : "Connect accounts to continue"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Review</CardTitle>
                      <CardDescription>
                        Flights are fetched first so you can verify the summary before
                        importing.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-md border bg-muted/40 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">
                            {reviewComplete
                              ? "Review complete"
                              : reviewRunning
                                ? "Review running"
                                : "Review idle"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            Last update: just now
                          </span>
                        </div>
                        <div className="mt-3">
                          <Progress value={reviewComplete ? 100 : reviewRunning ? 60 : 5} />
                        </div>
                        <div className="mt-3 text-xs text-emerald-700">
                          Flights are fetched from CloudAhoy first so you can check them
                          before running the actual import.
                        </div>
                      </div>
                      {reviewComplete && reviewSummary && (
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">
                            Flights: {reviewSummary.flight_count}
                          </Badge>
                          <Badge variant="secondary">
                            Hours: {reviewSummary.total_hours}
                          </Badge>
                          <Badge variant="warning">
                            Registration missing: {reviewSummary.missing_tail_numbers}
                          </Badge>
                        </div>
                      )}
                      {reviewComplete && (
                        <div className="overflow-x-auto">
                          <Table className="min-w-[720px]">
                            <TableHeader>
                              <TableRow>
                                <TableHead>Status</TableHead>
                                <TableHead>Flight ID</TableHead>
                                <TableHead>Date</TableHead>
                                <TableHead>Registration</TableHead>
                                <TableHead>Origin</TableHead>
                                <TableHead>Destination</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {visibleFlights.map((flight) => (
                                <TableRow key={flight.flight_id}>
                                  <TableCell>
                                    <Badge
                                      variant={
                                        flight.tail_number ? "success" : "warning"
                                      }
                                    >
                                      {flight.tail_number ? "OK" : "Needs review"}
                                    </Badge>
                                  </TableCell>
                                  <TableCell>{formatFlightId(flight)}</TableCell>
                                  <TableCell>{formatDate(flight.date)}</TableCell>
                                  <TableCell>{flight.tail_number ?? "—"}</TableCell>
                                  <TableCell>{flight.origin ?? "—"}</TableCell>
                                  <TableCell>{flight.destination ?? "—"}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      )}
                      {reviewComplete && flights.length > 3 && !showAllFlights && (
                        <Button
                          variant="link"
                          className="h-auto px-0 text-sm text-muted-foreground"
                          onClick={() => setShowAllFlights(true)}
                        >
                          Show more flights
                        </Button>
                      )}
                      {reviewComplete && flights.length > 3 && showAllFlights && (
                        <div className="text-sm text-muted-foreground">
                          All flights shown
                        </div>
                      )}
                      {errorMessage && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{errorMessage}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}
                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={handleApproveImport}
                          disabled={
                            !canApproveImport(flow) ||
                            importRunning ||
                            importComplete ||
                            actionLoading
                          }
                        >
                          Accept and start import
                        </Button>
                        <Button
                          variant="outline"
                          onClick={handleEditFilters}
                          disabled={!canEditFilters(flow)}
                        >
                          Edit import filters
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="import">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>4 · Import</span>
                    <Badge variant={importComplete ? "success" : "outline"}>
                      {importComplete ? "Completed" : "Approve review to continue"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Import</CardTitle>
                      <CardDescription>
                        Import runs after approval and produces a report summary.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-md border bg-muted/40 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">
                            {importComplete
                              ? "Import complete"
                              : importRunning
                                ? "Import running"
                                : "Import idle"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            Last update: just now
                          </span>
                        </div>
                        <div className="mt-3">
                          <Progress
                            value={importComplete ? 100 : importRunning ? 65 : 5}
                          />
                        </div>
                      </div>
                      {importComplete && job?.import_report && (
                        <ImportResults
                          imported={job.import_report.imported_count}
                          skipped={job.import_report.skipped_count}
                          failed={job.import_report.failed_count}
                          registrationMissing={
                            reviewSummary?.missing_tail_numbers ?? 0
                          }
                        />
                      )}
                      {importComplete && (
                        <Alert>
                          <AlertTitle>Next steps</AlertTitle>
                          <AlertDescription>
                            Review your imported flights in FlySto, download the report for
                            your records, and keep this page bookmarked while results are
                            retained.
                          </AlertDescription>
                        </Alert>
                      )}
                      {errorMessage && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{errorMessage}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}
                      {importComplete && (
                        <div className="flex flex-wrap gap-3">
                          <Button onClick={handleDownloadReport} disabled={actionLoading}>
                            Download report
                          </Button>
                          <Button
                            variant="destructive"
                            onClick={handleDeleteResults}
                            disabled={actionLoading}
                          >
                            Delete results now
                          </Button>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </section>
        </div>
      </main>

      <footer className="border-t bg-background/80">
        <div className="container flex flex-wrap items-center justify-between gap-3 py-6 text-sm text-muted-foreground">
          <div>© 2026 Inspirespace e.U.</div>
          <div className="flex flex-wrap gap-4">
            <a className="hover:text-foreground" href="#">
              Imprint
            </a>
            <a className="hover:text-foreground" href="#">
              Privacy
            </a>
            <a className="hover:text-foreground" href="#">
              Support
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StepStatus({
  label,
  active,
  done,
}: {
  label: string;
  active?: boolean;
  done?: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
      <span className={active ? "font-semibold" : "font-medium"}>{label}</span>
      <Badge variant={done ? "success" : "outline"}>
        {done ? "Done" : active ? "Active" : "Locked"}
      </Badge>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return value.slice(0, 10);
}

function formatFlightId(flight: FlightSummary) {
  const id = flight.flight_id;
  if (!id) return "—";
  if (id.length <= 16) return id;
  return `...${id.slice(-12)}`;
}

function generateCodeVerifier() {
  const bytes = new Uint8Array(32);
  window.crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

async function generateCodeChallenge(verifier: string) {
  const data = new TextEncoder().encode(verifier);
  const digest = await window.crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}

function generateState() {
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

function base64UrlEncode(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function parseJwt(token: string) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = atob(normalized);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}
