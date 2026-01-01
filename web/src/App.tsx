import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ThemeToggle } from "@/components/theme-toggle";

const steps = [
  { id: "sign-in", label: "Sign in", status: "Required" },
  { id: "connect", label: "Connect accounts", status: "Sign in required" },
  { id: "review", label: "Review", status: "Connect accounts to continue" },
  { id: "import", label: "Import", status: "Approve review to continue" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="text-sm font-semibold tracking-[0.3em]">SKYBRIDGE</div>
          <ThemeToggle />
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
                {steps.map((step, index) => (
                  <div
                    key={step.id}
                    className={
                      "flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                    }
                  >
                    <span className="font-medium">
                      {index + 1} · {step.label}
                    </span>
                    <Badge variant={index === 0 ? "secondary" : "outline"}>
                      {index === 0 ? "Active" : "Locked"}
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </aside>

          <section className="space-y-4">
            <Accordion type="single" collapsible defaultValue="sign-in">
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
                      <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                        <ul className="list-disc space-y-1 pl-5">
                          <li>We import flights, times, routes, aircraft details, and remarks.</li>
                          <li>You can review everything before approving the import.</li>
                          <li>Credentials are used only for this job and never stored.</li>
                        </ul>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <Button>Sign in with email</Button>
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
                    <CardContent className="grid gap-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <div className="text-sm font-medium">CloudAhoy</div>
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="Email"
                          />
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="Password"
                            type="password"
                          />
                        </div>
                        <div className="space-y-2">
                          <div className="text-sm font-medium">FlySto</div>
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="Email"
                          />
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="Password"
                            type="password"
                          />
                        </div>
                      </div>
                      <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                        Credentials are used only for this job and not stored.
                      </div>
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="space-y-2">
                          <label className="text-xs text-muted-foreground">Start date</label>
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="YYYY-MM-DD"
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs text-muted-foreground">End date</label>
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="YYYY-MM-DD"
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs text-muted-foreground">Max flights</label>
                          <input
                            className="w-full rounded-md border px-3 py-2 text-sm"
                            placeholder="50"
                          />
                        </div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Leave empty to import all available flights. Caps the total number
                        of flights that will be imported.
                      </div>
                      <Button>Connect and review</Button>
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
                          <span className="font-medium">Review complete</span>
                          <span className="text-xs text-muted-foreground">
                            Elapsed: 2m · Last update: just now
                          </span>
                        </div>
                        <div className="mt-3 h-2 rounded-full bg-muted">
                          <div className="h-2 w-full rounded-full bg-emerald-500" />
                        </div>
                        <div className="mt-3 text-xs text-emerald-700">
                          Flights are fetched from CloudAhoy first so you can check them
                          before running the actual import.
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">Flights: 12</Badge>
                        <Badge variant="secondary">Hours: 24.6</Badge>
                        <Badge variant="warning">Registration missing: 2</Badge>
                      </div>
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
                          <TableRow>
                            <TableCell>
                              <Badge variant="success">OK</Badge>
                            </TableCell>
                            <TableCell>...inUjIKt47ulA</TableCell>
                            <TableCell>2025-11-21</TableCell>
                            <TableCell>N12SB</TableCell>
                            <TableCell>KPAO</TableCell>
                            <TableCell>KTVL</TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell>
                              <Badge variant="warning">Needs review</Badge>
                            </TableCell>
                            <TableCell>...DW98Fd25R6JM</TableCell>
                            <TableCell>2025-11-23</TableCell>
                            <TableCell>—</TableCell>
                            <TableCell>KSJC</TableCell>
                            <TableCell>KSNS</TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell>
                              <Badge variant="success">OK</Badge>
                            </TableCell>
                            <TableCell>...c_U0DMhib1NA</TableCell>
                            <TableCell>2025-11-24</TableCell>
                            <TableCell>N12SB</TableCell>
                            <TableCell>KPAO</TableCell>
                            <TableCell>KSOL</TableCell>
                          </TableRow>
                        </TableBody>
                      </Table>
                      <div className="flex flex-wrap gap-3">
                        <Button>Accept and start import</Button>
                        <Button variant="outline">Edit import filters</Button>
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
                    <CardContent>
                      <div className="rounded-md border bg-muted/40 p-4 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Import idle</span>
                          <span className="text-xs text-muted-foreground">
                            Elapsed: 0m · Last update: --
                          </span>
                        </div>
                        <div className="mt-3 h-2 rounded-full bg-muted">
                          <div className="h-2 w-1/4 rounded-full bg-primary" />
                        </div>
                      </div>
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
