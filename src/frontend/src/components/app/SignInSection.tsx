import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { UserRound } from "lucide-react";

/** Render SignInSection component. */
export function SignInSection({
  allowed,
  signedIn,
  onSignIn,
  actionLoading,
  signInError,
  retentionDays,
}: {
  allowed: boolean;
  signedIn: boolean;
  onSignIn: () => void;
  actionLoading: boolean;
  signInError?: string | null;
  retentionDays: number;
}) {
  return (
    <AccordionItem value="sign-in" className="border-0 px-4 bg-white dark:bg-transparent">
      <AccordionTrigger disabled={!allowed}>
        <div className="flex w-full items-center justify-between">
          <span>1 · Sign in</span>
          <Badge variant={signedIn ? "success" : "secondary"}>
            {signedIn ? "Signed in" : "Required"}
          </Badge>
        </div>
      </AccordionTrigger>
      <AccordionContent>
        <div className="space-y-4 pb-4">
          <p className="max-w-2xl text-base font-semibold leading-relaxed text-foreground">
            Skybridge imports your CloudAhoy flights into FlySto. You’ll connect both
            accounts, review the summary, and approve the import.
          </p>
          <Alert className="border-sky-100 bg-sky-50/60 text-slate-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-slate-100">
            <AlertTitle>What you can expect</AlertTitle>
            <AlertDescription>
              <ul className="list-disc space-y-1 pl-5">
                <li>
                  Sign-in is required to identify your job, protect your data, and let
                  you resume later.
                </li>
                <li>
                  We import flights, times, routes, crew, trajectory data, and remarks.
                  You can review everything before approving.
                </li>
                <li>
                  Credentials are used only for this job and never stored. Results are
                  retained for {retentionDays} days, then deleted.
                </li>
              </ul>
            </AlertDescription>
          </Alert>
          <div className="grid gap-2 sm:grid-cols-3">
            <Button
              className="w-full justify-start gap-2 shadow-sm"
              onClick={onSignIn}
              disabled={signedIn || actionLoading}
            >
              <UserRound className="h-4 w-4" />
              Sign up / Sign in
            </Button>
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
  );
}
