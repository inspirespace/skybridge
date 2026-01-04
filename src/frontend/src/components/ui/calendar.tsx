import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";

import { cn } from "@/lib/utils";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({
  className,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("rdp-root p-3", className)}
      style={
        {
          "--rdp-accent-color": "hsl(var(--primary))",
          "--rdp-accent-background-color": "hsl(var(--accent))",
        } as React.CSSProperties
      }
      components={{
        IconLeft: ({ className: iconClassName, ...iconProps }) => (
          <ChevronLeft className={cn("h-4 w-4", iconClassName)} {...iconProps} />
        ),
        IconRight: ({ className: iconClassName, ...iconProps }) => (
          <ChevronRight className={cn("h-4 w-4", iconClassName)} {...iconProps} />
        ),
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
