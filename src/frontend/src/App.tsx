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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AppFooter } from "@/components/app/AppFooter";
import { ConnectSection } from "@/components/app/ConnectSection";
import { ReviewSection } from "@/components/app/ReviewSection";
import { ImportSection } from "@/components/app/ImportSection";
import { StepStatus } from "@/components/app/StepStatus";
import { ThemeToggle } from "@/components/theme-toggle";
import { navigateWithFade } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import {
  acceptReview,
  createJob,
  validateCredentials,
  listJobs,
  deleteJob,
  downloadArtifactsZip,
  type AuthContext,
} from "@/api/client";
import { canStartOver, deriveFlowState, getOpenStep } from "@/state/flow";
import { useJobSnapshot } from "@/hooks/use-job-snapshot";
import type { DateRange } from "react-day-picker";
import { Loader2, Mail, UserRound, ShieldCheck, ArrowRight } from "lucide-react";
import {
  formatDate,
  formatDateRange,
  formatFlightId,
  formatISODate,
  formatPhaseElapsed,
  formatPhaseLastUpdate,
  formatLastUpdate,
} from "@/lib/format";
import { isAuthExpiredError } from "@/lib/auth-helpers";
import { useOidcAuth } from "@/hooks/use-oidc-auth";
import { useFirebaseAuth } from "@/hooks/use-firebase-auth";

const USER_ID_KEY = "skybridge_user_id";
const JOB_ID_KEY = "skybridge_job_id";
const OPEN_STEP_KEY = "skybridge_open_step";
const FORCE_LOGIN_KEY = "skybridge_force_login";
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE ?? "header";
const AUTH_ISSUER =
  import.meta.env.VITE_AUTH_ISSUER_URL ??
  import.meta.env.VITE_AUTH_BROWSER_ISSUER_URL ??
  "";
const AUTH_CLIENT_ID = import.meta.env.VITE_AUTH_CLIENT_ID ?? "skybridge-dev";
const AUTH_SCOPE =
  import.meta.env.VITE_AUTH_SCOPE ?? "openid profile email offline_access";
const AUTH_REDIRECT_PATH = import.meta.env.VITE_AUTH_REDIRECT_PATH ?? "/app/auth/callback";
const AUTH_PROVIDER_PARAM = import.meta.env.VITE_AUTH_PROVIDER_PARAM ?? "kc_idp_hint";
const AUTH_LOGOUT_URL = import.meta.env.VITE_AUTH_LOGOUT_URL ?? "";
const FIREBASE_API_KEY = import.meta.env.VITE_FIREBASE_API_KEY ?? "";
const FIREBASE_AUTH_DOMAIN = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "";
const FIREBASE_PROJECT_ID = import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "";
const FIREBASE_APP_ID = import.meta.env.VITE_FIREBASE_APP_ID ?? "";
const FIREBASE_EMULATOR_HOST = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST ?? "";
const FIREBASE_USE_EMULATOR =
  (import.meta.env.VITE_FIREBASE_USE_EMULATOR ?? "") === "1";
const FIREBASE_ENABLE_GOOGLE =
  (import.meta.env.VITE_FIREBASE_ENABLE_GOOGLE ?? "") === "1";
const FIREBASE_ENABLE_APPLE =
  (import.meta.env.VITE_FIREBASE_ENABLE_APPLE ?? "") === "1";
const FIREBASE_ENABLE_FACEBOOK =
  (import.meta.env.VITE_FIREBASE_ENABLE_FACEBOOK ?? "") === "1";
const FIREBASE_ENABLE_MICROSOFT =
  (import.meta.env.VITE_FIREBASE_ENABLE_MICROSOFT ?? "") === "1";
const FIREBASE_ENABLE_GUEST =
  (import.meta.env.VITE_FIREBASE_ENABLE_GUEST ?? "") === "1";
const FIRESTORE_LISTEN_ENABLED =
  (import.meta.env.VITE_FIRESTORE_LISTEN ?? "") === "1";
const DEV_PREFILL =
  import.meta.env.DEV && (import.meta.env.VITE_DEV_PREFILL_CREDENTIALS ?? "") === "1";
const DEV_CLOUD_AHOY_EMAIL = import.meta.env.VITE_CLOUD_AHOY_EMAIL ?? "";
const DEV_CLOUD_AHOY_PASSWORD = import.meta.env.VITE_CLOUD_AHOY_PASSWORD ?? "";
const DEV_FLYSTO_EMAIL = import.meta.env.VITE_FLYSTO_EMAIL ?? "";
const DEV_FLYSTO_PASSWORD = import.meta.env.VITE_FLYSTO_PASSWORD ?? "";
const RETENTION_DAYS = Number.parseInt(import.meta.env.VITE_RETENTION_DAYS ?? "7", 10);
const retentionDays = Number.isFinite(RETENTION_DAYS) ? RETENTION_DAYS : 7;

