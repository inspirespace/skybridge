import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { Calendar as CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";
import * as React from "react";

/** Render ConnectSection component. */
export function ConnectSection({
  allowed,
  connected,
  signedIn,
  connectLocked,
  canConnect,
  rangeIncomplete,
  dateRange,
  dateRangeLabel,
  maxFlights,
  cloudahoyEmail,
  cloudahoyPassword,
  flystoEmail,
  flystoPassword,
  setCloudahoyEmail,
  setCloudahoyPassword,
  setFlystoEmail,
  setFlystoPassword,
  setDateRange,
  setMaxFlights,
  onConnectReview,
  actionLoading,
  connectError,
  onRefresh,
}: {
  allowed: boolean;
  connected: boolean;
  signedIn: boolean;
  connectLocked: boolean;
  canConnect: boolean;
  rangeIncomplete: boolean;
  dateRange?: DateRange;
  dateRangeLabel: string;
  maxFlights: string;
  cloudahoyEmail: string;
  cloudahoyPassword: string;
  flystoEmail: string;
  flystoPassword: string;
  setCloudahoyEmail: (value: string) => void;
  setCloudahoyPassword: (value: string) => void;
  setFlystoEmail: (value: string) => void;
  setFlystoPassword: (value: string) => void;
  setDateRange: (value?: DateRange) => void;
  setMaxFlights: (value: string) => void;
  onConnectReview: () => void;
  actionLoading: boolean;
  connectError?: string | null;
  onRefresh: () => void;
}) {
  const [isDesktop, setIsDesktop] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const media = window.matchMedia("(min-width: 768px)");
    /** Update . */
    const update = () => setIsDesktop(media.matches);
    update();
    if (media.addEventListener) {
      media.addEventListener("change", update);
      return () => media.removeEventListener("change", update);
    }
    media.addListener(update);
    return () => media.removeListener(update);
  }, []);

  return (
    <AccordionItem
      value="connect"
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
          <span>1 · Connect accounts</span>
          <Badge variant={connected ? "success" : "outline"} className={!allowed ? "border-dashed" : undefined}>
            {connected ? "Connected" : signedIn ? "Required" : "Sign in required"}
          </Badge>
        </div>
      </AccordionTrigger>
      <AccordionContent>
        <div className="space-y-4 pb-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Enter CloudAhoy and FlySto credentials, then run the review.
          </p>
          <Alert className="border-sky-100 bg-sky-50/60 text-slate-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-slate-100">
            <AlertTitle>Credentials</AlertTitle>
            <AlertDescription>Credentials are used only for this job and not stored.</AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="text-sm font-medium">CloudAhoy</div>
              <div className="relative space-y-2 overflow-hidden rounded-md border border-[#d9e1ec] bg-[#f8fafc] p-3 dark:border-sky-900/60 dark:bg-slate-900/80">
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.08),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.16),_transparent_60%)]" />
                <Label htmlFor="cloudahoy-email">Email</Label>
                <Input
                  id="cloudahoy-email"
                  placeholder="Email"
                  disabled={connectLocked}
                  value={cloudahoyEmail}
                  onChange={(event) => setCloudahoyEmail(event.target.value)}
                />
                <Label htmlFor="cloudahoy-password">Password</Label>
                <Input
                  id="cloudahoy-password"
                  type="password"
                  placeholder="Password"
                  disabled={connectLocked}
                  value={cloudahoyPassword}
                  onChange={(event) => setCloudahoyPassword(event.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <div className="text-sm font-medium">FlySto</div>
              <div className="relative space-y-2 overflow-hidden rounded-md border border-[#d9e1ec] bg-[#f8fafc] p-3 dark:border-sky-900/60 dark:bg-slate-900/80">
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.08),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.16),_transparent_60%)]" />
                <Label htmlFor="flysto-email">Email</Label>
                <Input
                  id="flysto-email"
                  placeholder="Email"
                  disabled={connectLocked}
                  value={flystoEmail}
                  onChange={(event) => setFlystoEmail(event.target.value)}
                />
                <Label htmlFor="flysto-password">Password</Label>
                <Input
                  id="flysto-password"
                  type="password"
                  placeholder="Password"
                  disabled={connectLocked}
                  value={flystoPassword}
                  onChange={(event) => setFlystoPassword(event.target.value)}
                />
              </div>
            </div>
          </div>

          <Separator className="my-1" />

          <div className="relative rounded-md border border-[#d9e1ec] bg-[#f8fafc] p-3 dark:border-sky-900/60 dark:bg-slate-900/80">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.08),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.16),_transparent_60%)]" />
            <div className="space-y-3">
              <div className="text-sm font-semibold">Import filters</div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2 md:col-span-2">
                  <Label>Date range</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className={cn(
                          "h-9 w-full justify-start text-left font-normal border-input bg-white/70 hover:bg-white/70 dark:bg-slate-900/70 dark:border-sky-900/60 dark:hover:bg-slate-900/70",
                          !dateRange?.from && "text-muted-foreground"
                        )}
                        disabled={connectLocked}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateRangeLabel}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-3" align="start">
                      <Calendar
                        mode="range"
                        fixedWeeks
                        numberOfMonths={isDesktop ? 2 : 1}
                        selected={dateRange}
                        onSelect={setDateRange}
                        fromYear={2000}
                        toYear={new Date().getFullYear() + 1}
                        disabled={connectLocked}
                      />
                      <div className="mt-3 flex items-center justify-between">
                        <div className="text-xs text-muted-foreground">
                          Leave empty to import all available flights.
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setDateRange(undefined)}
                          disabled={connectLocked || !dateRange?.from}
                        >
                          Clear dates
                        </Button>
                      </div>
                      {rangeIncomplete && (
                        <div className="mt-2 text-xs text-amber-600">
                          Select an end date or clear the range.
                        </div>
                      )}
                    </PopoverContent>
                  </Popover>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-flights">Max flights to import</Label>
                  <Input
                    id="max-flights"
                    type="number"
                    min={1}
                    step={1}
                    inputMode="numeric"
                    placeholder="50"
                    disabled={connectLocked}
                    value={maxFlights}
                    onChange={(event) => {
                      const next = event.target.value;
                      if (next === "" || /^[0-9]+$/.test(next)) {
                        setMaxFlights(next);
                      }
                    }}
                  />
                </div>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Caps the total number of flights that will be imported.
              </p>
            </div>
          </div>

          {connectError && (
            <Alert variant="destructive">
              <AlertTitle>Something went wrong</AlertTitle>
              <AlertDescription>{connectError}</AlertDescription>
              <div className="mt-3">
                <Button size="sm" variant="outline" onClick={onRefresh}>
                  Retry
                </Button>
              </div>
            </Alert>
          )}

          <Button
            onClick={onConnectReview}
            disabled={connectLocked || !canConnect || rangeIncomplete || actionLoading}
            className="shadow-sm"
          >
            Connect and review
          </Button>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
