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
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ImportResults } from "@/components/import-results";
import { cn } from "@/lib/utils";
import type { JobRecord } from "@/api/client";

export function ImportSection({
  allowed,
  importComplete,
  importRunning,
  reviewComplete,
  showImportProgress,
  importProgressCardClass,
  importStage,
  elapsed,
  lastUpdate,
  importProgress,
  latestImportEvent,
  formatFlightId,
  formatLastUpdate,
  now,
  job,
  reviewSummaryMissing,
  retentionDays,
  onDownloadFiles,
  onDeleteResults,
  actionLoading,
  importError,
  onRefresh,
}: {
  allowed: boolean;
  importComplete: boolean;
  importRunning: boolean;
  reviewComplete: boolean;
  showImportProgress: boolean;
  importProgressCardClass: string;
  importStage: string;
  elapsed: string;
  lastUpdate: string;
  importProgress: number;
  latestImportEvent?: { stage: string; flight_id?: string | null; percent?: number | null; created_at: string } | null;
  formatFlightId: (value: { flight_id?: string | null }) => string;
  formatLastUpdate: (value?: string | null, now?: Date) => string;
  now: Date;
  job?: JobRecord | null;
  reviewSummaryMissing: number;
  retentionDays: number;
  onDownloadFiles: () => void;
  onDeleteResults: () => void;
  actionLoading: boolean;
  importError?: string | null;
  onRefresh: () => void;
}) {
  return (
    <AccordionItem
      value="import"
      className={cn(
        "border-0 px-4 bg-white dark:bg-transparent",
        !allowed && "bg-[#f7fafd] dark:bg-slate-900/60"
      )}
    >
      <AccordionTrigger
        disabled={!allowed}
        className={!allowed ? "font-normal text-muted-foreground" : undefined}
      >
        <div className="flex w-full items-center justify-between">
          <span>4 · Import</span>
          <Badge
            variant={
              importComplete ? "success" : importRunning ? "active" : reviewComplete ? "secondary" : "outline"
            }
            className={!allowed ? "border-dashed" : undefined}
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
                  className={cn(
                    "flex items-center gap-2 font-medium",
                    importComplete
                      ? "text-emerald-800 dark:text-emerald-300"
                      : importRunning
                        ? "text-sky-800 dark:text-sky-300"
                        : ""
                  )}
                >
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      importComplete
                        ? "bg-emerald-500"
                        : importRunning
                          ? "bg-sky-500 animate-pulse"
                          : "bg-muted-foreground/40"
                    )}
                  />
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
                      ? "bg-emerald-100 dark:bg-emerald-950/50"
                      : importRunning
                        ? "bg-sky-100 dark:bg-sky-950/50"
                        : undefined
                  }
                  indicatorClassName={
                    importComplete
                      ? "bg-emerald-600 dark:bg-emerald-400"
                      : importRunning
                        ? "bg-sky-600 dark:bg-sky-400"
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
                  {latestImportEvent.percent != null ? ` · ${latestImportEvent.percent}%` : ""}
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
              registrationMissing={reviewSummaryMissing}
            />
          )}
          {importComplete && (
            <Alert className="border-emerald-200/70 bg-emerald-50/50 dark:border-emerald-900/50 dark:bg-emerald-950/40">
              <AlertTitle>Next steps</AlertTitle>
              <AlertDescription>
                Review your imported flights in FlySto, download the files for your
                records, and keep this page bookmarked while results are retained for
                {" "}
                {retentionDays} days before deletion.
              </AlertDescription>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button asChild>
                  <a href="https://www.flysto.net/logs" target="_blank" rel="noreferrer">
                    Open FlySto
                  </a>
                </Button>
                <Button variant="outline" onClick={onDownloadFiles} disabled={actionLoading}>
                  Download files
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive">Delete results now</Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete import results?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This removes the stored reports and review summary for this run.
                        This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={onDeleteResults}
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
                <Button size="sm" variant="outline" onClick={onRefresh}>
                  Retry
                </Button>
              </div>
            </Alert>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
