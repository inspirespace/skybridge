import * as React from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  canApproveImport,
  canEditFilters,
  canStartOver,
  getOpenStep,
  initialFlowState,
  type FlowState,
} from "@/state/flow";

const mockFlights = [
  {
    id: "...inUjIKt47ulA",
    date: "2025-11-21",
    registration: "N12SB",
    origin: "KPAO",
    destination: "KTVL",
    status: "OK",
  },
  {
    id: "...DW98Fd25R6JM",
    date: "2025-11-23",
    registration: "—",
    origin: "KSJC",
    destination: "KSNS",
    status: "Needs review",
  },
  {
    id: "...c_U0DMhib1NA",
    date: "2025-11-24",
    registration: "N12SB",
    origin: "KPAO",
    destination: "KSOL",
    status: "OK",
  },
];

export default function App() {
  const [flow, setFlow] = React.useState<FlowState>(initialFlowState);

  const reviewComplete = flow.reviewStatus === "complete";
  const importComplete = flow.importStatus === "complete";
  const reviewRunning = flow.reviewStatus === "running";
  const importRunning = flow.importStatus === "running";

  const openStep = React.useMemo(() => getOpenStep(flow), [flow]);

  const handleSignIn = () => {
    setFlow((prev) => ({ ...prev, signedIn: true }));
  };

  const handleConnectReview = () => {
    setFlow((prev) => ({
      ...prev,
      connected: true,
      reviewStatus: "running",
      importStatus: "idle",
    }));
  };

  React.useEffect(() => {
    if (!reviewRunning) return;
    const timer = window.setTimeout(() => {
      setFlow((prev) => ({ ...prev, reviewStatus: "complete" }));
    }, 1400);
    return () => window.clearTimeout(timer);
  }, [reviewRunning]);

  const handleApproveImport = () => {
    setFlow((prev) => ({ ...prev, importStatus: "running" }));
  };

  React.useEffect(() => {
    if (!importRunning) return;
    const timer = window.setTimeout(() => {
      setFlow((prev) => ({ ...prev, importStatus: "complete" }));
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [importRunning]);

  const handleEditFilters = () => {
    setFlow((prev) => ({
      ...prev,
      connected: false,
      reviewStatus: "idle",
      importStatus: "idle",
    }));
  };

  const handleStartOver = () => {
    setFlow(initialFlowState);
  };

  const handleSignOut = () => {
    setFlow(initialFlowState);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="text-sm font-semibold tracking-[0.3em]">SKYBRIDGE</div>
          <div className="flex items-center gap-4">
            {flow.signedIn && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleStartOver}
                disabled={!canStartOver(flow)}
              >
                Start over
              </Button>
            )}
            {flow.signedIn && (
              <Button variant="outline" size="sm" onClick={handleSignOut}>
                Sign out
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="container py-8">
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-[0.25em] text-muted-foreground">
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <StepStatus label="1 · Sign in" active={!flow.signedIn} done={flow.signedIn} />
                <StepStatus label="2 · Connect" active={flow.signedIn && !flow.connected} done={flow.connected} />
                <StepStatus label="3 · Review" active={flow.connected && !reviewComplete} done={reviewComplete} />
                <StepStatus label="4 · Import" active={reviewComplete && !importComplete} done={importComplete} />
              </CardContent>
            </Card>
          </aside>

          <section className="space-y-4">
            <Accordion type="single" collapsible value={openStep}>
              <AccordionItem value="sign-in">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>1 · Sign in</span>
                    <Badge variant="secondary">Required</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Sign in</CardTitle>
                      <CardDescription>
                        Skybridge imports your CloudAhoy flights into FlySto. You’ll
                        connect both accounts, review the summary, and approve the
                        import.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <Alert>
                        <AlertTitle>What you can expect</AlertTitle>
                        <AlertDescription>
                          <ul className="list-disc space-y-1 pl-5">
                            <li>We import flights, times, routes, aircraft details, and remarks.</li>
                            <li>You can review everything before approving the import.</li>
                            <li>Credentials are used only for this job and never stored.</li>
                          </ul>
                        </AlertDescription>
                      </Alert>
                      <div className="flex flex-wrap gap-3">
                        <Button onClick={handleSignIn}>Sign in with email</Button>
                        <Button variant="outline">Continue with Google</Button>
                        <Button variant="outline">Continue with Apple</Button>
                      </div>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="connect">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>2 · Connect accounts</span>
                    <Badge variant="outline">Sign in required</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Connect accounts</CardTitle>
                      <CardDescription>
                        Enter CloudAhoy and FlySto credentials, then run the review.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <Alert variant="default">
                        <AlertTitle>Credentials</AlertTitle>
                        <AlertDescription>
                          Credentials are used only for this job and not stored.
                        </AlertDescription>
                      </Alert>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <div className="text-sm font-medium">CloudAhoy</div>
                          <div className="space-y-2">
                            <Label htmlFor="cloudahoy-email">Email</Label>
                            <Input id="cloudahoy-email" placeholder="Email" />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="cloudahoy-password">Password</Label>
                            <Input id="cloudahoy-password" type="password" placeholder="Password" />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="text-sm font-medium">FlySto</div>
                          <div className="space-y-2">
                            <Label htmlFor="flysto-email">Email</Label>
                            <Input id="flysto-email" placeholder="Email" />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="flysto-password">Password</Label>
                            <Input id="flysto-password" type="password" placeholder="Password" />
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="space-y-2">
                          <Label htmlFor="start-date">Start date</Label>
                          <Input id="start-date" placeholder="YYYY-MM-DD" />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="end-date">End date</Label>
                          <Input id="end-date" placeholder="YYYY-MM-DD" />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="max-flights">Max flights</Label>
                          <Input id="max-flights" placeholder="50" />
                        </div>
                      </div>

                      <p className="text-xs text-muted-foreground">
                        Leave empty to import all available flights. Caps the total number
                        of flights that will be imported.
                      </p>

                      <Button onClick={handleConnectReview}>Connect and review</Button>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="review">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>3 · Review</span>
                    <Badge variant="outline">Connect accounts to continue</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Review</CardTitle>
                      <CardDescription>
                        Flights are fetched first so you can verify the summary before
                        importing.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-md border bg-muted/40 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">
                            {reviewComplete ? "Review complete" : "Review running"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            Elapsed: 2m · Last update: just now
                          </span>
                        </div>
                        <div className="mt-3">
                          <Progress value={reviewComplete ? 100 : 60} />
                        </div>
                        <div className="mt-3 text-xs text-emerald-700">
                          Flights are fetched from CloudAhoy first so you can check them
                          before running the actual import.
                        </div>
                      </div>
                      {reviewComplete && (
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">Flights: 12</Badge>
                          <Badge variant="secondary">Hours: 24.6</Badge>
                          <Badge variant="warning">Registration missing: 2</Badge>
                        </div>
                      )}
                      {reviewComplete && (
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Status</TableHead>
                              <TableHead>Flight ID</TableHead>
                              <TableHead>Date</TableHead>
                              <TableHead>Registration</TableHead>
                              <TableHead>Origin</TableHead>
                              <TableHead>Destination</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {mockFlights.map((flight) => (
                              <TableRow key={flight.id}>
                                <TableCell>
                                  <Badge
                                    variant={
                                      flight.status === "OK" ? "success" : "warning"
                                    }
                                  >
                                    {flight.status}
                                  </Badge>
                                </TableCell>
                                <TableCell>{flight.id}</TableCell>
                                <TableCell>{flight.date}</TableCell>
                                <TableCell>{flight.registration}</TableCell>
                                <TableCell>{flight.origin}</TableCell>
                                <TableCell>{flight.destination}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      )}
                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={handleApproveImport}
                          disabled={!canApproveImport(flow) || importRunning || importComplete}
                        >
                          Accept and start import
                        </Button>
                        <Button
                          variant="outline"
                          onClick={handleEditFilters}
                          disabled={!canEditFilters(flow)}
                        >
                          Edit import filters
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="import">
                <AccordionTrigger>
                  <div className="flex items-center gap-3">
                    <span>4 · Import</span>
                    <Badge variant="outline">Approve review to continue</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <Card>
                    <CardHeader>
                      <CardTitle>Import</CardTitle>
                      <CardDescription>
                        Import runs after approval and produces a report summary.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-md border bg-muted/40 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">
                            {importComplete
                              ? "Import complete"
                              : importRunning
                                ? "Import running"
                                : "Import idle"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            Elapsed: 0m · Last update: --
                          </span>
                        </div>
                        <div className="mt-3">
                          <Progress value={importComplete ? 100 : importRunning ? 45 : 10} />
                        </div>
                      </div>
                      {importComplete && (
                        <Alert>
                          <AlertTitle>Next steps</AlertTitle>
                          <AlertDescription>
                            Review your imported flights in FlySto, download the report for
                            your records, and keep this page bookmarked while results are
                            retained.
                          </AlertDescription>
                        </Alert>
                      )}
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </section>
        </div>
      </main>

      <footer className="border-t bg-background/80">
        <div className="container flex flex-wrap items-center justify-between gap-3 py-6 text-sm text-muted-foreground">
          <div>© 2026 Inspirespace e.U.</div>
          <div className="flex flex-wrap gap-4">
            <a className="hover:text-foreground" href="#">Imprint</a>
            <a className="hover:text-foreground" href="#">Privacy</a>
            <a className="hover:text-foreground" href="#">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StepStatus({ label, active, done }: { label: string; active?: boolean; done?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
      <span className={active ? "font-semibold" : "font-medium"}>{label}</span>
      <Badge variant={done ? "success" : "outline"}>{done ? "Done" : active ? "Active" : "Locked"}</Badge>
    </div>
  );
}
