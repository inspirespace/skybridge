import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type ImportResultsProps = {
  imported: number;
  skipped: number;
  failed: number;
  registrationMissing: number;
};

export function ImportResults({
  imported,
  skipped,
  failed,
  registrationMissing,
}: ImportResultsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Import results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ResultRow
          label="Imported flights"
          description="All approved flights created in FlySto."
          total={imported}
          badge={<Badge variant="success">OK</Badge>}
        />
        <ResultRow
          label="Skipped or failed"
          description={`Skipped: ${skipped} · Failed: ${failed}`}
          total={skipped + failed}
          badge={<Badge variant="success">OK</Badge>}
        />
        <ResultRow
          label="Registration missing"
          description="Flights without aircraft registration."
          total={registrationMissing}
          badge={<Badge variant="warning">Needs review</Badge>}
        />
      </CardContent>
    </Card>
  );
}

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
    <div className="flex items-start justify-between gap-4 rounded-md border px-4 py-3">
      <div className="flex items-start gap-3">
        {badge}
        <div>
          <div className="font-medium">{label}</div>
          <div className="text-sm text-muted-foreground">{description}</div>
        </div>
      </div>
      <div className="text-right">
        <div className="text-xs text-muted-foreground">Total</div>
        <div className="text-lg font-semibold">{total}</div>
      </div>
    </div>
  );
}
