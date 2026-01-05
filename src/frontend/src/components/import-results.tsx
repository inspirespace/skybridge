import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Type ImportResultsProps. */
export type ImportResultsProps = {
  imported: number;
  skipped: number;
  failed: number;
  registrationMissing: number;
};

/** Render ImportResults component. */
export function ImportResults({
  imported,
  skipped,
  failed,
  registrationMissing,
}: ImportResultsProps) {
  const skippedFailedTotal = skipped + failed;
  const totalProcessed = imported + skippedFailedTotal;
  const skippedBadge =
    skippedFailedTotal > 0 ? (
      <Badge variant="warning">Needs review</Badge>
    ) : (
      <Badge variant="success">OK</Badge>
    );
  const registrationBadge =
    registrationMissing > 0 ? (
      <Badge variant="warning">Needs review</Badge>
    ) : (
      <Badge variant="success">OK</Badge>
    );
  return (
    <Card className="border border-[#e3ebf5] bg-card/90 shadow-sm dark:border-sky-900/60 dark:bg-slate-950/40">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Import results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <ResultRow
          label="Total processed"
          description="All flights considered during this import."
          total={totalProcessed}
          badge={<Badge variant="success">OK</Badge>}
        />
        <ResultRow
          label="Imported flights"
          description="All approved flights created in FlySto."
          total={imported}
          badge={<Badge variant="success">OK</Badge>}
        />
        <ResultRow
          label="Skipped or failed"
          description={`Skipped: ${skipped} · Failed: ${failed}`}
          total={skippedFailedTotal}
          badge={skippedBadge}
        />
        <ResultRow
          label="Registration missing"
          description="Flights without aircraft registration."
          total={registrationMissing}
          badge={registrationBadge}
        />
      </CardContent>
    </Card>
  );
}

/** Render ResultRow component. */
function ResultRow({
  label,
  description,
  total,
  badge,
}: {
  label: string;
  description: string;
  total: number;
  badge: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-[#e3ebf5] bg-muted/20 px-4 py-3 dark:border-sky-900/60 dark:bg-slate-950/30">
      <div className="flex items-center gap-3">
        {badge}
        <div className="space-y-1">
          <div className="font-medium leading-tight">{label}</div>
          <div className="text-sm text-muted-foreground">{description}</div>
        </div>
      </div>
      <div className="text-right">
        <div className="text-xs text-muted-foreground">Total</div>
        <div className="text-lg font-semibold tabular-nums">{total}</div>
      </div>
    </div>
  );
}