const ProviderIcon = ({ name }: { name: string }) => {
  switch (name) {
    case "google":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/5">
          <svg aria-hidden viewBox="0 0 48 48" className="h-4 w-4">
            <path
              fill="#EA4335"
              d="M24 9.5c3.2 0 6 .9 8.2 2.7l6.1-6.1C34.7 2.6 29.7 0 24 0 14.6 0 6.5 5.4 2.4 13.2l7.3 5.7C11.4 13 17.1 9.5 24 9.5z"
            />
            <path
              fill="#4285F4"
              d="M46.1 24.5c0-1.6-.1-2.8-.4-4.1H24v7.8h12.5c-.5 2.7-2.1 5.1-4.7 6.7l7.2 5.6c4.2-3.9 6.6-9.6 6.6-16z"
            />
            <path
              fill="#FBBC05"
              d="M9.7 28.9c-1-2.7-1-5.7 0-8.4l-7.3-5.7c-3.1 6.2-3.1 13.6 0 19.8l7.3-5.7z"
            />
            <path
              fill="#34A853"
              d="M24 48c5.7 0 10.6-1.9 14.1-5.1l-7.2-5.6c-2 1.4-4.6 2.2-6.9 2.2-6.9 0-12.6-3.5-14.3-9.4l-7.3 5.7C6.5 42.6 14.6 48 24 48z"
            />
          </svg>
        </span>
      );
    case "apple":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-black text-white">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path
              fill="currentColor"
              d="M16.3 1.5c0 1-.4 2-1 2.7-.7.9-1.9 1.6-3 1.5-.1-1 .4-2 .9-2.7.7-.8 1.9-1.5 3.1-1.5ZM19.7 17.4c-.4.9-.6 1.3-1.1 2.1-.7 1-1.6 2.2-2.8 2.2-1.1 0-1.4-.7-2.9-.7-1.5 0-1.9.7-3 .7-1.2 0-2-1.1-2.7-2.1-1.5-2.2-2.6-6.1-1.1-8.8.8-1.4 2.2-2.3 3.7-2.3 1.2 0 2.3.8 3 .8.7 0 2.1-.9 3.5-.8.6 0 2.3.2 3.4 1.7-2.9 1.6-2.4 5.7 1 7.2Z"
            />
          </svg>
        </span>
      );
    case "facebook":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#1877F2] text-white">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path
              fill="currentColor"
              d="M22 12a10 10 0 1 0-11.6 9.9v-7H8v-2.9h2.4V9.8c0-2.4 1.4-3.7 3.6-3.7 1 0 2.1.2 2.1.2v2.3h-1.2c-1.2 0-1.6.7-1.6 1.5v1.9h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12Z"
            />
          </svg>
        </span>
      );
    case "microsoft":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/5">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path fill="#F25022" d="M1 1h10v10H1z" />
            <path fill="#7FBA00" d="M13 1h10v10H13z" />
            <path fill="#00A4EF" d="M1 13h10v10H1z" />
            <path fill="#FFB900" d="M13 13h10v10H13z" />
          </svg>
        </span>
      );
    case "email":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-sky-700">
          <Mail className="h-4 w-4" aria-hidden />
        </span>
      );
    case "guest":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-slate-700">
          <UserRound className="h-4 w-4" aria-hidden />
        </span>
      );
    default:
      return null;
  }
};

const AuthDivider = () => (
  <div className="relative my-3 flex items-center">
    <div className="h-px w-full bg-slate-200 dark:bg-slate-800" />
    <span className="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-xs uppercase tracking-[0.3em] text-slate-400 dark:bg-slate-950 dark:text-slate-600">
      Or
    </span>
  </div>
);

