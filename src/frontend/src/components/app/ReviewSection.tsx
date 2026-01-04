import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  return (
    <AccordionItem
      value="review"
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
          <span>3 · Review</span>
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
        <div className="space-y-3 pb-4">
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
            <div className="flex flex-wrap gap-2 rounded-md border border-[#e3ebf5] bg-muted/20 p-2 shadow-sm dark:border-sky-900/60 dark:bg-slate-950/40">
              <Badge
                variant="secondary"
                className="border border-sky-200/40 text-foreground dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-100"
              >
                <span className="tabular-nums">Flights: {reviewSummary.flight_count}</span>
              </Badge>
              <Badge
                variant="secondary"
                className="border border-sky-200/40 text-foreground dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-100"
              >
                <span className="tabular-nums">Hours: {reviewSummary.total_hours}</span>
              </Badge>
              <Badge
                variant={reviewSummary.missing_tail_numbers > 0 ? "warning" : "secondary"}
                className={
                  reviewSummary.missing_tail_numbers > 0
                    ? undefined
                    : "border border-sky-200/40 text-foreground dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-100"
                }
              >
                <span className="tabular-nums">
                  Registration missing: {reviewSummary.missing_tail_numbers}
                </span>
              </Badge>
            </div>
          )}
          {reviewComplete && (
            <div className="overflow-x-auto rounded-md border border-[#e3ebf5] bg-background/70 shadow-sm dark:border-sky-900/60 dark:bg-slate-950/40">
              <Table className="min-w-[640px]">
                <TableHeader className="bg-muted/40 dark:bg-slate-900/60">
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
            <Button
              onClick={onApproveImport}
              disabled={!canApprove || importRunning || importComplete || actionLoading}
              className="shadow-sm"
            >
              Accept and start import
            </Button>
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
