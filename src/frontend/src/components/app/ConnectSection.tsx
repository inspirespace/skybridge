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
import * as React from "react";

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

          <div className="relative rounded-md border border-[#d9e1ec] bg-[#f8fafc] p-3 dark:border-sky-900/60 dark:bg-slate-900/80">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.08),_transparent_60%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.16),_transparent_60%)]" />
            <div className="space-y-3">
              <div className="text-sm font-semibold">Import filters</div>
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
                              <CalendarIcon className="h-4 w-4" />
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
            className="shadow-sm"
          >
            Connect and review
          </Button>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
