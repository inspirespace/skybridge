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
      <Card className="relative overflow-hidden rounded-3xl border border-[#d1dbea] bg-white shadow-[0_18px_50px_rgba(22,32,44,0.12)] dark:border-sky-900/60 dark:bg-slate-950/75 dark:shadow-none">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.18),_transparent_55%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.24),_transparent_55%)]" />
        <div className="pointer-events-none absolute -right-32 top-20 h-72 w-72 rounded-full bg-sky-200/40 blur-3xl dark:bg-sky-500/20" />
        <CardContent className="relative space-y-8 p-6 sm:p-10">
          <Badge
            variant="secondary"
            className="w-fit border border-sky-200/50 text-slate-700 dark:border-sky-900/60 dark:bg-sky-950/60 dark:text-slate-200"
          >
            CloudAhoy → FlySto
          </Badge>
          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              <h1 className="text-3xl font-semibold leading-snug text-foreground sm:text-4xl lg:text-[2.75rem] lg:leading-[1.1]">
                Move your CloudAhoy history into FlySto with complete confidence.
              </h1>
              <p className="text-base leading-relaxed text-muted-foreground">
                Skybridge connects both accounts, builds a clean summary, and lets you review
                everything before approving the import. No scripts or CSV juggling—just a guided,
                review‑first workflow built for pilots and operators.
              </p>
              <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span className="rounded-full border border-sky-200/60 bg-white/70 px-3 py-1 dark:border-sky-900/60 dark:bg-slate-950/60">
                  Review before import
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white/70 px-3 py-1 dark:border-sky-900/60 dark:bg-slate-950/60">
                  Credentials never stored
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white/70 px-3 py-1 dark:border-sky-900/60 dark:bg-slate-950/60">
                  Results retained {retentionDays} days
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  size="lg"
                  className="px-6 shadow-[0_12px_24px_rgba(56,189,248,0.2)] dark:shadow-[0_14px_30px_rgba(56,189,248,0.22)]"
                  onClick={onSignIn}
                >
                  Sign up / Sign in
                </Button>
              </div>
            </div>
            <div className="rounded-xl border border-sky-200/80 bg-white/80 p-5 text-slate-900 shadow-[0_14px_28px_rgba(56,189,248,0.15)] dark:border-sky-800/70 dark:bg-slate-950/60 dark:text-slate-100 dark:shadow-[0_18px_30px_rgba(14,116,144,0.2)]">
              <div className="text-base font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                What you can expect
              </div>
              <ul className="mt-4 space-y-3 text-base leading-[1.65]">
                <li className="flex items-start gap-3">
                  <span className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center text-emerald-500">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                  <span className="leading-[1.7]">
                    Sign in to identify your job, protect your data, and resume later.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center text-emerald-500">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                  <span className="leading-[1.7]">
                    We import flights, times, routes, crew, trajectory data, and remarks.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center text-emerald-500">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                  <span className="leading-[1.7]">
                    Credentials are used only for this job and never stored.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center text-emerald-500">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                  <span className="leading-[1.7]">
                    Results are retained for {retentionDays} days, then deleted.
                  </span>
                </li>
              </ul>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-sky-100 bg-white/70 p-3 text-sm text-muted-foreground dark:border-sky-900/60 dark:bg-slate-950/50">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Avg. setup
              </div>
              <div className="mt-1 text-lg font-semibold text-foreground">2 minutes</div>
            </div>
            <div className="rounded-lg border border-sky-100 bg-white/70 p-3 text-sm text-muted-foreground dark:border-sky-900/60 dark:bg-slate-950/50">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Review first
              </div>
              <div className="mt-1 text-lg font-semibold text-foreground">Always</div>
            </div>
            <div className="rounded-lg border border-sky-100 bg-white/70 p-3 text-sm text-muted-foreground dark:border-sky-900/60 dark:bg-slate-950/50">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Stored for
              </div>
              <div className="mt-1 text-lg font-semibold text-foreground">{retentionDays} days</div>
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