/** Render App component. */
export default function App() {
  const [jobId, setJobId] = React.useState<string | null>(() =>
    localStorage.getItem(JOB_ID_KEY)
  );
  const [headerUserId, setHeaderUserId] = React.useState<string | null>(() =>
    localStorage.getItem(USER_ID_KEY)
  );
  const [showAllFlights, setShowAllFlights] = React.useState(false);
  const [actionError, setActionError] = React.useState<{
    scope: "sign-in" | "connect" | "review" | "import" | "global";
    message: string;
  } | null>(null);
  const [actionNotice, setActionNotice] = React.useState<{
    scope: "sign-in" | "connect" | "review" | "import" | "global";
    message: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = React.useState(false);
  const [downloadLoading, setDownloadLoading] = React.useState(false);
  const {
    accessToken,
    startLogin: startOidcLogin,
    signOut: signOutOidc,
    clearAuth: clearOidcAuth,
  } = useOidcAuth({
    enabled: AUTH_MODE === "oidc",
    issuer: AUTH_ISSUER,
    clientId: AUTH_CLIENT_ID,
    scope: AUTH_SCOPE,
    redirectPath: AUTH_REDIRECT_PATH,
    providerParam: AUTH_PROVIDER_PARAM,
    logoutUrl: AUTH_LOGOUT_URL,
    onError: (message) => setActionError({ scope: "sign-in", message }),
    onLoadingChange: setActionLoading,
  });
  const {
    accessToken: firebaseToken,
    startLogin: startFirebaseLogin,
    startEmailLink: startFirebaseEmailLink,
    isAnonymous: firebaseAnonymous,
    emulatorProvider: firebaseEmulatorProvider,
    emulatorReady: firebaseEmulatorReady,
    signOut: signOutFirebase,
    clearAuth: clearFirebaseAuth,
  } = useFirebaseAuth({
    enabled: AUTH_MODE === "firebase",
    apiKey: FIREBASE_API_KEY,
    authDomain: FIREBASE_AUTH_DOMAIN,
    projectId: FIREBASE_PROJECT_ID,
    appId: FIREBASE_APP_ID || undefined,
    emulatorHost: FIREBASE_EMULATOR_HOST || undefined,
    useEmulator: FIREBASE_USE_EMULATOR,
    onError: (message) => setActionError({ scope: "sign-in", message }),
    onLoadingChange: setActionLoading,
  });
  const [showAuthDialog, setShowAuthDialog] = React.useState(false);
  const [emailAddress, setEmailAddress] = React.useState("");
  const [emailLinkNotice, setEmailLinkNotice] = React.useState<string | null>(null);
  const [emailLinkUrl, setEmailLinkUrl] = React.useState<string | null>(null);

  const [cloudahoyEmail, setCloudahoyEmail] = React.useState("");
  const [cloudahoyPassword, setCloudahoyPassword] = React.useState("");
  const [flystoEmail, setFlystoEmail] = React.useState("");
  const [flystoPassword, setFlystoPassword] = React.useState("");
  const [dateRange, setDateRange] = React.useState<DateRange | undefined>(undefined);
  const [maxFlights, setMaxFlights] = React.useState("");

  const activeAccessToken = AUTH_MODE === "firebase" ? firebaseToken : accessToken;
  const isSignedIn =
    AUTH_MODE === "oidc" || AUTH_MODE === "firebase"
      ? Boolean(activeAccessToken)
      : Boolean(headerUserId);
  const isAnonymous =
    AUTH_MODE === "firebase" &&
    firebaseAnonymous &&
    !(FIREBASE_USE_EMULATOR && firebaseEmulatorProvider && firebaseEmulatorProvider !== "anonymous");
  const auth = React.useMemo<AuthContext>(
    () =>
      AUTH_MODE === "oidc" || AUTH_MODE === "firebase"
        ? { token: activeAccessToken }
        : { userId: headerUserId },
    [activeAccessToken, headerUserId]
  );

  const {
    data: job,
    error: jobError,
    refresh,
    listenerFailed,
    listenerActive,
  } = useJobSnapshot(
    isSignedIn ? jobId : null,
    auth
  );

  const flow = React.useMemo(
    () => deriveFlowState(isSignedIn, job ?? null),
    [isSignedIn, job]
  );
  const [manualOpen, setManualOpen] = React.useState<string | undefined>(() =>
    typeof window !== "undefined" ? localStorage.getItem(OPEN_STEP_KEY) ?? undefined : undefined
  );
  const backendResetCheckRef = React.useRef(false);
  const openStep = React.useMemo(() => {
    if (flow.importStatus === "running" || flow.importStatus === "complete") return "import";
    if (flow.reviewStatus === "running") return "review";
    if (!flow.connected) return manualOpen ?? "connect";
    return manualOpen ?? getOpenStep(flow);
  }, [flow, manualOpen]);

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
  const jobErrorStatus = (jobError as Error & { status?: number })?.status;
  const jobErrorMessage =
    jobError && !isAuthExpiredError(jobError)
      ? jobErrorStatus && [502, 503, 504].includes(jobErrorStatus)
        ? null
        : jobError.message
      : null;
  const jobFailureMessage =
    job?.status === "failed" ? job.error_message ?? "Job failed." : null;
  const reviewFailureMessage = !hasImportEvents ? jobFailureMessage : null;
  const importFailureMessage = hasImportEvents ? jobFailureMessage : null;
  const showLiveUpdatesNotice =
    AUTH_MODE === "firebase" && FIRESTORE_LISTEN_ENABLED && flow.signedIn;
  const authButtonsDisabled =
    actionLoading || (AUTH_MODE === "firebase" && FIREBASE_USE_EMULATOR && !firebaseEmulatorReady);
  const signInError =
    actionError?.scope === "sign-in" || actionError?.scope === "global"
      ? actionError.message
      : null;
  const connectError = flow.signedIn
    ? actionError?.scope === "connect" || actionError?.scope === "global"
      ? actionError.message
      : jobErrorMessage
    : null;
  const reviewError = flow.connected
    ? actionError?.scope === "review" || actionError?.scope === "global"
      ? actionError.message
      : reviewFailureMessage ?? jobErrorMessage
    : null;
  const importError = flow.connected
    ? actionError?.scope === "import" || actionError?.scope === "global"
      ? actionError.message
      : importFailureMessage ?? jobErrorMessage
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

  const reviewElapsed = formatPhaseElapsed(
    job?.progress_log,
    "review",
    now,
    reviewRunning
  );
  const importElapsed = formatPhaseElapsed(
    job?.progress_log,
    "import",
    now,
    importRunning
  );
  const reviewLastUpdate = formatPhaseLastUpdate(job?.progress_log, "review", now);
  const importLastUpdate = formatPhaseLastUpdate(job?.progress_log, "import", now);

  React.useEffect(() => {
    if (!DEV_PREFILL) return;
    if (DEV_CLOUD_AHOY_EMAIL) setCloudahoyEmail(DEV_CLOUD_AHOY_EMAIL);
    if (DEV_CLOUD_AHOY_PASSWORD) setCloudahoyPassword(DEV_CLOUD_AHOY_PASSWORD);
    if (DEV_FLYSTO_EMAIL) setFlystoEmail(DEV_FLYSTO_EMAIL);
    if (DEV_FLYSTO_PASSWORD) setFlystoPassword(DEV_FLYSTO_PASSWORD);
  }, []);

  const connectLocked = flow.connected && flow.reviewStatus !== "idle";

  const allowedSteps = React.useMemo(() => {
    if (!flow.signedIn) return new Set<string>();
    if (!flow.connected) return new Set(["connect"]);
    if (flow.importStatus !== "idle") {
      return new Set(["connect", "review", "import"]);
    }
    return new Set(["connect", "review"]);
  }, [flow]);

  React.useEffect(() => {
    if (!manualOpen) return;
    if (!allowedSteps.has(manualOpen)) {
      setManualOpen(undefined);
    }
  }, [allowedSteps, manualOpen]);

  React.useEffect(() => {
    if (!isSignedIn) {
      localStorage.removeItem(OPEN_STEP_KEY);
      return;
    }
    if (openStep) {
      localStorage.setItem(OPEN_STEP_KEY, openStep);
    }
  }, [isSignedIn, openStep]);

  React.useEffect(() => {
    if (!flow.signedIn) return;
    if (!flow.connected) {
      if (!manualOpen && !jobId) {
        setManualOpen("connect");
      }
      return;
    }
    if (flow.importStatus === "running" || flow.importStatus === "complete") {
      setManualOpen("import");
      return;
    }
    if (flow.reviewStatus === "running") {
      setManualOpen("review");
    }
  }, [flow.connected, flow.importStatus, flow.reviewStatus, flow.signedIn, jobId, manualOpen]);

  /** Handle handleAccordionChange. */
  const handleAccordionChange = (value?: string) => {
    if (!value) {
      setManualOpen(undefined);
      return;
    }
    if (
      (flow.importStatus === "running" || flow.importStatus === "complete") &&
      value !== "import"
    ) {
      return;
    }
    if (flow.reviewStatus === "running" && value !== "review") return;
    if (!allowedSteps.has(value)) return;
    setManualOpen(value);
  };

  /** Handle handleSignIn. */
  const handleSignIn = React.useCallback(() => {
    setActionError(null);
    if (AUTH_MODE === "oidc") {
      startOidcLogin();
      return;
    }
    if (AUTH_MODE === "firebase") {
      setShowAuthDialog(true);
      return;
    }
    const nextUserId = "pilot@skybridge.dev";
    localStorage.setItem(USER_ID_KEY, nextUserId);
    setHeaderUserId(nextUserId);
    setActionError(null);
    const stored = localStorage.getItem(OPEN_STEP_KEY) ?? undefined;
    setManualOpen(stored ?? "connect");
  }, [startOidcLogin, startFirebaseLogin, setHeaderUserId, setManualOpen]);

  const handleFirebaseLogin = React.useCallback(
    (provider: Parameters<typeof startFirebaseLogin>[0], options?: Parameters<typeof startFirebaseLogin>[1]) => {
      setActionError(null);
      const enabled =
        provider === "google"
          ? FIREBASE_ENABLE_GOOGLE
          : provider === "apple"
            ? FIREBASE_ENABLE_APPLE
            : provider === "facebook"
              ? FIREBASE_ENABLE_FACEBOOK
              : provider === "microsoft"
                ? FIREBASE_ENABLE_MICROSOFT
                : provider === "anonymous"
                  ? FIREBASE_ENABLE_GUEST
                  : false;
      if (!enabled) {
        setActionError({
          scope: "sign-in",
          message: "This sign-in option is disabled. Use the email link instead.",
        });
        return;
      }
      void startFirebaseLogin(provider, options);
    },
    [startFirebaseLogin]
  );

  const handleEmailLink = React.useCallback(async () => {
    setActionError(null);
    setEmailLinkNotice(null);
    setEmailLinkUrl(null);
    const email = emailAddress.trim();
    if (!email) {
      setActionError({ scope: "sign-in", message: "Enter a valid email address." });
      return;
    }
    const link = await startFirebaseEmailLink(email);
    setEmailLinkNotice(`We sent a sign-in link to ${email}.`);
    if (link) {
      setEmailLinkUrl(link);
    }
  }, [emailAddress, startFirebaseEmailLink]);

  const isSignInRedirect =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("signin") === "1";
  const isAuthCallback =
    typeof window !== "undefined" &&
    (() => {
      const url = new URL(window.location.href);
      const redirectPathTrimmed = AUTH_REDIRECT_PATH.endsWith("/")
        ? AUTH_REDIRECT_PATH.slice(0, -1)
        : AUTH_REDIRECT_PATH;
      const currentPath = url.pathname.endsWith("/")
        ? url.pathname.slice(0, -1)
        : url.pathname;
      return currentPath.endsWith(redirectPathTrimmed);
    })();

  React.useEffect(() => {
    if (flow.signedIn || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("signin") !== "1") return;
    if (AUTH_MODE === "firebase") {
      setShowAuthDialog(true);
    } else {
      handleSignIn();
    }
    if (AUTH_MODE !== "oidc") {
      params.delete("signin");
      const nextSearch = params.toString();
      window.history.replaceState(
        {},
        document.title,
        `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}`
      );
    }
  }, [flow.signedIn, handleSignIn]);

  React.useEffect(() => {
    if (flow.signedIn) {
      setShowAuthDialog(false);
    }
  }, [flow.signedIn]);

  /** Handle handleConnectReview. */
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
      await validateCredentials({ credentials: payload.credentials }, auth);
      const createdJob = await createJob(payload, auth);
      localStorage.setItem(JOB_ID_KEY, createdJob.job_id);
      setJobId(createdJob.job_id);
      setShowAllFlights(false);
      setManualOpen("review");
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

  /** Handle handleApproveImport. */
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
      setManualOpen("import");
      refresh();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleTokenExpired();
        return;
      }
      let message = err instanceof Error ? err.message : "Failed to start import";
      if (message.includes("Review not ready")) {
        message =
          "Review not ready yet. The review may still be running or was canceled before it finished. " +
          "Please wait for “Review ready”, or use “Edit import filters” to restart the review.";
      }
      setActionError({
        scope: "review",
        message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  /** Handle handleEditFilters. */
  const handleEditFilters = () => {
    if (!jobId) {
      setManualOpen("connect");
      return;
    }
    setActionLoading(true);
    setActionError(null);
    deleteJob(jobId, auth)
      .catch((err) => {
        if (isAuthExpiredError(err)) {
          handleTokenExpired();
          return;
        }
        setActionError({
          scope: "review",
          message: err instanceof Error ? err.message : "Failed to reset filters",
        });
      })
      .finally(() => {
        localStorage.removeItem(JOB_ID_KEY);
        setJobId(null);
        setShowAllFlights(false);
        setManualOpen("connect");
        setActionLoading(false);
      });
  };

  /** Handle clearLocalState. */
  const clearLocalState = () => {
    localStorage.removeItem(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
  };

  /** Handle handleStartOverConfirm. */
  const handleStartOverConfirm = async () => {
    if (downloadLoading) return;
    if (!jobId) {
      clearLocalState();
      return;
    }
    setActionLoading(true);
    setActionError(null);
    setActionNotice(null);
    try {
      await deleteJob(jobId, auth);
      clearLocalState();
      setActionNotice({
        scope: "global",
        message: "Results deleted. You can start a new import now.",
      });
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

  /** Handle handleSignOut. */
  const handleSignOut = () => {
    localStorage.removeItem(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
    if (AUTH_MODE === "oidc") {
      sessionStorage.setItem(FORCE_LOGIN_KEY, "1");
      localStorage.setItem(FORCE_LOGIN_KEY, "1");
      signOutOidc();
      return;
    }
    if (AUTH_MODE === "firebase") {
      void signOutFirebase();
      return;
    }
    localStorage.removeItem(USER_ID_KEY);
    setHeaderUserId(null);
  };

  const handleTokenExpired = React.useCallback(() => {
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(JOB_ID_KEY);
    setHeaderUserId(null);
    setJobId(null);
    if (AUTH_MODE === "oidc") {
      clearOidcAuth();
    }
    if (AUTH_MODE === "firebase") {
      clearFirebaseAuth();
    }
    setShowAllFlights(false);
    setActionError(null);
  }, [AUTH_MODE, clearOidcAuth, clearFirebaseAuth, setHeaderUserId]);

  React.useEffect(() => {
    if (!jobError || !isSignedIn) return;
    if (isAuthExpiredError(jobError)) {
      handleTokenExpired();
      return;
    }
    const status = (jobError as Error & { status?: number }).status;
    if (status === 404 || jobError.message.toLowerCase().includes("job not found")) {
      clearLocalState();
    }
  }, [jobError, isSignedIn, handleTokenExpired, clearLocalState]);

  React.useEffect(() => {
    if (!isSignedIn || !jobId || job) return;
    const status = jobErrorStatus;
    if (!status || ![502, 503, 504].includes(status)) return;
    if (backendResetCheckRef.current) return;
    backendResetCheckRef.current = true;
    (async () => {
      try {
        const response = await listJobs(auth);
        const jobs = response.jobs ?? [];
        if (jobs.length === 0) {
          clearLocalState();
          return;
        }
        const current = jobs.find((item) => item.job_id === jobId);
        if (!current && jobs[0]?.job_id) {
          localStorage.setItem(JOB_ID_KEY, jobs[0].job_id);
          setJobId(jobs[0].job_id);
        }
      } catch (err) {
        if (isAuthExpiredError(err)) {
          handleTokenExpired();
        }
      } finally {
        backendResetCheckRef.current = false;
      }
    })();
  }, [
    isSignedIn,
    jobId,
    job,
    jobErrorStatus,
    auth,
    clearLocalState,
    handleTokenExpired,
  ]);

  React.useEffect(() => {
    if (!isSignedIn) return;
    if (jobId || actionLoading) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await listJobs(auth);
        if (cancelled) return;
        const latest = response.jobs?.[0];
        if (latest?.job_id) {
          localStorage.setItem(JOB_ID_KEY, latest.job_id);
          setJobId(latest.job_id);
        }
      } catch (err) {
        if (isAuthExpiredError(err)) {
          handleTokenExpired();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, jobId, actionLoading, auth, handleTokenExpired]);

  /** Handle handleDownloadFiles. */
  const handleDownloadFiles = async () => {
    if (!jobId || downloadLoading) return;
    setDownloadLoading(true);
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
      setDownloadLoading(false);
    }
  };

  /** Handle handleDeleteResults. */
  const handleDeleteResults = async () => {
    if (!jobId || downloadLoading) return;
    setActionLoading(true);
    setActionError(null);
    setActionNotice(null);
    try {
      await deleteJob(jobId, auth);
      localStorage.removeItem(JOB_ID_KEY);
      setJobId(null);
      setActionNotice({
        scope: "global",
        message: "Results deleted. You can start a new import any time.",
      });
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
    reviewComplete && flow.importStatus === "idle" && !actionLoading;
  const canEditFiltersNow =
    reviewComplete && !importRunning && !importComplete && !actionLoading;

  const stepIndex = !flow.connected
    ? 1
    : !reviewComplete
      ? 2
      : !importComplete
        ? 3
        : 3;
  const nextLabel = !flow.connected
    ? "Connect"
    : !reviewComplete
      ? "Review"
      : !importComplete
        ? "Import"
        : "All steps completed";

  const isRedirectScreen =
    !flow.signedIn && AUTH_MODE === "oidc" && (isSignInRedirect || isAuthCallback);
  const hasOptionalProviders =
    FIREBASE_ENABLE_GOOGLE ||
    FIREBASE_ENABLE_APPLE ||
    FIREBASE_ENABLE_FACEBOOK ||
    FIREBASE_ENABLE_MICROSOFT ||
    FIREBASE_ENABLE_GUEST;

  if (isRedirectScreen) {
    return <div className="min-h-screen bg-background" />;
  }

  return (
    <div className="app-shell min-h-screen flex flex-col bg-gradient-to-b from-[#f7f9fc] to-[#eef3f8] text-[#1c2430] dark:bg-gradient-to-b dark:from-[#0b1120] dark:to-[#0f172a] dark:text-slate-100">
      <header className="sticky top-0 z-40 border-b border-[#d9e1ec] bg-white/95 backdrop-blur dark:border-sky-900/60 dark:bg-slate-950/90">
        <div className="absolute inset-x-0 top-0 h-1 bg-[#f1f4f8] dark:bg-slate-900/70" />
        <div className="container flex h-14 items-center justify-between sm:h-16">
          <a
            className="text-xs font-semibold tracking-[0.28em] text-[#5b6775] hover:text-foreground dark:text-slate-300"
            href={flow.signedIn ? "/app/" : "/"}
            onClick={(event) => navigateWithFade(event, flow.signedIn ? "/app/" : "/")}
          >
            SKYBRIDGE
          </a>
          <div className="flex items-center gap-2 sm:gap-4">
            {!flow.signedIn && AUTH_MODE !== "firebase" && (
              <Button size="sm" onClick={handleSignIn}>
                Sign up / Sign in
              </Button>
            )}
            {!flow.signedIn && AUTH_MODE === "firebase" && (
              <AlertDialog open={showAuthDialog} onOpenChange={setShowAuthDialog}>
                <AlertDialogTrigger asChild>
                  <Button size="sm">Sign up / Sign in</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Continue with</AlertDialogTitle>
                    <AlertDialogDescription>
                      {hasOptionalProviders
                        ? "Use a passwordless email link or choose a provider."
                        : "Use the passwordless email link to sign in."}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <div className="space-y-2">
                    {signInError && (
                      <Alert className="border-rose-200 bg-rose-50/70 text-rose-900">
                        <AlertTitle>Sign-in failed</AlertTitle>
                        <AlertDescription>{signInError}</AlertDescription>
                      </Alert>
                    )}
                    {FIREBASE_USE_EMULATOR && !firebaseEmulatorReady && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900">
                        Auth emulator is starting up. Sign-in will be available shortly.
                      </div>
                    )}
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-slate-500">
                        Email link (passwordless)
                      </label>
                      <div className="flex w-full max-w-xl gap-2">
                        <input
                          className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-slate-400 focus:outline-none"
                          placeholder="you@example.com"
                          value={emailAddress}
                          onChange={(event) => setEmailAddress(event.target.value)}
                        />
                        <Button
                          variant="outline"
                          className="h-11 px-4"
                          onClick={handleEmailLink}
                          disabled={authButtonsDisabled}
                        >
                          Send link
                        </Button>
                      </div>
                      {emailLinkNotice && (
                        <p className="text-xs text-slate-500">{emailLinkNotice}</p>
                      )}
                      {emailLinkUrl && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          Emulator link (click to sign in):
                          <a
                            className="ml-1 break-all text-sky-600 hover:underline"
                            href={emailLinkUrl}
                          >
                            {emailLinkUrl}
                          </a>
                        </div>
                      )}
                    </div>
                    {hasOptionalProviders && (
                      <>
                        <AuthDivider />
                        <div className="grid gap-2">
                          {FIREBASE_ENABLE_GOOGLE && (
                            <Button
                              className="h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                              onClick={() => handleFirebaseLogin("google")}
                              disabled={actionLoading}
                            >
                              <ProviderIcon name="google" />
                              Continue with Google
                            </Button>
                          )}
                          {FIREBASE_ENABLE_APPLE && (
                            <Button
                              className="h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                              onClick={() => handleFirebaseLogin("apple")}
                              disabled={actionLoading}
                            >
                              <ProviderIcon name="apple" />
                              Continue with Apple
                            </Button>
                          )}
                          {FIREBASE_ENABLE_FACEBOOK && (
                            <Button
                              className="h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                              onClick={() => handleFirebaseLogin("facebook")}
                              disabled={actionLoading}
                            >
                              <ProviderIcon name="facebook" />
                              Continue with Facebook
                            </Button>
                          )}
                          {FIREBASE_ENABLE_MICROSOFT && (
                            <Button
                              className="h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                              onClick={() => handleFirebaseLogin("microsoft")}
                              disabled={actionLoading}
                            >
                              <ProviderIcon name="microsoft" />
                              Continue with Microsoft
                            </Button>
                          )}
                          {FIREBASE_ENABLE_GUEST && (
                            <Button
                              className="h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                              onClick={() => handleFirebaseLogin("anonymous")}
                              disabled={actionLoading}
                            >
                              <ProviderIcon name="guest" />
                              Continue as guest
                            </Button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            {flow.connected && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!canStartOver(flow) || actionLoading || downloadLoading}
                  >
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
                      disabled={!jobId || actionLoading || downloadLoading}
                      aria-busy={downloadLoading}
                    >
                      <span className="flex items-center gap-2">
                        {downloadLoading && (
                          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                        )}
                        <span>
                          {downloadLoading ? "Preparing download" : "Download files"}
                        </span>
                      </span>
                    </Button>
                  </div>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleStartOverConfirm}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      disabled={actionLoading || downloadLoading}
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
        {!flow.signedIn &&
          AUTH_MODE === "oidc" &&
          (isSignInRedirect || isAuthCallback) && (
          <div className="min-h-[60vh]" />
        )}

        {!flow.signedIn &&
          !(AUTH_MODE === "oidc" && (isSignInRedirect || isAuthCallback)) && (
            <div className="mx-auto max-w-3xl space-y-4">
              <Card className="rounded-xl border border-[#d9e1ec] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-sky-900/60 dark:bg-slate-950/70 dark:shadow-none">
                <CardHeader className="space-y-2">
                  <CardTitle>Sign in to start your import</CardTitle>
                  <CardDescription>
                    Identify your job and keep your progress in sync across devices.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {signInError && (
                    <Alert className="border-rose-200 bg-rose-50/70 text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100">
                      <AlertTitle>Sign-in failed</AlertTitle>
                      <AlertDescription>{signInError}</AlertDescription>
                    </Alert>
                  )}
                  {AUTH_MODE !== "firebase" && (
                    <Button onClick={handleSignIn} disabled={actionLoading}>
                      Sign up / Sign in
                    </Button>
                  )}
                  {AUTH_MODE === "firebase" && (
                    <div className="space-y-2">
                      {FIREBASE_USE_EMULATOR && !firebaseEmulatorReady && (
                        <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900">
                          Auth emulator is starting up. Sign-in will be available shortly.
                        </div>
                      )}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500">
                          {hasOptionalProviders ? "Email link (passwordless)" : "Passwordless email link"}
                        </label>
                      <div className="flex w-full max-w-xl gap-2">
                        <input
                          className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-slate-400 focus:outline-none"
                          placeholder="you@example.com"
                          value={emailAddress}
                          onChange={(event) => setEmailAddress(event.target.value)}
                        />
                        <Button
                          variant="outline"
                          className="h-11 px-4"
                          onClick={handleEmailLink}
                          disabled={authButtonsDisabled}
                        >
                          Send link
                        </Button>
                      </div>
                        {emailLinkNotice && (
                          <p className="text-xs text-slate-500">{emailLinkNotice}</p>
                        )}
                        {emailLinkUrl && (
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                            Emulator link (click to sign in):
                            <a
                              className="ml-1 break-all text-sky-600 hover:underline"
                              href={emailLinkUrl}
                            >
                              {emailLinkUrl}
                            </a>
                          </div>
                        )}
                      </div>
                      {(FIREBASE_ENABLE_GOOGLE ||
                        FIREBASE_ENABLE_APPLE ||
                        FIREBASE_ENABLE_FACEBOOK ||
                        FIREBASE_ENABLE_MICROSOFT ||
                        FIREBASE_ENABLE_GUEST) && (
                        <>
                          <AuthDivider />
                          <div className="grid gap-2">
                            {FIREBASE_ENABLE_GOOGLE && (
                              <Button
                                className="h-12 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleFirebaseLogin("google")}
                                disabled={authButtonsDisabled}
                              >
                                <ProviderIcon name="google" />
                                Continue with Google
                              </Button>
                            )}
                            {FIREBASE_ENABLE_APPLE && (
                              <Button
                                className="h-12 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleFirebaseLogin("apple")}
                                disabled={authButtonsDisabled}
                              >
                                <ProviderIcon name="apple" />
                                Continue with Apple
                              </Button>
                            )}
                            {FIREBASE_ENABLE_FACEBOOK && (
                              <Button
                                className="h-12 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleFirebaseLogin("facebook")}
                                disabled={authButtonsDisabled}
                              >
                                <ProviderIcon name="facebook" />
                                Continue with Facebook
                              </Button>
                            )}
                            {FIREBASE_ENABLE_MICROSOFT && (
                              <Button
                                className="h-12 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleFirebaseLogin("microsoft")}
                                disabled={authButtonsDisabled}
                              >
                                <ProviderIcon name="microsoft" />
                                Continue with Microsoft
                              </Button>
                            )}
                            {FIREBASE_ENABLE_GUEST && (
                              <Button
                                className="h-12 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleFirebaseLogin("anonymous")}
                                disabled={authButtonsDisabled}
                              >
                                <ProviderIcon name="guest" />
                                Continue as guest
                              </Button>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                  {AUTH_MODE === "firebase" && FIREBASE_USE_EMULATOR && (
                    <p className="text-xs text-muted-foreground">
                      Local auth emulator is enabled. Email sign-in links are simulated.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

        {flow.signedIn && (
          <>
            {AUTH_MODE === "firebase" && isAnonymous && (
              <Card className="mb-4 rounded-xl border border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100">
                <CardHeader className="space-y-1">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <ShieldCheck className="h-4 w-4" aria-hidden />
                    Upgrade your guest session
                  </CardTitle>
                  <CardDescription className="text-amber-800/80 dark:text-amber-100/70">
                    Link a provider to keep your import history across devices.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex flex-wrap gap-2">
                    {FIREBASE_ENABLE_GOOGLE && (
                      <Button
                        className="h-11 justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                        onClick={() => handleFirebaseLogin("google", { link: true })}
                        disabled={actionLoading}
                      >
                        <ProviderIcon name="google" />
                        Link Google
                      </Button>
                    )}
                    {FIREBASE_ENABLE_APPLE && (
                      <Button
                        className="h-11 justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                        onClick={() => handleFirebaseLogin("apple", { link: true })}
                        disabled={actionLoading}
                      >
                        <ProviderIcon name="apple" />
                        Link Apple
                      </Button>
                    )}
                    {FIREBASE_ENABLE_MICROSOFT && (
                      <Button
                        className="h-11 justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                        onClick={() => handleFirebaseLogin("microsoft", { link: true })}
                        disabled={actionLoading}
                      >
                        <ProviderIcon name="microsoft" />
                        Link Microsoft
                      </Button>
                    )}
                    {FIREBASE_ENABLE_FACEBOOK && (
                      <Button
                        className="h-11 justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
                        onClick={() => handleFirebaseLogin("facebook", { link: true })}
                        disabled={actionLoading}
                      >
                        <ProviderIcon name="facebook" />
                        Link Facebook
                      </Button>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-amber-800/80 dark:text-amber-100/70">
                    <ArrowRight className="h-3 w-3" aria-hidden />
                    You can also link an email address below.
                  </div>
                  <div className="flex w-full max-w-xl gap-2">
                    <input
                      className="h-11 w-full rounded-lg border border-amber-200 bg-white px-3 text-sm text-amber-900 shadow-sm focus:border-amber-300 focus:outline-none"
                      placeholder="you@example.com"
                      value={emailAddress}
                      onChange={(event) => setEmailAddress(event.target.value)}
                    />
                    <Button variant="outline" className="h-11 px-4" onClick={handleEmailLink}>
                      Link email
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
            <div className="mb-4 lg:hidden">
              <Card className="rounded-xl border border-[#d9e1ec] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-sky-900/60 dark:bg-slate-950/70 dark:shadow-none">
                <CardContent className="space-y-2 py-3">
                  <div className="flex items-center justify-between text-xs text-[#5b6775]">
                    <span>Step {stepIndex} of 3</span>
                    <span>
                      {nextLabel === "All steps completed"
                        ? nextLabel
                        : `Next: ${nextLabel}`}
                    </span>
                  </div>
                  <Progress value={(stepIndex / 3) * 100} />
                </CardContent>
              </Card>
            </div>

            {actionNotice && (
              <Alert className="mb-4 border-emerald-200 bg-emerald-50/60 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-100">
                <AlertTitle>Done</AlertTitle>
                <AlertDescription>{actionNotice.message}</AlertDescription>
              </Alert>
            )}

            <div className="grid min-w-0 gap-4 lg:grid-cols-[240px_1fr]">
          <aside className="hidden space-y-3 lg:sticky lg:top-20 lg:block lg:self-start">
            <Card className="relative overflow-hidden rounded-xl border border-[#d9e1ec] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-sky-900/60 dark:bg-slate-950/70 dark:shadow-none">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.14),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.2),_transparent_60%)]" />
              <CardHeader className="pb-2">
                <CardTitle className="text-xs uppercase tracking-[0.28em] text-[#5b6775]">
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                <StepStatus
                  label="1 · Connect"
                  active={!flow.connected}
                  done={flow.connected}
                />
                <StepStatus
                  label="2 · Review"
                  active={flow.connected && !reviewComplete}
                  done={reviewComplete}
                />
                <StepStatus
                  label="3 · Import"
                  active={reviewComplete && !importComplete}
                  done={importComplete}
                />
                {showLiveUpdatesNotice && (
                  <div
                    className={cn(
                      "mt-2 rounded-lg border px-2.5 py-2 text-[11px] font-medium",
                      listenerFailed
                        ? "border-amber-200 bg-amber-50 text-amber-900"
                        : "border-emerald-200 bg-emerald-50 text-emerald-900"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span>
                        {listenerFailed
                          ? "Live updates paused. Polling every 4s."
                          : listenerActive
                            ? "Live updates connected."
                            : "Connecting live updates..."}
                      </span>
                      {listenerFailed && (
                        <button
                          type="button"
                          onClick={() => refresh()}
                          className="rounded-md border border-amber-200 bg-white/70 px-2 py-0.5 text-[10px] font-semibold text-amber-900 transition hover:bg-white"
                        >
                          Refresh
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>

          <section className="min-w-0 space-y-2.5">
            <div className="relative min-w-0 overflow-hidden rounded-xl border border-[#d1dbea] bg-white shadow-[0_10px_30px_rgba(22,32,44,0.08)] dark:border-sky-900/60 dark:bg-slate-950/70 dark:shadow-none">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.12),_transparent_58%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.18),_transparent_58%)]" />
            <Accordion
              type="single"
              collapsible
              value={openStep}
              onValueChange={handleAccordionChange}
            >
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
                elapsed={reviewElapsed}
                lastUpdate={reviewLastUpdate}
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
                elapsed={importElapsed}
                lastUpdate={importLastUpdate}
                importProgress={importProgress}
                latestImportEvent={latestImportEvent ?? null}
                formatFlightId={formatFlightId}
                formatLastUpdate={formatLastUpdate}
                now={now}
                job={job}
                reviewSummaryMissing={reviewSummary?.missing_tail_numbers ?? 0}
                retentionDays={retentionDays}
                onDownloadFiles={handleDownloadFiles}
                downloadLoading={downloadLoading}
                onDeleteResults={handleDeleteResults}
                actionLoading={actionLoading}
                importError={importError}
                onRefresh={refresh}
              />
            </Accordion>
            </div>
          </section>
        </div>
          </>
        )}
      </main>

      <AppFooter />
    </div>
  );
}
