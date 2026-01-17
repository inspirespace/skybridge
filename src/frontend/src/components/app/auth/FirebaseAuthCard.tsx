import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FirebaseEmailLinkForm } from "./FirebaseEmailLinkForm";
import { FirebaseProviderButtons, type ProviderFlags } from "./FirebaseProviderButtons";
import type { ProviderName } from "./shared";

export function FirebaseAuthCard({
  signInError,
  authReady,
  useEmulator,
  emulatorReady,
  hasOptionalProviders,
  emailAddress,
  onEmailChange,
  onSendLink,
  onCompleteLink,
  emailLinkPending,
  emailLinkNotice,
  emailLinkUrl,
  authButtonsDisabled,
  providers,
  onProvider,
}: {
  signInError: string | null;
  authReady: boolean;
  useEmulator: boolean;
  emulatorReady: boolean;
  hasOptionalProviders: boolean;
  emailAddress: string;
  onEmailChange: (value: string) => void;
  onSendLink: () => void;
  onCompleteLink: () => void;
  emailLinkPending: boolean;
  emailLinkNotice: string | null;
  emailLinkUrl: string | null;
  authButtonsDisabled: boolean;
  providers: ProviderFlags;
  onProvider: (provider: ProviderName) => void;
}) {
  const emailActionLabel = emailLinkPending ? "Complete sign-in" : "Send link";
  const emailAction = emailLinkPending ? onCompleteLink : onSendLink;
  return (
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
        {useEmulator && !emulatorReady && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900">
            Auth emulator is starting up. Sign-in will be available shortly.
          </div>
        )}
        {!authReady && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900">
            Auth is still starting. Sign-in will be available shortly.
          </div>
        )}
        <FirebaseEmailLinkForm
          label={hasOptionalProviders ? "Email link (passwordless)" : "Passwordless email link"}
          email={emailAddress}
          onEmailChange={onEmailChange}
          onSend={emailAction}
          disabled={authButtonsDisabled}
          buttonLabel={emailActionLabel}
          notice={emailLinkNotice}
          linkUrl={emailLinkUrl}
        />
        <FirebaseProviderButtons
          enabled={providers}
          labelPrefix="Continue with"
          onSelect={onProvider}
          disabled={authButtonsDisabled}
          showDivider={hasOptionalProviders}
          buttonClassName="h-12"
        />
        {useEmulator && (
          <p className="text-xs text-muted-foreground">
            Local auth emulator is enabled. Email sign-in links are simulated.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
