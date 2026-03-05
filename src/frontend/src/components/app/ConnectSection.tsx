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
import { cn } from "@/lib/utils";
import { formatISODate } from "@/lib/format";
import { Calendar as CalendarIcon } from "lucide-react";

/** Render ConnectSection component. */
export function ConnectSection({
  allowed,
  connected,
  signedIn,
  connectLocked,
  canConnect,
  startDate,
  endDate,
  startDateInput,
  endDateInput,
  setStartDateInput,
  setEndDateInput,
  dateRangeError,
  maxFlights,
  cloudahoyEmail,
  cloudahoyPassword,
  flystoEmail,
  flystoPassword,
  setCloudahoyEmail,
  setCloudahoyPassword,
  setFlystoEmail,
  setFlystoPassword,
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
  startDate?: Date;
  endDate?: Date;
  startDateInput: string;
  endDateInput: string;
  setStartDateInput: (value: string) => void;
  setEndDateInput: (value: string) => void;
  dateRangeError: string | null;
  maxFlights: string;
  cloudahoyEmail: string;
  cloudahoyPassword: string;
  flystoEmail: string;
  flystoPassword: string;
  setCloudahoyEmail: (value: string) => void;
  setCloudahoyPassword: (value: string) => void;
  setFlystoEmail: (value: string) => void;
  setFlystoPassword: (value: string) => void;
  setMaxFlights: (value: string) => void;
  onConnectReview: () => void;
  actionLoading: boolean;
  connectError?: string | null;
  onRefresh: () => void;
}) {
  return (
    <AccordionItem
      value="connect"
      className={cn(
        "flow-accordion-item border-0 px-4 sm:px-5 bg-transparent",
        !allowed && "opacity-60"
      )}
    >
      <AccordionTrigger
        disabled={!allowed}
        className={cn(
          "flow-accordion-trigger",
          !allowed && "font-normal text-muted-foreground"
        )}
      >
        <div className="flex w-full items-center justify-between gap-3">
          <div className="flow-accordion-title">
            <span className="flow-accordion-icon" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </span>
            <span className="flow-accordion-label">1. Connect Accounts</span>
          </div>
          <Badge
            variant={connected ? "success" : "outline"}
            className={cn("flow-accordion-badge", !allowed && "border-dashed")}
          >
            {connected ? "Connected" : signedIn ? "Required" : "Sign in required"}
          </Badge>
        </div>
      </AccordionTrigger>
      <AccordionContent>
        <div className="space-y-4 pb-6">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Enter CloudAhoy and FlySto credentials, then run the review.
          </p>
          <Alert className="border-[hsl(var(--sky-accent))]/20 bg-[hsl(var(--sky-accent))]/5 text-foreground dark:border-[hsl(var(--sky-accent))]/25 dark:bg-[hsl(var(--sky-accent))]/8">
            <AlertTitle className="text-[hsl(var(--sky-accent))]">Credentials</AlertTitle>
            <AlertDescription className="text-muted-foreground">Credentials are used only for this job and not stored.</AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Decoy login fields to divert aggressive password managers. */}
            <div className="sr-only" aria-hidden="true">
              <input
                type="text"
                name="username"
                autoComplete="username"
                tabIndex={-1}
                defaultValue=""
                readOnly
              />
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                tabIndex={-1}
                defaultValue=""
                readOnly
              />
            </div>
            <div className="space-y-2">
              <div className="text-sm font-semibold text-foreground">CloudAhoy</div>
              <div className="relative space-y-3 overflow-hidden rounded-xl border border-border/40 bg-muted/30 p-4 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/40">
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.03),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.06),_transparent_60%)]" />
                <Label htmlFor="cloudahoy-email">Email</Label>
                <Input
                  id="cloudahoy-email"
                  name="cloudahoy-import-id"
                  autoComplete="off"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  data-lpignore="true"
                  data-1p-ignore="true"
                  data-bwignore="true"
                  data-form-type="other"
                  placeholder="Email"
                  disabled={connectLocked}
                  value={cloudahoyEmail}
                  onChange={(event) => setCloudahoyEmail(event.target.value)}
                />
                <Label htmlFor="cloudahoy-password">Password</Label>
                <Input
                  id="cloudahoy-password"
                  type="password"
                  name="cloudahoy-secret"
                  autoComplete="off"
                  data-lpignore="true"
                  data-1p-ignore="true"
                  data-bwignore="true"
                  data-form-type="other"
                  placeholder="Password"
                  disabled={connectLocked}
                  value={cloudahoyPassword}
                  onChange={(event) => setCloudahoyPassword(event.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <div className="text-sm font-semibold text-foreground">FlySto</div>
              <div className="relative space-y-3 overflow-hidden rounded-xl border border-border/40 bg-muted/30 p-4 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/40">
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.03),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.06),_transparent_60%)]" />
                <Label htmlFor="flysto-email">Email</Label>
                <Input
                  id="flysto-email"
                  name="flysto-import-id"
                  autoComplete="off"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  data-lpignore="true"
                  data-1p-ignore="true"
                  data-bwignore="true"
                  data-form-type="other"
                  placeholder="Email"
                  disabled={connectLocked}
                  value={flystoEmail}
                  onChange={(event) => setFlystoEmail(event.target.value)}
                />
                <Label htmlFor="flysto-password">Password</Label>
                <Input
                  id="flysto-password"
                  type="password"
                  name="flysto-secret"
                  autoComplete="off"
                  data-lpignore="true"
                  data-1p-ignore="true"
                  data-bwignore="true"
                  data-form-type="other"
                  placeholder="Password"
                  disabled={connectLocked}
                  value={flystoPassword}
                  onChange={(event) => setFlystoPassword(event.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="relative rounded-xl border border-border/40 bg-muted/30 p-4 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/40">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.03),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--sky-accent)/0.06),_transparent_60%)]" />
            <div className="space-y-3">
              <div className="text-sm font-semibold text-foreground">Import filters</div>
              <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                <div className="space-y-2">
                  <Label>Date range</Label>
                  <div className="grid gap-2 md:grid-cols-2">
                    <div className="space-y-1.5">
                      <div className="h-4 text-xs leading-4 text-muted-foreground">Start date</div>
                      <div className="relative">
                        <Input
                          id="start-date"
                          placeholder="YYYY-MM-DD"
                          disabled={connectLocked}
                          value={startDateInput}
                          onChange={(event) => setStartDateInput(event.target.value)}
                          className={cn("pr-10", dateRangeError && "border-amber-400")}
                        />
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={connectLocked}
                              className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 text-muted-foreground/80 hover:text-foreground hover:bg-transparent"
                            >
                <CalendarIcon className="h-4 w-4 cursor-pointer" />
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-3" align="start">
                            <Calendar
                              mode="single"
                              fixedWeeks
                              numberOfMonths={1}
                              selected={startDate}
                              onSelect={(value) => {
                                setStartDateInput(value ? formatISODate(value) : "");
                              }}
                              fromYear={2000}
                              toYear={new Date().getFullYear() + 1}
                              disabled={connectLocked}
                            />
                          </PopoverContent>
                        </Popover>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <div className="h-4 text-xs leading-4 text-muted-foreground">End date</div>
                      <div className="relative">
                        <Input
                          id="end-date"
                          placeholder="YYYY-MM-DD"
                          disabled={connectLocked}
                          value={endDateInput}
                          onChange={(event) => setEndDateInput(event.target.value)}
                          className={cn("pr-10", dateRangeError && "border-amber-400")}
                        />
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={connectLocked}
                              className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 text-muted-foreground/80 hover:text-foreground hover:bg-transparent"
                            >
                              <CalendarIcon className="h-4 w-4" />
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-3" align="start">
                            <Calendar
                              mode="single"
                              fixedWeeks
                              numberOfMonths={1}
                              selected={endDate}
                              onSelect={(value) => {
                                setEndDateInput(value ? formatISODate(value) : "");
                              }}
                              fromYear={2000}
                              toYear={new Date().getFullYear() + 1}
                              disabled={connectLocked}
                            />
                          </PopoverContent>
                        </Popover>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="text-xs text-muted-foreground">
                      Leave both dates empty to import all available flights.
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setStartDateInput("");
                        setEndDateInput("");
                      }}
                      disabled={connectLocked || (!startDateInput && !endDateInput)}
                      className="ml-auto h-7 px-2 text-xs font-medium text-muted-foreground/80 hover:text-foreground"
                    >
                      Clear dates
                    </Button>
                  </div>
                  {dateRangeError && (
                    <div className="text-xs text-amber-600">{dateRangeError}</div>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-flights">Max flights to import</Label>
                  <div className="h-[14px]" aria-hidden />
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
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Caps the total number of flights that will be imported.
                  </p>
                </div>
              </div>
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
            disabled={connectLocked || !canConnect || Boolean(dateRangeError) || actionLoading}
            className="btn-primary-glow"
          >
            Connect and review
          </Button>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
