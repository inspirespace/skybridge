import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-all duration-300",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground dark:border-[hsl(var(--sky-accent))]/20 dark:bg-[hsl(var(--sky-accent))]/8 dark:text-[hsl(var(--sky-accent))]",
        outline:
          "text-foreground border-border/50 dark:border-[hsl(var(--sky-accent))]/15 dark:bg-[hsl(var(--cockpit-dark))]/30 dark:text-muted-foreground",
        success: "border-[hsl(var(--altitude))]/30 bg-[hsl(var(--altitude))]/10 text-[hsl(var(--altitude))] dark:border-[hsl(var(--altitude))]/30 dark:bg-[hsl(var(--altitude))]/10 dark:text-[hsl(var(--altitude))]",
        warning: "border-amber-300/40 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400",
        active: "border-[hsl(var(--horizon))]/40 bg-[hsl(var(--horizon))]/10 text-[hsl(var(--horizon))] shadow-[0_0_12px_hsl(var(--horizon)/0.2)] dark:border-[hsl(var(--horizon))]/30 dark:bg-[hsl(var(--horizon))]/10 dark:text-[hsl(var(--horizon))]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

/** Interface BadgeProps. */
export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

/** Render Badge component. */
function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
