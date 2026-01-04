import * as React from "react";

import { Accordion } from "@/components/ui/accordion";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppFooter } from "@/components/app/AppFooter";
import { StaticPage } from "@/components/app/StaticPage";
import { SignInSection } from "@/components/app/SignInSection";
import { ConnectSection } from "@/components/app/ConnectSection";
import { ReviewSection } from "@/components/app/ReviewSection";
import { ImportSection } from "@/components/app/ImportSection";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import {
  acceptReview,
  createJob,
  deleteJob,
  downloadArtifactsZip,
  exchangeToken,
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
const RETENTION_DAYS = Number.parseInt(import.meta.env.VITE_RETENTION_DAYS ?? "7", 10);
const retentionDays = Number.isFinite(RETENTION_DAYS) ? RETENTION_DAYS : 7;

export default function App() {
  const pathname =
    typeof window !== "undefined"
      ? window.location.pathname.replace(/\/+$/, "") || "/"
      : "/";
  const staticPage =
    pathname === "/imprint" ? "imprint" : pathname === "/privacy" ? "privacy" : null;

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

  const clearLocalState = () => {
    localStorage.removeItem(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
  };

  const handleStartOverConfirm = async () => {
    if (!jobId) {
      clearLocalState();
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      await deleteJob(jobId, auth);
      clearLocalState();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      if ((err as Error & { status?: number }).status === 404) {
        clearLocalState();
        return;
      }
      setActionError({
        scope: "global",
        message: err instanceof Error ? err.message : "Failed to start over",
      });
    } finally {
      setActionLoading(false);
    }
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

  const handleDownloadFiles = async () => {
    if (!jobId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const blob = await downloadArtifactsZip(jobId, auth);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `skybridge-run-${jobId}.zip`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      if ((err as Error & { status?: number }).status === 404) {
        setActionError({
          scope: "import",
          message: "Files are no longer available (this run may have expired).",
        });
        return;
      }
      setActionError({
        scope: "import",
        message: err instanceof Error ? err.message : "Failed to download files",
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
      if ((err as Error & { status?: number }).status === 404) {
        localStorage.removeItem(JOB_ID_KEY);
        setJobId(null);
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
      ? "border-emerald-200/70 bg-emerald-50/40 dark:border-emerald-900/60 dark:bg-emerald-950/40"
      : reviewRunning
        ? "border-sky-200/70 bg-sky-50/40 dark:border-sky-900/60 dark:bg-sky-950/40"
        : "bg-background/70 dark:bg-background/80"
  );
  const reviewNoteClass = reviewComplete
    ? "text-emerald-700 dark:text-emerald-300"
    : reviewRunning
      ? "text-sky-700 dark:text-sky-300"
      : "text-muted-foreground";
  const importProgressCardClass = cn(
    "rounded-md border p-3 text-sm shadow-sm",
    importComplete
      ? "border-emerald-200/70 bg-emerald-50/40 dark:border-emerald-900/60 dark:bg-emerald-950/40"
      : importRunning
        ? "border-sky-200/70 bg-sky-50/40 dark:border-sky-900/60 dark:bg-sky-950/40"
        : "bg-background/70 dark:bg-background/80"
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

  if (staticPage) {
    return <StaticPage page={staticPage} retentionDays={retentionDays} />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-[#f7f9fc] to-[#eef3f8] text-[#1c2430] dark:bg-gradient-to-b dark:from-[#0b1120] dark:to-[#0f172a] dark:text-slate-100">
      <header className="sticky top-0 z-40 border-b border-[#d9e1ec] bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="absolute inset-x-0 top-0 h-1 bg-[#f1f4f8] dark:bg-slate-900" />
        <div className="container flex h-14 items-center justify-between sm:h-16">
          <div className="text-xs font-semibold tracking-[0.28em] text-[#5b6775] dark:text-slate-300">
            SKYBRIDGE
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            {flow.connected && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="outline" size="sm" disabled={!canStartOver(flow)}>
                    Start over
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Start a new import?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will delete the current run results. Download the files first if
                      you want to keep them.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={handleDownloadFiles}
                      disabled={!jobId || actionLoading}
                    >
                      Download files
                    </Button>
                  </div>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleStartOverConfirm}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      disabled={actionLoading}
                    >
                      Delete and start over
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
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

      <main className="container flex-1 pb-16 pt-5 lg:pb-8">
        <div className="mb-4 lg:hidden">
          <Card className="rounded-xl border border-[#d9e1ec] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-slate-800 dark:bg-slate-900 dark:shadow-none">
            <CardContent className="space-y-2 py-3">
              <div className="flex items-center justify-between text-xs text-[#5b6775]">
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
            <Card className="rounded-xl border border-[#d9e1ec] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-slate-800 dark:bg-slate-900 dark:shadow-none">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs uppercase tracking-[0.28em] text-[#5b6775]">
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
            <div className="overflow-hidden rounded-xl border border-[#d1dbea] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-slate-700 dark:bg-slate-900/90 dark:shadow-none">
            <Accordion
              type="single"
              collapsible
              value={openStep}
              onValueChange={handleAccordionChange}
            >
              <SignInSection
                allowed={allowedSteps.has("sign-in")}
                signedIn={flow.signedIn}
                onSignIn={handleSignIn}
                actionLoading={actionLoading}
                signInError={signInError}
                retentionDays={retentionDays}
              />

              <div className="border-t border-[#e3ebf5] dark:border-sky-900/60" />
              <ConnectSection
                allowed={allowedSteps.has("connect")}
                connected={flow.connected}
                signedIn={flow.signedIn}
                connectLocked={connectLocked}
                canConnect={canConnect}
                rangeIncomplete={rangeIncomplete}
                dateRange={dateRange}
                dateRangeLabel={dateRangeLabel}
                maxFlights={maxFlights}
                cloudahoyEmail={cloudahoyEmail}
                cloudahoyPassword={cloudahoyPassword}
                flystoEmail={flystoEmail}
                flystoPassword={flystoPassword}
                setCloudahoyEmail={setCloudahoyEmail}
                setCloudahoyPassword={setCloudahoyPassword}
                setFlystoEmail={setFlystoEmail}
                setFlystoPassword={setFlystoPassword}
                setDateRange={setDateRange}
                setMaxFlights={setMaxFlights}
                onConnectReview={handleConnectReview}
                actionLoading={actionLoading}
                connectError={connectError}
                onRefresh={refresh}
              />

              <div className="border-t border-[#e3ebf5] dark:border-sky-900/60" />
              <ReviewSection
                allowed={allowedSteps.has("review")}
                reviewComplete={reviewComplete}
                reviewRunning={reviewRunning}
                reviewApproved={reviewApproved}
                showReviewProgress={showReviewProgress}
                reviewProgressCardClass={reviewProgressCardClass}
                reviewStage={reviewStage}
                elapsed={elapsed}
                lastUpdate={lastUpdate}
                reviewProgress={reviewProgress}
                reviewNoteClass={reviewNoteClass}
                reviewSummary={reviewSummary}
                flights={flights}
                visibleFlights={visibleFlights}
                showAllFlights={showAllFlights}
                setShowAllFlights={setShowAllFlights}
                reviewError={reviewError}
                onRefresh={refresh}
                canApprove={canApprove}
                importRunning={importRunning}
                importComplete={importComplete}
                actionLoading={actionLoading}
                onApproveImport={handleApproveImport}
                canEditFiltersNow={canEditFiltersNow}
                onEditFilters={handleEditFilters}
                formatDate={formatDate}
              />

              <div className="border-t border-[#e3ebf5] dark:border-sky-900/60" />
              <ImportSection
                allowed={allowedSteps.has("import")}
                importComplete={importComplete}
                importRunning={importRunning}
                reviewComplete={reviewComplete}
                showImportProgress={showImportProgress}
                importProgressCardClass={importProgressCardClass}
                importStage={importStage}
                elapsed={elapsed}
                lastUpdate={lastUpdate}
                importProgress={importProgress}
                latestImportEvent={latestImportEvent ?? null}
                formatFlightId={formatFlightId}
                formatLastUpdate={formatLastUpdate}
                now={now}
                job={job}
                reviewSummaryMissing={reviewSummary?.missing_tail_numbers ?? 0}
                retentionDays={retentionDays}
                onDownloadFiles={handleDownloadFiles}
                onDeleteResults={handleDeleteResults}
                actionLoading={actionLoading}
                importError={importError}
                onRefresh={refresh}
              />
            </Accordion>
            </div>
          </section>
        </div>
      </main>

      <AppFooter />
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
        "relative flex items-center justify-between rounded-md border border-[#d9e1ec] bg-[#f8fafc] px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900",
        active ? "bg-[#eef3f8] dark:bg-slate-800" : "bg-[#f8fafc] dark:bg-slate-900"
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
