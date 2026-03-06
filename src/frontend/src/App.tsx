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
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AppFooter } from "@/components/app/AppFooter";
import { ConnectSection } from "@/components/app/ConnectSection";
import { ReviewSection } from "@/components/app/ReviewSection";
import { ImportSection } from "@/components/app/ImportSection";
import { FirebaseAuthCard } from "@/components/app/auth/FirebaseAuthCard";
import { GuestUpgradeCard } from "@/components/app/auth/GuestUpgradeCard";
import type { ProviderFlags } from "@/components/app/auth/FirebaseProviderButtons";
import { ThemeToggle } from "@/components/theme-toggle";
import type { ProviderName } from "@/components/app/auth/shared";
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
import { Check, Loader2 } from "lucide-react";
import {
  formatDate,
  formatFlightId,
  formatISODate,
  formatPhaseElapsed,
  formatPhaseLastUpdate,
  formatLastUpdate,
} from "@/lib/format";
import { isAuthExpiredError } from "@/lib/auth-helpers";
import { useFirebaseAuth } from "@/hooks/use-firebase-auth";
import {
  DEV_CLOUD_AHOY_EMAIL,
  DEV_CLOUD_AHOY_PASSWORD,
  DEV_FLYSTO_EMAIL,
  DEV_FLYSTO_PASSWORD,
  DEV_PREFILL,
  FIREBASE_API_KEY,
  FIREBASE_APP_ID,
  FIREBASE_AUTH_DOMAIN,
  FIREBASE_EMULATOR_HOST,
  FIREBASE_ENABLE_APPLE,
  FIREBASE_ENABLE_FACEBOOK,
  FIREBASE_ENABLE_GOOGLE,
  FIREBASE_ENABLE_GUEST,
  FIREBASE_ENABLE_MICROSOFT,
  FIREBASE_PROJECT_ID,
  FIREBASE_USE_EMULATOR,
  retentionDays,
} from "@/lib/app-config";
import { parseISODateInput } from "@/lib/date-input";

const JOB_ID_KEY = "skybridge_job_id";
const OPEN_STEP_KEY = "skybridge_open_step";
const EMAIL_LINK_EMAIL_KEY = "skybridge_email_link_email";

const readSessionValue = (key: string) =>
  typeof window !== "undefined" ? sessionStorage.getItem(key) : null;
const setSessionValue = (key: string, value: string) => {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(key, value);
};
const removeSessionValue = (key: string) => {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(key);
};
const readEmailLinkEmail = () => {
  if (typeof window === "undefined") return null;
  return (
    sessionStorage.getItem(EMAIL_LINK_EMAIL_KEY) ||
    window.localStorage?.getItem(EMAIL_LINK_EMAIL_KEY) ||
    null
  );
};
const setEmailLinkEmail = (email: string) => {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(EMAIL_LINK_EMAIL_KEY, email);
  window.localStorage?.setItem(EMAIL_LINK_EMAIL_KEY, email);
};
const clearEmailLinkEmail = () => {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(EMAIL_LINK_EMAIL_KEY);
  window.localStorage?.removeItem(EMAIL_LINK_EMAIL_KEY);
};

