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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ArrowRight } from "lucide-react";
import type { FlightSummary, ReviewSummary } from "@/api/client";
import * as React from "react";

/** Render ReviewSection component. */
export function ReviewSection({
  allowed,
  reviewComplete,
  reviewRunning,
  reviewApproved,
  showReviewProgress,
  reviewProgressCardClass,
  reviewStage,
  elapsed,
  lastUpdate,
  reviewProgress,
  reviewNoteClass,
  reviewSummary,
  flights,
  visibleFlights,
  showAllFlights,
  setShowAllFlights,
  reviewError,
  onRefresh,
  canApprove,
  importRunning,
  importComplete,
  actionLoading,
  onApproveImport,
  canEditFiltersNow,
  onEditFilters,
  formatDate,
}: {
  allowed: boolean;
  reviewComplete: boolean;
  reviewRunning: boolean;
  reviewApproved: boolean;
  showReviewProgress: boolean;
  reviewProgressCardClass: string;
  reviewStage: string;
  elapsed: string;
  lastUpdate: string;
  reviewProgress: number;
  reviewNoteClass: string;
  reviewSummary: ReviewSummary | null;
  flights: FlightSummary[];
  visibleFlights: FlightSummary[];
  showAllFlights: boolean;
  setShowAllFlights: (value: boolean) => void;
  reviewError?: string | null;
  onRefresh: () => void;
  canApprove: boolean;
  importRunning: boolean;
  importComplete: boolean;
  actionLoading: boolean;
  onApproveImport: () => void;
  canEditFiltersNow: boolean;
  onEditFilters: () => void;
  formatDate: (value?: string | null) => string;
}) {
  const [ackOpen, setAckOpen] = React.useState(false);
  const [acknowledged, setAcknowledged] = React.useState(false);

  React.useEffect(() => {
    if (!ackOpen) setAcknowledged(false);
  }, [ackOpen]);

  return (
    <AccordionItem
      value="review"
      className={cn(
        "border-0 px-4 sm:px-5 bg-transparent",
        !allowed && "opacity-60"
      )}
    >
      <AccordionTrigger
        disabled={!allowed}
        className={!allowed ? "font-normal text-muted-foreground" : undefined}
      >
        <div className="flex w-full items-center justify-between">
          <span>2 · Review</span>
          <Badge
            variant={reviewComplete ? "success" : reviewRunning ? "active" : "outline"}
            className={!allowed ? "border-dashed" : undefined}
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
        <div className="space-y-3 pb-6">
          {showReviewProgress && (
            <div className={reviewProgressCardClass}>
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    "flex items-center gap-2 font-medium",
                    reviewComplete
                      ? "text-emerald-800 dark:text-emerald-300"
                      : reviewRunning
                        ? "text-sky-800 dark:text-sky-300"
                        : ""
                  )}
                >
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      reviewComplete
                        ? "bg-emerald-500"
                        : reviewRunning
                          ? "bg-sky-500 animate-pulse"
                          : "bg-muted-foreground/40"
                    )}
                  />
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
                      ? "bg-emerald-100 dark:bg-emerald-950/50"
                      : reviewRunning
                        ? "bg-sky-100 dark:bg-sky-950/50"
                        : undefined
                  }
                  indicatorClassName={
                    reviewComplete
                      ? "bg-emerald-600 dark:bg-emerald-400"
                      : reviewRunning
                        ? "bg-sky-600 dark:bg-sky-400"
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
            <div className="flex flex-wrap gap-2 rounded-xl border border-border/30 bg-muted/20 p-3 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/30">
              <Badge
                variant="secondary"
                className="border border-[hsl(var(--sky-accent))]/20 text-foreground dark:border-[hsl(var(--sky-accent))]/25 dark:bg-[hsl(var(--sky-accent))]/8"
              >
                <span className="tabular-nums">Flights: {reviewSummary.flight_count}</span>
              </Badge>
              <Badge
                variant="secondary"
                className="border border-[hsl(var(--sky-accent))]/20 text-foreground dark:border-[hsl(var(--sky-accent))]/25 dark:bg-[hsl(var(--sky-accent))]/8"
              >
                <span className="tabular-nums">Hours: {reviewSummary.total_hours}</span>
              </Badge>
              <Badge
                variant={reviewSummary.missing_tail_numbers > 0 ? "warning" : "secondary"}
                className={
                  reviewSummary.missing_tail_numbers > 0
                    ? undefined
                    : "border border-[hsl(var(--sky-accent))]/20 text-foreground dark:border-[hsl(var(--sky-accent))]/25 dark:bg-[hsl(var(--sky-accent))]/8"
                }
              >
                <span className="tabular-nums">
                  Registration missing: {reviewSummary.missing_tail_numbers}
                </span>
              </Badge>
            </div>
          )}
          {reviewComplete && (
            <div className="relative w-full max-w-full overflow-x-auto rounded-xl border border-border/30 bg-background/70 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/30">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.03),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.06),_transparent_60%)]" />
              <Table className="w-full min-w-[640px]">
                <TableHeader className="bg-muted/30 dark:bg-[hsl(var(--cockpit-dark))]/50">
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Registration</TableHead>
                    <TableHead>From / To</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleFlights.map((flight, index) => (
                    <TableRow
                      key={flight.flight_id}
                      className={
                        index % 2 === 0 ? "bg-muted/40 dark:bg-slate-900/30" : undefined
                      }
                    >
                      <TableCell>
                        <Badge
                          variant={flight.tail_number ? "success" : "warning"}
                          className="min-w-[110px] justify-center"
                        >
                          {flight.tail_number ? "OK" : "Needs review"}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatDate(flight.date)}</TableCell>
                      <TableCell>{flight.tail_number ?? "—"}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-2">
                          <span className="tabular-nums">{flight.origin ?? "—"}</span>
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="tabular-nums">{flight.destination ?? "—"}</span>
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {reviewComplete && flights.length > 3 && !showAllFlights && (
            <div className="flex">
              <Button
                variant="link"
                className="h-auto px-0 text-sm text-muted-foreground"
                onClick={() => setShowAllFlights(true)}
              >
                Show more flights
              </Button>
            </div>
          )}
          {reviewComplete && flights.length > 3 && showAllFlights && (
            <div className="text-sm text-muted-foreground">All flights shown</div>
          )}
          {reviewError && (
            <Alert variant="destructive">
              <AlertTitle>Something went wrong</AlertTitle>
              <AlertDescription>{reviewError}</AlertDescription>
              <div className="mt-3">
                <Button size="sm" variant="outline" onClick={onRefresh}>
                  Retry
                </Button>
              </div>
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <AlertDialog open={ackOpen} onOpenChange={setAckOpen}>
              <AlertDialogTrigger asChild>
                <Button
                  disabled={!canApprove || importRunning || importComplete || actionLoading}
                  className="btn-primary-glow"
                >
                  Accept and start import
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Confirm import</AlertDialogTitle>
                  <AlertDialogDescription>
                    By proceeding, you acknowledge that you are using Skybridge at your own risk.
                    Inspirespace e.U. is not responsible for any damages, data loss, or other issues
                    resulting from this import.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <label className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 accent-sky-600"
                    checked={acknowledged}
                    onChange={(event) => setAcknowledged(event.target.checked)}
                  />
                  <span>I understand and want to proceed with the import.</span>
                </label>
                <AlertDialogFooter className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                  <AlertDialogAction onClick={onApproveImport} disabled={!acknowledged}>
                    Start import
                  </AlertDialogAction>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            {canEditFiltersNow && (
              <Button variant="outline" onClick={onEditFilters}>
                Edit import filters
              </Button>
            )}
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
