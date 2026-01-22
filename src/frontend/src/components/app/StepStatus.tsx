import { Check, Lock } from "lucide-react";

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
  const badgeClass = done || active ? "" : "border-dashed text-muted-foreground/60 dark:border-[hsl(var(--sky-accent))]/15";
  const labelClass = active
    ? "font-semibold text-[hsl(var(--horizon))]"
    : done
      ? "font-medium text-[hsl(var(--altitude))]"
      : "font-medium text-muted-foreground/70";
  return (
    <div
      className={cn(
        "relative flex items-center justify-between rounded-xl border px-3 py-2.5 text-sm transition-all duration-300",
        active
          ? "border-[hsl(var(--horizon))]/40 bg-[hsl(var(--horizon))]/10 shadow-[0_0_20px_hsl(var(--horizon)/0.15)] dark:border-[hsl(var(--horizon))]/30 dark:bg-[hsl(var(--horizon))]/5"
          : done
            ? "border-[hsl(var(--altitude))]/30 bg-[hsl(var(--altitude))]/5 dark:border-[hsl(var(--altitude))]/20 dark:bg-[hsl(var(--altitude))]/5"
            : "border-border/30 bg-muted/20 dark:border-[hsl(var(--sky-accent))]/10 dark:bg-[hsl(var(--cockpit-dark))]/30"
      )}
    >
      {active && (
        <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-0.5 rounded-full bg-[hsl(var(--horizon))] shadow-[0_0_8px_hsl(var(--horizon)/0.5)]" />
      )}
      {done && (
        <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-0.5 rounded-full bg-[hsl(var(--altitude))]" />
      )}
      <span className={cn(labelClass, (active || done) && "pl-2")}>{label}</span>
      <Badge variant={badgeVariant} className={cn("flex items-center gap-1.5", badgeClass)}>
        {done ? (
          <>
            <Check className="h-3 w-3" /> Done
          </>
        ) : active ? (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--horizon))] animate-pulse" />
            Active
          </>
        ) : (
          <>
            <Lock className="h-3 w-3 opacity-50" /> Locked
          </>
        )}
      </Badge>
    </div>
  );
}
