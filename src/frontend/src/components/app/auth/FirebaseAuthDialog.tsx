import {
  AlertDialog,
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
import { FirebaseEmailLinkForm } from "./FirebaseEmailLinkForm";
import { FirebaseProviderButtons, type ProviderFlags } from "./FirebaseProviderButtons";
import type { ProviderName } from "./shared";

export function FirebaseAuthDialog({
  open,
  onOpenChange,
  signInError,
  authReady,
  emulatorReady,
  useEmulator,
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
  actionLoading,
  triggerLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  signInError: string | null;
  authReady: boolean;
  emulatorReady: boolean;
  useEmulator: boolean;
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
  actionLoading: boolean;
  triggerLabel: string;
}) {
  const emailActionLabel = emailLinkPending ? "Complete sign-in" : "Send link";
  const emailAction = emailLinkPending ? onCompleteLink : onSendLink;
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogTrigger asChild>
        <Button size="sm">{triggerLabel}</Button>
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
            label="Email link (passwordless)"
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
            disabled={actionLoading}
            showDivider={hasOptionalProviders}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
