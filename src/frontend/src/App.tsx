import * as React from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Progress } from "@/components/ui/progress";
import { ImportResults } from "@/components/import-results";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { Apple, Calendar as CalendarIcon, Check, Chrome, Mail } from "lucide-react";
import {
  acceptReview,
  createJob,
  deleteJob,
  exchangeToken,
  fetchArtifact,
  listArtifacts,
  type AuthContext,
} from "@/api/client";
import { canStartOver, deriveFlowState, getOpenStep } from "@/state/flow";
import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import type { DateRange } from "react-day-picker";

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
const AUTH_PROVIDER_PARAM = import.meta.env.VITE_AUTH_PROVIDER_PARAM ?? "kc_idp_hint";
const AUTH_LOGOUT_URL = import.meta.env.VITE_AUTH_LOGOUT_URL ?? "";
const DEV_PREFILL =
  import.meta.env.DEV && (import.meta.env.VITE_DEV_PREFILL_CREDENTIALS ?? "") === "1";
const DEV_CLOUD_AHOY_EMAIL = import.meta.env.VITE_CLOUD_AHOY_EMAIL ?? "";
const DEV_CLOUD_AHOY_PASSWORD = import.meta.env.VITE_CLOUD_AHOY_PASSWORD ?? "";
const DEV_FLYSTO_EMAIL = import.meta.env.VITE_FLYSTO_EMAIL ?? "";
const DEV_FLYSTO_PASSWORD = import.meta.env.VITE_FLYSTO_PASSWORD ?? "";

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
  const [actionError, setActionError] = React.useState<{
    scope: "sign-in" | "connect" | "review" | "import" | "global";
    message: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = React.useState(false);
  const didExchangeRef = React.useRef(false);

  const [cloudahoyEmail, setCloudahoyEmail] = React.useState("");
  const [cloudahoyPassword, setCloudahoyPassword] = React.useState("");
  const [flystoEmail, setFlystoEmail] = React.useState("");
  const [flystoPassword, setFlystoPassword] = React.useState("");
  const [dateRange, setDateRange] = React.useState<DateRange | undefined>(undefined);
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
  const [manualOpen, setManualOpen] = React.useState<string | undefined>(undefined);
  const openStep = React.useMemo(() => manualOpen ?? getOpenStep(flow), [flow, manualOpen]);

  const reviewSummary = job?.review_summary ?? null;
  const flights = reviewSummary?.flights ?? [];
  const importEvents = React.useMemo(
    () =>
      (job?.progress_log ?? [])
        .filter((event) => event.phase === "import")
        .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)),
    [job?.progress_log]
  );
  const latestImportEvent = importEvents[importEvents.length - 1];
  const hasImportEvents = importEvents.length > 0;

  const reviewComplete = flow.reviewStatus === "complete";
  const reviewRunning = flow.reviewStatus === "running";
  const importRunning = flow.importStatus === "running";
  const importComplete = flow.importStatus === "complete";
  const reviewApproved = importRunning || importComplete;
  const showReviewProgress = reviewRunning || reviewComplete;
  const showImportProgress = importRunning || importComplete;
  const [now, setNow] = React.useState(() => new Date());
  const signInError =
    actionError?.scope === "sign-in" || actionError?.scope === "global"
      ? actionError.message
      : null;
  const connectError = flow.signedIn
    ? actionError?.scope === "connect" || actionError?.scope === "global"
      ? actionError.message
      : jobError
    : null;
  const reviewError = flow.connected
    ? actionError?.scope === "review" || actionError?.scope === "global"
      ? actionError.message
      : jobError
    : null;
  const importError = flow.connected
    ? actionError?.scope === "import" || actionError?.scope === "global"
      ? actionError.message
      : jobError
    : null;

  const reviewProgress =
    typeof job?.progress_percent === "number" && job.status.startsWith("review")
      ? job.progress_percent
      : reviewComplete
        ? 100
        : reviewRunning
          ? 45
          : 0;
  const importProgress =
    typeof job?.progress_percent === "number" &&
    (job.status.startsWith("import") || job.status === "completed")
      ? job.progress_percent
      : importComplete
        ? 100
        : importRunning
          ? 55
          : 0;
  const reviewStage = job?.status?.startsWith("review")
    ? job?.progress_stage ?? (reviewComplete ? "Review ready" : "Review running")
    : reviewComplete
      ? "Review ready"
      : "Review running";
  const importStage = job?.status?.startsWith("import") || job?.status === "completed"
    ? job?.progress_stage ?? (importComplete ? "Import complete" : "Import running")
    : importComplete
      ? "Import complete"
      : "Import running";
  React.useEffect(() => {
    if (!reviewRunning && !importRunning) return;
    const interval = window.setInterval(() => setNow(new Date()), 15000);
    return () => window.clearInterval(interval);
  }, [reviewRunning, importRunning]);

  const elapsed = formatElapsed(
    job?.created_at,
    reviewRunning || importRunning ? now.toISOString() : job?.updated_at
  );
  const lastUpdate = formatLastUpdate(job?.updated_at, now);

  React.useEffect(() => {
    if (AUTH_MODE !== "oidc") return;
    const url = new URL(window.location.href);
    const redirectPath = AUTH_REDIRECT_PATH.endsWith("/")
      ? AUTH_REDIRECT_PATH.slice(0, -1)
      : AUTH_REDIRECT_PATH;
    const currentPath = url.pathname.endsWith("/")
      ? url.pathname.slice(0, -1)
      : url.pathname;
    if (!currentPath.endsWith(redirectPath)) return;
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    if (!code || !state) return;
    if (didExchangeRef.current) return;
    const expectedState = sessionStorage.getItem(AUTH_STATE_KEY);
    const verifier = sessionStorage.getItem(CODE_VERIFIER_KEY);
    if (!verifier || !expectedState || expectedState !== state) {
      setActionError({
        scope: "sign-in",
        message: "Auth session expired. Please sign in again.",
      });
      return;
    }
    const redirectUri = `${window.location.origin}${AUTH_REDIRECT_PATH}`;
    (async () => {
      setActionLoading(true);
      setActionError(null);
      didExchangeRef.current = true;
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
        setActionError({
          scope: "sign-in",
          message: err instanceof Error ? err.message : "Auth failed",
        });
      } finally {
        setActionLoading(false);
      }
    })();
  }, []);

  React.useEffect(() => {
    if (!DEV_PREFILL) return;
    if (DEV_CLOUD_AHOY_EMAIL) setCloudahoyEmail(DEV_CLOUD_AHOY_EMAIL);
    if (DEV_CLOUD_AHOY_PASSWORD) setCloudahoyPassword(DEV_CLOUD_AHOY_PASSWORD);
    if (DEV_FLYSTO_EMAIL) setFlystoEmail(DEV_FLYSTO_EMAIL);
    if (DEV_FLYSTO_PASSWORD) setFlystoPassword(DEV_FLYSTO_PASSWORD);
  }, []);

  const connectLocked = flow.connected && flow.reviewStatus !== "idle";

  const allowedSteps = React.useMemo(() => {
    if (!flow.signedIn) return new Set(["sign-in"]);
    if (!flow.connected) return new Set(["sign-in", "connect"]);
    if (flow.importStatus !== "idle") {
      return new Set(["sign-in", "connect", "review", "import"]);
    }
    return new Set(["sign-in", "connect", "review"]);
  }, [flow]);

  React.useEffect(() => {
    if (!manualOpen) return;
    if (!allowedSteps.has(manualOpen)) {
      setManualOpen(undefined);
    }
  }, [allowedSteps, manualOpen]);

  const handleAccordionChange = (value?: string) => {
    if (!value) {
      setManualOpen(undefined);
      return;
    }
    if (!allowedSteps.has(value)) return;
    setManualOpen(value);
  };

  const startOidcLogin = async (provider?: string) => {
    setActionError(null);
    if (!AUTH_ISSUER) {
      setActionError({
        scope: "sign-in",
        message: "Auth issuer is not configured.",
      });
      return;
    }
    const redirectUri = `${window.location.origin}${AUTH_REDIRECT_PATH}`;
    const verifier = generateCodeVerifier();
    sessionStorage.setItem(CODE_VERIFIER_KEY, verifier);
    const challenge = await generateCodeChallenge(verifier);
    const state = generateState();
    sessionStorage.setItem(AUTH_STATE_KEY, state);
    const issuerBase = AUTH_ISSUER.endsWith("/")
      ? AUTH_ISSUER.slice(0, -1)
      : AUTH_ISSUER;
    const authUrl = new URL(`${issuerBase}/protocol/openid-connect/auth`);
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
        start_date: dateRange?.from ? formatISODate(dateRange.from) : null,
        end_date: dateRange?.to ? formatISODate(dateRange.to) : null,
        max_flights: maxFlights ? Number(maxFlights) : null,
      };
      const createdJob = await createJob(payload, auth);
      localStorage.setItem(JOB_ID_KEY, createdJob.job_id);
      setJobId(createdJob.job_id);
      setShowAllFlights(false);
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      setActionError({
        scope: "connect",
        message: err instanceof Error ? err.message : "Failed to start review",
      });
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
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      setActionError({
        scope: "review",
        message: err instanceof Error ? err.message : "Failed to start import",
      });
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
    sessionStorage.removeItem(CODE_VERIFIER_KEY);
    sessionStorage.removeItem(AUTH_STATE_KEY);
    setUserId(null);
    setJobId(null);
    setAccessToken(null);
    setIdToken(null);
    setShowAllFlights(false);
    setActionError(null);
    if (AUTH_MODE === "oidc" && AUTH_LOGOUT_URL && idToken) {
      const url = new URL(AUTH_LOGOUT_URL);
      url.searchParams.set("client_id", AUTH_CLIENT_ID);
      url.searchParams.set("id_token_hint", idToken);
      url.searchParams.set(
        "post_logout_redirect_uri",
        window.location.origin + AUTH_REDIRECT_PATH
      );
      window.location.assign(url.toString());
    }
  };

  const handleTokenExpired = React.useCallback(() => {
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(JOB_ID_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ID_TOKEN_KEY);
    sessionStorage.removeItem(CODE_VERIFIER_KEY);
    sessionStorage.removeItem(AUTH_STATE_KEY);
    setUserId(null);
    setJobId(null);
    setAccessToken(null);
    setIdToken(null);
    setShowAllFlights(false);
    setActionError(null);
  }, []);

  React.useEffect(() => {
    if (!jobError || !isSignedIn) return;
    const text = jobError.toLowerCase();
    if (text.includes("invalid token") || text.includes("signature") || text.includes("expired")) {
      handleTokenExpired();
    }
  }, [jobError, isSignedIn, handleTokenExpired]);

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
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      setActionError({
        scope: "import",
        message: err instanceof Error ? err.message : "Failed to download report",
      });
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
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      setActionError({
        scope: "import",
        message: err instanceof Error ? err.message : "Failed to delete results",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const canConnect =
    Boolean(cloudahoyEmail) &&
    Boolean(cloudahoyPassword) &&
    Boolean(flystoEmail) &&
    Boolean(flystoPassword);
  const rangeIncomplete = Boolean(dateRange?.from && !dateRange?.to);
  const dateRangeLabel = formatDateRange(dateRange);
  const reviewProgressCardClass = cn(
    "rounded-md border p-3 text-sm shadow-sm",
    reviewComplete
      ? "border-emerald-200/70 bg-emerald-50/40"
      : reviewRunning
        ? "border-sky-200/70 bg-sky-50/40"
        : "bg-background/70"
  );
  const reviewNoteClass = reviewComplete
    ? "text-emerald-700 dark:text-emerald-300"
    : reviewRunning
      ? "text-sky-700 dark:text-sky-300"
      : "text-muted-foreground";
  const importProgressCardClass = cn(
    "rounded-md border p-3 text-sm shadow-sm",
    importComplete
      ? "border-emerald-200/70 bg-emerald-50/40"
      : importRunning
        ? "border-sky-200/70 bg-sky-50/40"
        : "bg-background/70"
  );

  const visibleFlights = showAllFlights ? flights : flights.slice(0, 3);
  const canApprove =
    (job?.status === "review_ready" ||
      (job?.status === "failed" && reviewSummary && !hasImportEvents)) &&
    !actionLoading;
  const canEditFiltersNow =
    (job?.status === "review_ready" ||
      (job?.status === "failed" && reviewSummary && !hasImportEvents)) &&
    !actionLoading;

  const stepIndex = !flow.signedIn
    ? 1
    : !flow.connected
      ? 2
      : !reviewComplete
        ? 3
        : !importComplete
          ? 4
          : 4;
  const nextLabel = !flow.signedIn
    ? "Sign in"
    : !flow.connected
      ? "Connect"
      : !reviewComplete
        ? "Review"
        : !importComplete
          ? "Import"
          : "All steps completed";

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30 text-foreground">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-transparent via-primary/25 to-transparent" />
        <div className="container flex h-14 items-center justify-between sm:h-16">
          <div className="text-xs font-semibold tracking-[0.28em] text-muted-foreground">
            SKYBRIDGE
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
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

      <main className="container pb-16 pt-5 lg:pb-8">
        <div className="mb-4 lg:hidden">
          <Card className="rounded-lg border bg-card/90">
            <CardContent className="space-y-2 py-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Step {stepIndex} of 4</span>
                <span>
                  {nextLabel === "All steps completed"
                    ? nextLabel
                    : `Next: ${nextLabel}`}
                </span>
              </div>
              <Progress value={(stepIndex / 4) * 100} />
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          <aside className="hidden space-y-3 lg:sticky lg:top-20 lg:block lg:self-start">
            <Card className="rounded-lg border bg-card/90 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
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

          <section className="space-y-2.5">
            <Accordion
              type="single"
              collapsible
              value={openStep}
              onValueChange={handleAccordionChange}
            >
              <AccordionItem
                value="sign-in"
                className="rounded-lg border bg-card/90 px-4 shadow-sm data-[state=open]:border-primary/30 data-[state=open]:ring-1 data-[state=open]:ring-primary/10"
              >
                <AccordionTrigger disabled={!allowedSteps.has("sign-in")}>
                  <div className="flex w-full items-center justify-between">
                    <span>1 · Sign in</span>
                    <Badge variant={flow.signedIn ? "success" : "secondary"}>
                      {flow.signedIn ? "Signed in" : "Required"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-4 pb-4">
                    <p className="max-w-2xl text-base font-semibold leading-relaxed text-foreground">
                      Skybridge imports your CloudAhoy flights into FlySto. You’ll
                      connect both accounts, review the summary, and approve the
                      import.
                    </p>
                    <Alert className="border-sky-100 bg-sky-50/60 text-slate-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-slate-100">
                      <AlertTitle>What you can expect</AlertTitle>
                      <AlertDescription>
                        <ul className="list-disc space-y-1 pl-5">
                          <li>
                            Sign-in is required to identify your job, protect your
                            data, and let you resume later.
                          </li>
                          <li>
                            We import flights, times, routes, aircraft details, and
                            remarks. You can review everything before approving.
                          </li>
                          <li>
                            Credentials are used only for this job and never stored.
                            Results are retained for 10 days.
                          </li>
                        </ul>
                      </AlertDescription>
                    </Alert>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Button
                        className="w-full justify-start gap-2 shadow-sm"
                        onClick={handleSignIn}
                        disabled={flow.signedIn || actionLoading}
                      >
                        <Mail className="h-4 w-4" />
                        Sign in with email
                      </Button>
                      {AUTH_MODE === "oidc" ? (
                        <>
                          <Button
                            variant="outline"
                            className="w-full justify-start gap-2"
                            disabled={flow.signedIn || actionLoading}
                            onClick={() => startOidcLogin("google")}
                          >
                            <Chrome className="h-4 w-4" />
                            Continue with Google
                          </Button>
                          <Button
                            variant="outline"
                            className="w-full justify-start gap-2"
                            disabled={flow.signedIn || actionLoading}
                            onClick={() => startOidcLogin("apple")}
                          >
                            <Apple className="h-4 w-4" />
                            Continue with Apple
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button className="w-full justify-start gap-2" variant="outline" disabled>
                            <Chrome className="h-4 w-4" />
                            Continue with Google
                          </Button>
                          <Button className="w-full justify-start gap-2" variant="outline" disabled>
                            <Apple className="h-4 w-4" />
                            Continue with Apple
                          </Button>
                        </>
                      )}
                    </div>
                    {signInError && (
                      <Alert variant="destructive">
                        <AlertTitle>Sign-in failed</AlertTitle>
                        <AlertDescription>{signInError}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem
                value="connect"
                className={cn(
                  "rounded-lg border bg-card/90 px-4 shadow-sm data-[state=open]:border-primary/30 data-[state=open]:ring-1 data-[state=open]:ring-primary/10",
                  !allowedSteps.has("connect") && "border-dashed bg-muted/20"
                )}
              >
                <AccordionTrigger
                  disabled={!allowedSteps.has("connect")}
                  className={!allowedSteps.has("connect") ? "font-normal text-muted-foreground" : undefined}
                >
                  <div className="flex w-full items-center justify-between">
                    <span>2 · Connect accounts</span>
                    <Badge
                      variant={flow.connected ? "success" : "outline"}
                      className={!allowedSteps.has("connect") ? "border-dashed" : undefined}
                    >
                      {flow.connected ? "Connected" : flow.signedIn ? "Required" : "Sign in required"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-4 pb-4">
                      <p className="text-sm text-muted-foreground">
                        Enter CloudAhoy and FlySto credentials, then run the review.
                      </p>
                      <Alert variant="default" className="bg-muted/40">
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

                      <Separator className="my-1" />

                      <div className="rounded-md border bg-background/60 p-3">
                        <div className="space-y-3">
                          <div className="text-sm font-semibold">Import filters</div>
                          <div className="grid gap-3 md:grid-cols-3">
                            <div className="space-y-2 md:col-span-2">
                              <Label>Date range</Label>
                              <Popover>
                                <PopoverTrigger asChild>
                                  <Button
                                    variant="outline"
                                    className={cn(
                                      "w-full justify-start text-left font-normal",
                                      !dateRange?.from && "text-muted-foreground"
                                    )}
                                    disabled={connectLocked}
                                  >
                                    <CalendarIcon className="mr-2 h-4 w-4" />
                                    {dateRangeLabel}
                                  </Button>
                                </PopoverTrigger>
                                <PopoverContent className="w-auto p-3" align="start">
                                  <Calendar
                                    mode="range"
                                    numberOfMonths={1}
                                    selected={dateRange}
                                    onSelect={setDateRange}
                                    disabled={connectLocked}
                                  />
                                  <div className="mt-3 flex items-center justify-between">
                                    <div className="text-xs text-muted-foreground">
                                      Leave empty to import all available flights.
                                    </div>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => setDateRange(undefined)}
                                      disabled={connectLocked || !dateRange?.from}
                                    >
                                      Clear dates
                                    </Button>
                                  </div>
                                  {rangeIncomplete && (
                                    <div className="mt-2 text-xs text-amber-600">
                                      Select an end date or clear the range.
                                    </div>
                                  )}
                                </PopoverContent>
                              </Popover>
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="max-flights">Max flights to import</Label>
                              <Input
                                id="max-flights"
                                type="number"
                                min={1}
                                step={1}
                                inputMode="numeric"
                                placeholder="50"
                                disabled={connectLocked}
                                value={maxFlights}
                                onChange={(event) => {
                                  const next = event.target.value;
                                  if (next === "" || /^[0-9]+$/.test(next)) {
                                    setMaxFlights(next);
                                  }
                                }}
                              />
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Caps the total number of flights that will be imported.
                          </p>
                        </div>
                      </div>

                      {connectError && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{connectError}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}

                      <Button
                        onClick={handleConnectReview}
                        disabled={connectLocked || !canConnect || rangeIncomplete || actionLoading}
                        className="shadow-sm"
                      >
                        Connect and review
                      </Button>
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem
                value="review"
                className={cn(
                  "rounded-lg border bg-card/90 px-4 shadow-sm data-[state=open]:border-primary/30 data-[state=open]:ring-1 data-[state=open]:ring-primary/10",
                  !allowedSteps.has("review") && "border-dashed bg-muted/20"
                )}
              >
                <AccordionTrigger
                  disabled={!allowedSteps.has("review")}
                  className={!allowedSteps.has("review") ? "font-normal text-muted-foreground" : undefined}
                >
                  <div className="flex w-full items-center justify-between">
                    <span>3 · Review</span>
                    <Badge
                      variant={reviewComplete ? "success" : reviewRunning ? "active" : "outline"}
                      className={!allowedSteps.has("review") ? "border-dashed" : undefined}
                    >
                      {reviewApproved
                        ? "Approved"
                        : reviewComplete
                          ? "Review ready"
                          : reviewRunning
                            ? "Review running"
                            : "Connect accounts to continue"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 pb-4">
                      {showReviewProgress && (
                        <div className={reviewProgressCardClass}>
                          <div className="flex items-center justify-between">
                            <span
                              className={`font-medium ${
                                reviewComplete
                                  ? "text-emerald-800 dark:text-emerald-300"
                                  : reviewRunning
                                    ? "text-sky-800 dark:text-sky-300"
                                    : ""
                              }`}
                            >
                              {reviewStage}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {elapsed ? `Elapsed: ${elapsed} · ` : ""}Last update: {lastUpdate}
                            </span>
                          </div>
                          <div className="mt-3">
                            <Progress
                              value={reviewProgress}
                              className={
                                reviewComplete
                                  ? "bg-emerald-100"
                                  : reviewRunning
                                    ? "bg-sky-100"
                                    : undefined
                              }
                              indicatorClassName={
                                reviewComplete
                                  ? "bg-emerald-600"
                                  : reviewRunning
                                    ? "bg-sky-600"
                                    : undefined
                              }
                            />
                          </div>
                          <div className={cn("mt-3 text-xs", reviewNoteClass)}>
                            Flights are fetched from CloudAhoy first so you can check them
                            before running the actual import.
                          </div>
                        </div>
                      )}
                      {reviewComplete && reviewSummary && (
                        <div className="flex flex-wrap gap-2 rounded-md border bg-muted/20 p-2">
                          <Badge variant="secondary">
                            <span className="tabular-nums">
                              Flights: {reviewSummary.flight_count}
                            </span>
                          </Badge>
                          <Badge variant="secondary">
                            <span className="tabular-nums">
                              Hours: {reviewSummary.total_hours}
                            </span>
                          </Badge>
                          <Badge
                            variant={
                              reviewSummary.missing_tail_numbers > 0
                                ? "warning"
                                : "secondary"
                            }
                          >
                            <span className="tabular-nums">
                              Registration missing: {reviewSummary.missing_tail_numbers}
                            </span>
                          </Badge>
                        </div>
                      )}
                      {reviewComplete && (
                        <div className="overflow-x-auto rounded-md border bg-background/70">
                          <Table className="min-w-[720px]">
                            <TableHeader className="bg-muted/40">
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
                              {visibleFlights.map((flight, index) => (
                                <TableRow
                                  key={flight.flight_id}
                                  className={index % 2 === 0 ? "bg-muted/40" : undefined}
                                >
                                  <TableCell>
                                    <Badge
                                      variant={flight.tail_number ? "success" : "warning"}
                                      className="min-w-[110px] justify-center"
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
                      {reviewError && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{reviewError}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button
                          onClick={handleApproveImport}
                          disabled={
                            !canApprove || importRunning || importComplete || actionLoading
                          }
                          className="shadow-sm"
                        >
                          Accept and start import
                        </Button>
                        {canEditFiltersNow && (
                          <Button variant="outline" onClick={handleEditFilters}>
                            Edit import filters
                          </Button>
                        )}
                      </div>
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem
                value="import"
                className={cn(
                  "rounded-lg border bg-card/90 px-4 shadow-sm data-[state=open]:border-primary/30 data-[state=open]:ring-1 data-[state=open]:ring-primary/10",
                  !allowedSteps.has("import") && "border-dashed bg-muted/20"
                )}
              >
                <AccordionTrigger
                  disabled={!allowedSteps.has("import")}
                  className={!allowedSteps.has("import") ? "font-normal text-muted-foreground" : undefined}
                >
                  <div className="flex w-full items-center justify-between">
                    <span>4 · Import</span>
                    <Badge
                      variant={
                        importComplete
                          ? "success"
                          : importRunning
                            ? "active"
                            : reviewComplete
                              ? "secondary"
                              : "outline"
                      }
                      className={!allowedSteps.has("import") ? "border-dashed" : undefined}
                    >
                      {importComplete
                        ? "Completed"
                        : importRunning
                          ? "Import running"
                          : reviewComplete
                            ? "Ready to import"
                            : "Approve review to continue"}
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-4 pb-4">
                      <p className="text-sm text-muted-foreground">
                        Import runs after approval and produces a report summary.
                      </p>
                      {showImportProgress && (
                        <div className={importProgressCardClass}>
                          <div className="flex items-center justify-between">
                            <span
                              className={`font-medium ${
                                importComplete
                                  ? "text-emerald-800 dark:text-emerald-300"
                                  : importRunning
                                    ? "text-sky-800 dark:text-sky-300"
                                    : ""
                              }`}
                            >
                              {importStage}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {elapsed ? `Elapsed: ${elapsed} · ` : ""}Last update: {lastUpdate}
                            </span>
                          </div>
                          <div className="mt-3">
                            <Progress
                              value={importProgress}
                              className={
                                importComplete
                                  ? "bg-emerald-100"
                                  : importRunning
                                    ? "bg-sky-100"
                                    : undefined
                              }
                              indicatorClassName={
                                importComplete
                                  ? "bg-emerald-600"
                                  : importRunning
                                    ? "bg-sky-600"
                                    : undefined
                              }
                            />
                          </div>
                          {latestImportEvent && (
                            <div className="mt-2 text-xs text-muted-foreground">
                              {latestImportEvent.stage}
                              {latestImportEvent.flight_id
                                ? ` · ${formatFlightId({ flight_id: latestImportEvent.flight_id })}`
                                : ""}
                              {latestImportEvent.percent != null
                                ? ` · ${latestImportEvent.percent}%`
                                : ""}
                              {" · "}
                              {formatLastUpdate(latestImportEvent.created_at, now)}
                            </div>
                          )}
                        </div>
                      )}
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
                          <div className="mt-4 flex flex-wrap gap-3">
                            <Button asChild>
                              <a
                                href="https://www.flysto.net/logs"
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open FlySto
                              </a>
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="destructive">Delete results now</Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete import results?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    This removes the stored reports and review summary for this
                                    run. This action cannot be undone.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction
                                    onClick={handleDeleteResults}
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    disabled={actionLoading}
                                  >
                                    Delete results
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </Alert>
                      )}
                      {importError && (
                        <Alert variant="destructive">
                          <AlertTitle>Something went wrong</AlertTitle>
                          <AlertDescription>{importError}</AlertDescription>
                          <div className="mt-3">
                            <Button size="sm" variant="outline" onClick={refresh}>
                              Retry
                            </Button>
                          </div>
                        </Alert>
                      )}
                      {importComplete && (
                        <div className="flex flex-wrap gap-2">
                          <Button onClick={handleDownloadReport} disabled={actionLoading}>
                            Download report
                          </Button>
                        </div>
                      )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </section>
        </div>
      </main>

      <footer className="border-t bg-background/80">
        <div className="container flex flex-wrap items-center justify-between gap-3 pb-20 pt-6 text-sm text-muted-foreground lg:py-6">
          <div>© {new Date().getFullYear()} Inspirespace e.U.</div>
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
  const badgeVariant = done ? "success" : active ? "active" : "outline";
  const badgeClass =
    done || active ? "" : "border-dashed text-muted-foreground";
  const labelClass = active
    ? "font-semibold"
    : done
      ? "font-medium"
      : "font-medium text-muted-foreground";
  return (
    <div
      className={cn(
        "relative flex items-center justify-between rounded-md border px-3 py-2 text-sm",
        active ? "bg-muted/40" : "bg-transparent"
      )}
    >
      {active && (
        <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-0.5 rounded-full bg-primary/60" />
      )}
      <span className={cn(labelClass, active && "pl-2")}>{label}</span>
      <Badge variant={badgeVariant} className={cn("flex items-center gap-1", badgeClass)}>
        {done ? (
          <>
            <Check className="h-3 w-3" /> Done
          </>
        ) : active ? (
          "Active"
        ) : (
          "Locked"
        )}
      </Badge>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return value.slice(0, 10);
}

function formatFlightId(flight: { flight_id?: string | null }) {
  const id = flight.flight_id ?? "";
  if (!id) return "—";
  if (id.length <= 16) return id;
  return `...${id.slice(-12)}`;
}

function formatDateRange(range?: DateRange) {
  if (!range?.from && !range?.to) return "Any date";
  const formatter = new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  if (range.from && range.to) {
    return `${formatter.format(range.from)} – ${formatter.format(range.to)}`;
  }
  if (range.from) {
    return `From ${formatter.format(range.from)}`;
  }
  return "Any date";
}

function formatISODate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function formatElapsed(start?: string | null, end?: string | null) {
  if (!start || !end) return "";
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) return "";
  const diffMs = Math.max(0, endMs - startMs);
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "<1m";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const rem = mins % 60;
  return `${hours}h ${rem}m`;
}

function formatLastUpdate(value?: string | null, now: Date = new Date()) {
  if (!value) return "just now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "just now";
  const diffMs = Math.max(0, now.getTime() - parsed.getTime());
  const diffSec = Math.round(diffMs / 1000);
  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  return `${diffHr}h ago`;
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

function isAuthExpiredError(error: unknown) {
  if (!error) return false;
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const status = (error as Error & { status?: number }).status;
  const lower = message.toLowerCase();
  if (status === 401) return true;
  if (lower.includes("invalid token")) return true;
  if (lower.includes("signature") && lower.includes("expired")) return true;
  if (lower.includes("token") && lower.includes("expired")) return true;
  return false;
}
