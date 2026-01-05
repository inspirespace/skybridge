import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowRight, CheckCircle2 } from "lucide-react";

/** Render LandingPage component. */
export function LandingPage({
  onSignIn,
  signInError,
  retentionDays,
}: {
  onSignIn: () => void;
  signInError?: string | null;
  retentionDays: number;
}) {
  return (
    <section className="space-y-6">
      <Card className="rounded-2xl border border-[#d1dbea] bg-white shadow-[0_12px_34px_rgba(22,32,44,0.08)] dark:border-sky-900/60 dark:bg-slate-950/70 dark:shadow-none">
        <CardContent className="space-y-6 p-6 sm:p-8">
          <Badge variant="secondary" className="w-fit border border-sky-200/50 text-slate-700 dark:border-sky-900/60 dark:bg-sky-950/60 dark:text-slate-200">
            CloudAhoy → FlySto
          </Badge>
          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              <h1 className="text-3xl font-semibold leading-tight text-foreground sm:text-4xl">
                Move your CloudAhoy history into FlySto with confidence.
              </h1>
              <p className="text-base leading-relaxed text-muted-foreground">
                Skybridge connects both accounts, builds a clean summary, and lets you review
                everything before approving the import. No scripts, no manual CSV wrangling—just
                a guided flow built for pilots and operators.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg" className="px-6" onClick={onSignIn}>
                  Sign up / Sign in
                </Button>
                <div className="text-sm text-muted-foreground">
                  Review before import · Results retained for {retentionDays} days
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-sky-100 bg-sky-50/60 p-4 text-slate-900 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-slate-100">
              <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                What you can expect
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed">
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  Sign in to identify your job, protect your data, and resume later.
                </li>
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  We import flights, times, routes, crew, trajectory data, and remarks.
                </li>
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  Credentials are used only for this job and never stored.
                </li>
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  Results are retained for {retentionDays} days, then deleted.
                </li>
              </ul>
            </div>
          </div>
          {signInError && (
            <Alert variant="destructive">
              <AlertTitle>Sign-in failed</AlertTitle>
              <AlertDescription>{signInError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="rounded-xl border border-[#d1dbea] bg-white/80 p-5 shadow-[0_10px_24px_rgba(22,32,44,0.06)] dark:border-sky-900/60 dark:bg-slate-950/60 dark:shadow-none">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">Connect accounts</div>
              <p className="mt-2 text-sm text-muted-foreground">
                Authenticate CloudAhoy and FlySto, then set your optional import filters.
              </p>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </div>
        </Card>
        <Card className="rounded-xl border border-[#d1dbea] bg-white/80 p-5 shadow-[0_10px_24px_rgba(22,32,44,0.06)] dark:border-sky-900/60 dark:bg-slate-950/60 dark:shadow-none">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">Review the summary</div>
              <p className="mt-2 text-sm text-muted-foreground">
                Preview flights, hours, and missing registrations before any changes are made.
              </p>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </div>
        </Card>
        <Card className="rounded-xl border border-[#d1dbea] bg-white/80 p-5 shadow-[0_10px_24px_rgba(22,32,44,0.06)] dark:border-sky-900/60 dark:bg-slate-950/60 dark:shadow-none">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">Approve import</div>
              <p className="mt-2 text-sm text-muted-foreground">
                Start the import when you are ready, then download the results as a bundle.
              </p>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </div>
        </Card>
      </div>
    </section>
  );
}