/** Render App component. */
export default function App() {
  const [jobId, setJobId] = React.useState<string | null>(() =>
    readSessionValue(JOB_ID_KEY)
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
    accessToken: firebaseToken,
    startLogin: startFirebaseLogin,
    startEmailLink: startFirebaseEmailLink,
    completeEmailLink: completeFirebaseEmailLink,
    isAnonymous: firebaseAnonymous,
    emulatorProvider: firebaseEmulatorProvider,
    emulatorReady: firebaseEmulatorReady,
    authReady: firebaseAuthReady,
    emailLinkPending: firebaseEmailLinkPending,
    signOut: signOutFirebase,
  } = useFirebaseAuth({
    enabled: true,
    apiKey: FIREBASE_API_KEY,
    authDomain: FIREBASE_AUTH_DOMAIN,
    projectId: FIREBASE_PROJECT_ID,
    appId: FIREBASE_APP_ID || undefined,
    emulatorHost: FIREBASE_EMULATOR_HOST || undefined,
    useEmulator: FIREBASE_USE_EMULATOR,
    allowAnonymous: FIREBASE_ENABLE_GUEST,
    onError: (message) => setActionError({ scope: "sign-in", message }),
    onLoadingChange: setActionLoading,
  });
  const [authInitTimedOut, setAuthInitTimedOut] = React.useState(false);
  const [emailAddress, setEmailAddress] = React.useState("");
  const [emailLinkNotice, setEmailLinkNotice] = React.useState<string | null>(null);
  const [emailLinkUrl, setEmailLinkUrl] = React.useState<string | null>(null);
  const providerFlags = React.useMemo<ProviderFlags>(
    () => ({
      google: Boolean(FIREBASE_ENABLE_GOOGLE),
      apple: Boolean(FIREBASE_ENABLE_APPLE),
      facebook: Boolean(FIREBASE_ENABLE_FACEBOOK),
      microsoft: Boolean(FIREBASE_ENABLE_MICROSOFT),
      anonymous: Boolean(FIREBASE_ENABLE_GUEST),
    }),
    []
  );
  const hasOptionalProviders = Object.values(providerFlags).some(Boolean);
  const focusFirebaseAuthCard = React.useCallback(() => {
    if (typeof window === "undefined") return;
    const card = document.getElementById("firebase-auth-card");
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    const emailInput = card.querySelector("input");
    if (emailInput instanceof HTMLInputElement) {
      emailInput.focus({ preventScroll: true });
    }
  }, []);

  const [cloudahoyEmail, setCloudahoyEmail] = React.useState("");
  const [cloudahoyPassword, setCloudahoyPassword] = React.useState("");
  const [flystoEmail, setFlystoEmail] = React.useState("");
  const [flystoPassword, setFlystoPassword] = React.useState("");
  const [startDateInput, setStartDateInput] = React.useState("");
  const [endDateInput, setEndDateInput] = React.useState("");
  const [maxFlights, setMaxFlights] = React.useState("");
  const startDate = parseISODateInput(startDateInput);
  const endDate = parseISODateInput(endDateInput);

  const activeAccessToken = firebaseToken;
  const isSignedIn = Boolean(activeAccessToken);
  const isAnonymous =
    firebaseAnonymous &&
    !(FIREBASE_USE_EMULATOR && firebaseEmulatorProvider && firebaseEmulatorProvider !== "anonymous");
  const auth = React.useMemo<AuthContext>(
    () => ({ token: activeAccessToken }),
    [activeAccessToken]
  );

  const { data: job, error: jobError, refresh } = useJobSnapshot(isSignedIn ? jobId : null, auth);

  const flow = React.useMemo(
    () => deriveFlowState(isSignedIn, job ?? null),
    [isSignedIn, job]
  );
  const [manualOpen, setManualOpen] = React.useState<string | undefined>(() =>
    readSessionValue(OPEN_STEP_KEY) ?? undefined
  );
  const backendResetCheckRef = React.useRef(false);
  const emailLinkAutoRef = React.useRef(false);
  const openStep = React.useMemo(() => {
    if (flow.importStatus === "running" || flow.importStatus === "complete") return "import";
    if (flow.reviewStatus === "running") return "review";
    if (!flow.connected) return manualOpen ?? "connect";
    return manualOpen ?? getOpenStep(flow);
  }, [flow, manualOpen]);

  React.useEffect(() => {
    if (!firebaseEmailLinkPending) return;
    const params =
      typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const emailParam = params?.get("email") ?? "";
    if (emailParam) {
      setEmailLinkEmail(emailParam);
    }
    const storedEmail = readEmailLinkEmail() ?? "";
    if (!emailAddress && storedEmail) {
      setEmailAddress(storedEmail);
    }
    setEmailLinkNotice(
      storedEmail
        ? `Email link detected for ${storedEmail}. Complete sign-in to continue.`
        : "Email link detected. Enter the email you used to request the link to finish signing in."
    );
    if (!emailLinkAutoRef.current && storedEmail) {
      emailLinkAutoRef.current = true;
      void completeFirebaseEmailLink(storedEmail);
    }
  }, [firebaseEmailLinkPending, emailAddress, completeFirebaseEmailLink]);

  React.useEffect(() => {
    if (!flow.signedIn) return;
    setEmailLinkNotice(null);
    setEmailLinkUrl(null);
    clearEmailLinkEmail();
    emailLinkAutoRef.current = false;
  }, [flow.signedIn]);

  React.useEffect(() => {
    if (firebaseAuthReady) {
      setAuthInitTimedOut(false);
      return;
    }
    const timeout = window.setTimeout(() => {
      setAuthInitTimedOut(true);
    }, 10000);
    return () => window.clearTimeout(timeout);
  }, [firebaseAuthReady]);

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
  const authButtonsDisabled = actionLoading || !firebaseAuthReady;
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
      removeSessionValue(OPEN_STEP_KEY);
      return;
    }
    if (openStep) {
      setSessionValue(OPEN_STEP_KEY, openStep);
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
    focusFirebaseAuthCard();
  }, [focusFirebaseAuthCard]);

  const handleFirebaseLogin = React.useCallback(
    (
      provider: ProviderName,
      options?: Parameters<typeof startFirebaseLogin>[1]
    ) => {
      setActionError(null);
      const enabled =
        provider === "google"
          ? providerFlags.google
          : provider === "apple"
            ? providerFlags.apple
            : provider === "facebook"
              ? providerFlags.facebook
              : provider === "microsoft"
                ? providerFlags.microsoft
                : provider === "anonymous"
                  ? providerFlags.anonymous
                  : false;
      if (!enabled) {
        setActionError({
          scope: "sign-in",
          message: "This sign-in option is disabled. Use the email link instead.",
        });
        return;
      }
      void startFirebaseLogin(provider as Parameters<typeof startFirebaseLogin>[0], options);
    },
    [startFirebaseLogin, providerFlags]
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
    setEmailLinkEmail(email);
    const link = await startFirebaseEmailLink(email);
    setEmailLinkNotice(`We sent a sign-in link to ${email}.`);
    if (link) {
      setEmailLinkUrl(link);
    }
  }, [emailAddress, startFirebaseEmailLink]);

  const handleEmailLinkComplete = React.useCallback(async () => {
    setActionError(null);
    const storedEmail = readEmailLinkEmail() ?? "";
    const email = emailAddress.trim() || storedEmail;
    if (!email) {
      setActionError({ scope: "sign-in", message: "Enter your email to complete sign-in." });
      return;
    }
    if (storedEmail && email !== storedEmail) {
      setActionError({
        scope: "sign-in",
        message: `Use ${storedEmail} to complete sign-in.`,
      });
      return;
    }
    if (!emailAddress.trim() && storedEmail) {
      setEmailAddress(storedEmail);
    }
    await completeFirebaseEmailLink(email);
  }, [emailAddress, completeFirebaseEmailLink]);

  React.useEffect(() => {
    if (flow.signedIn || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("signin") !== "1") return;
    handleSignIn();
    params.delete("signin");
    const nextSearch = params.toString();
    window.history.replaceState(
      {},
      document.title,
      `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}`
    );
  }, [flow.signedIn, handleSignIn]);

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
        start_date: startDate ? formatISODate(startDate) : null,
        end_date: endDate ? formatISODate(endDate) : null,
        max_flights: maxFlights ? Number(maxFlights) : null,
      };
      await validateCredentials({ credentials: payload.credentials }, auth);
      const createdJob = await createJob(payload, auth);
      setSessionValue(JOB_ID_KEY, createdJob.job_id);
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
    const currentJobId = jobId;
    if (!currentJobId) {
      setManualOpen("connect");
      return;
    }
    // Leave review immediately so polling errors from a just-deleted job never flash in step 2.
    removeSessionValue(JOB_ID_KEY);
    setJobId(null);
    setShowAllFlights(false);
    setManualOpen("connect");
    setActionLoading(true);
    setActionError(null);
    deleteJob(currentJobId, auth)
      .catch((err) => {
        if (isAuthExpiredError(err)) {
          handleTokenExpired();
          return;
        }
        setActionError({
          scope: "connect",
          message: err instanceof Error ? err.message : "Failed to reset filters",
        });
      })
      .finally(() => {
        setActionLoading(false);
      });
  };

  /** Handle clearLocalState. */
  const clearLocalState = () => {
    removeSessionValue(JOB_ID_KEY);
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
    removeSessionValue(JOB_ID_KEY);
    clearEmailLinkEmail();
    setJobId(null);
    setShowAllFlights(false);
    setActionError(null);
    void signOutFirebase();
  };

  const handleTokenExpired = React.useCallback(() => {
    removeSessionValue(JOB_ID_KEY);
    clearEmailLinkEmail();
    setJobId(null);
    void signOutFirebase();
    setShowAllFlights(false);
    setActionError(null);
  }, [signOutFirebase]);

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
          setSessionValue(JOB_ID_KEY, jobs[0].job_id);
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
          setSessionValue(JOB_ID_KEY, latest.job_id);
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
      removeSessionValue(JOB_ID_KEY);
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
        removeSessionValue(JOB_ID_KEY);
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
  const dateRangeError = (() => {
    const hasStart = Boolean(startDateInput.trim());
    const hasEnd = Boolean(endDateInput.trim());
    if (!hasStart && !hasEnd) return null;
    if (!hasStart || !hasEnd) {
      return "Enter both start and end dates, or clear both.";
    }
    if (!startDate || !endDate) {
      return "Use the YYYY-MM-DD format for both dates.";
    }
    if (endDate < startDate) {
      return "End date must be on or after the start date.";
    }
    return null;
  })();
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
      : 3;
  const nextLabel = !flow.connected
    ? "Review"
    : !reviewComplete
      ? "Import"
      : !importComplete
        ? "Complete import"
        : "All steps completed";
  const navSteps = [
    {
      id: "connect",
      title: "Connect",
      subtitle: "Link CloudAhoy and FlySto",
      done: flow.connected,
      active: !flow.connected,
      locked: false,
    },
    {
      id: "review",
      title: "Review",
      subtitle: "Verify your flight data",
      done: reviewComplete,
      active: flow.connected && !reviewComplete,
      locked: !flow.connected,
    },
    {
      id: "import",
      title: "Import",
      subtitle: "Transfer to FlySto",
      done: importComplete,
      active: reviewComplete && !importComplete,
      locked: !reviewComplete,
    },
  ] as const;
  const completedSteps = navSteps.filter((step) => step.done).length;
  const checklistProgress = (completedSteps / navSteps.length) * 100;

  const authInitializing = !firebaseAuthReady && !authInitTimedOut;

  return (
    <div className="app-shell relative min-h-screen flex flex-col text-foreground">
      {/* Atmospheric background */}
      <div className="atmosphere">
        <div className="stars">
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
          <div className="star"></div>
        </div>
        <div className="runway-lights"></div>
      </div>

      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur-xl dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/90">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[hsl(var(--horizon))]/30 to-transparent" />
        <div className="container flex h-14 items-center justify-between sm:h-16">
          <a
            className="group flex items-center gap-3"
            href={flow.signedIn ? "/app/" : "/"}
            onClick={(event) => navigateWithFade(event, flow.signedIn ? "/app/" : "/")}
          >
            <img
              src="/brand/logo-64.png"
              srcSet="/brand/logo-64.png 1x, /brand/logo-128.png 2x"
              alt=""
              aria-hidden
              className="h-8 w-8 rounded-lg object-cover shadow-lg shadow-primary/30 transition-transform group-hover:scale-105 animate-float"
            />
            <span className="text-sm font-bold tracking-[0.2em] text-foreground/80 transition-colors group-hover:text-foreground">
              SKYBRIDGE
            </span>
          </a>
          <div className="flex items-center gap-2 sm:gap-4">
            {!flow.signedIn && firebaseAuthReady && (
              <Button size="sm" onClick={handleSignIn}>
                Sign up / Sign in
              </Button>
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
                      className="min-w-[11.5rem] justify-center"
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

      <main className="container relative z-10 flex-1 pb-16 pt-5 lg:pb-8">
        {!flow.signedIn && (
          <div className="mx-auto max-w-3xl space-y-4">
            {authInitializing && (
              <div className="flex min-h-[40vh] items-center justify-center">
                <div className="text-center space-y-3">
                  <div className="h-8 w-8 mx-auto rounded-full border-2 border-[hsl(var(--horizon))]/30 border-t-[hsl(var(--horizon))] animate-spin" />
                  <p className="text-sm text-muted-foreground">Loading...</p>
                </div>
              </div>
            )}
            {!firebaseAuthReady && authInitTimedOut && (
              <Alert className="border-amber-300 bg-amber-50/80 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                <AlertTitle>Sign-in initialization delayed</AlertTitle>
                <AlertDescription>
                  Firebase Auth is taking longer than expected to initialize.
                  Check your local stack and refresh this page.
                </AlertDescription>
                {signInError && (
                  <p className="mt-2 text-xs font-medium text-amber-950 dark:text-amber-200">
                    Details: {signInError}
                  </p>
                )}
                <div className="mt-3">
                  <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
                    Reload
                  </Button>
                </div>
              </Alert>
            )}
            {firebaseAuthReady && (
              <div id="firebase-auth-card">
                <FirebaseAuthCard
                  signInError={signInError}
                  authReady={firebaseAuthReady}
                  useEmulator={FIREBASE_USE_EMULATOR}
                  emulatorReady={firebaseEmulatorReady}
                  hasOptionalProviders={hasOptionalProviders}
                  emailAddress={emailAddress}
                  onEmailChange={setEmailAddress}
                  onSendLink={handleEmailLink}
                  onCompleteLink={handleEmailLinkComplete}
                  emailLinkPending={firebaseEmailLinkPending}
                  emailLinkNotice={emailLinkNotice}
                  emailLinkUrl={emailLinkUrl}
                  authButtonsDisabled={authButtonsDisabled}
                  providers={providerFlags}
                  onProvider={handleFirebaseLogin}
                />
              </div>
            )}
          </div>
        )}

        {flow.signedIn && (
          <>
            {isAnonymous && (
              <GuestUpgradeCard
                providers={providerFlags}
                onProvider={(provider) => handleFirebaseLogin(provider, { link: true })}
                emailAddress={emailAddress}
                onEmailChange={setEmailAddress}
                onSendLink={handleEmailLink}
                onCompleteLink={handleEmailLinkComplete}
                emailLinkPending={firebaseEmailLinkPending}
                actionLoading={actionLoading}
              />
            )}
            <div className="mb-4 lg:hidden">
              <Card className="glass-card rounded-2xl">
                <CardContent className="space-y-2 py-3">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Step {stepIndex} of 3</span>
                    <span className="text-[hsl(var(--horizon))]">
                      {nextLabel === "All steps completed"
                        ? nextLabel
                        : `Next: ${nextLabel}`}
                    </span>
                  </div>
                  <Progress value={(stepIndex / 3) * 100} className="progress-bar-aviation" />
                </CardContent>
              </Card>
            </div>

            {actionNotice && (
              <Alert className="mb-4 border-[hsl(var(--altitude))]/30 bg-[hsl(var(--altitude))]/10 text-[hsl(var(--altitude))] dark:border-[hsl(var(--altitude))]/30 dark:bg-[hsl(var(--altitude))]/10">
                <AlertTitle>Done</AlertTitle>
                <AlertDescription>{actionNotice.message}</AlertDescription>
              </Alert>
            )}

            <div className="grid min-w-0 gap-4 lg:grid-cols-[280px_1fr]">
          <aside className="hidden space-y-3 lg:sticky lg:top-20 lg:block lg:self-start">
            <Card className="glass-card nav-panel relative overflow-hidden rounded-2xl">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.06),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.1),_transparent_60%)]" />
              <CardContent className="space-y-4 p-5">
                <div className="checklist-header">
                  <p className="checklist-kicker">Import progress</p>
                  <div className="checklist-summary-row">
                    <span className="checklist-summary-label">
                      {completedSteps}/{navSteps.length} complete
                    </span>
                    <span className="checklist-summary-next">
                      {nextLabel === "All steps completed"
                        ? "Done"
                        : nextLabel}
                    </span>
                  </div>
                  <Progress
                    value={checklistProgress}
                    className="checklist-progress"
                    indicatorClassName="checklist-progress-indicator"
                  />
                </div>
                <div className="nav-steps-container">
                  <div className="nav-steps gap-1.5">
                    {navSteps.map((step, index) => {
                      const statusLabel = step.done
                        ? "Done"
                        : step.active
                          ? "Current"
                          : step.locked
                            ? "Locked"
                            : "Ready";
                      return (
                        <div
                          key={step.id}
                          className={cn(
                            "nav-step",
                            step.active && "active",
                            step.done && !step.active && "completed",
                            step.locked && "locked"
                          )}
                        >
                          <span className="step-indicator">
                            {step.done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                          </span>
                          <span className="step-content">
                            <span className="step-title-row">
                              <span className="step-title">{step.title}</span>
                              <span
                                className={cn(
                                  "step-inline-status",
                                  step.done && "done",
                                  step.active && "active",
                                  step.locked && "locked"
                                )}
                              >
                                <span className="step-inline-dot" aria-hidden />
                                <span className="step-inline-label">{statusLabel}</span>
                              </span>
                            </span>
                            <span className="step-subtitle">{step.subtitle}</span>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>
          </aside>

          <section className="min-w-0 space-y-2.5 app-content-stack">
            <div className="glass-card-accent relative min-w-0 rounded-2xl">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.04),_transparent_58%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.08),_transparent_58%)]" />
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
                startDate={startDate ?? undefined}
                endDate={endDate ?? undefined}
                startDateInput={startDateInput}
                endDateInput={endDateInput}
                setStartDateInput={setStartDateInput}
                setEndDateInput={setEndDateInput}
                dateRangeError={dateRangeError}
                maxFlights={maxFlights}
                cloudahoyEmail={cloudahoyEmail}
                cloudahoyPassword={cloudahoyPassword}
                flystoEmail={flystoEmail}
                flystoPassword={flystoPassword}
                setCloudahoyEmail={setCloudahoyEmail}
                setCloudahoyPassword={setCloudahoyPassword}
                setFlystoEmail={setFlystoEmail}
                setFlystoPassword={setFlystoPassword}
                setMaxFlights={setMaxFlights}
                onConnectReview={handleConnectReview}
                actionLoading={actionLoading}
                connectError={connectError}
                onRefresh={refresh}
              />

              <div className="border-t border-border/30 dark:border-[hsl(var(--sky-accent))]/10" />
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

              <div className="border-t border-border/30 dark:border-[hsl(var(--sky-accent))]/10" />
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
