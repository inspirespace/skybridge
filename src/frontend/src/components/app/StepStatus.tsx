import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Render StepStatus component. */
export function StepStatus({
  label,
  active,
  done,
}: {
  label: string;
  active?: boolean;
  done?: boolean;
}) {
  const badgeVariant = done ? "success" : active ? "active" : "outline";
  const badgeClass = done || active ? "" : "border-dashed text-muted-foreground";
  const labelClass = active
    ? "font-semibold"
    : done
      ? "font-medium"
      : "font-medium text-muted-foreground";
  return (
    <div
      className={cn(
        "relative flex items-center justify-between rounded-md border border-[#d9e1ec] bg-[#f8fafc] px-3 py-2 text-sm dark:border-sky-900/60 dark:bg-slate-950/70",
        active ? "bg-[#eef3f8] dark:bg-slate-900/70" : "bg-[#f8fafc] dark:bg-slate-950/70"
      )}
    >
      {active && (
        <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-0.5 rounded-full bg-primary/60" />
      )}
      <span className={cn(labelClass, active && "pl-2")}>{label}</span>
      <Badge variant={badgeVariant} className={cn("flex items-center gap-1", badgeClass)}>
        {done ? (
          <>
            <Check className="h-3 w-3" /> Done
          </>
        ) : active ? (
          "Active"
        ) : (
          "Locked"
        )}
      </Badge>
    </div>
  );
}
