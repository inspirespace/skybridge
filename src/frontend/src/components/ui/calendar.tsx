import * as React from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";

import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

/** Type CalendarProps. */
export type CalendarProps = React.ComponentProps<typeof DayPicker>;

/** Render Calendar component. */
function Calendar({
  className,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      captionLayout="dropdown"
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        months: "calendar-months relative flex flex-col gap-4 sm:flex-row sm:gap-6 px-10",
        month: "space-y-4 min-w-[250px]",
        month_caption: "relative flex items-center justify-center pt-1",
        caption_label: "text-sm font-medium text-foreground",
        nav: "pointer-events-none absolute inset-y-0 left-0 right-0 flex items-center justify-between",
        button_previous: cn(
          buttonVariants({ variant: "outline" }),
          "pointer-events-auto h-8 w-8 bg-transparent p-0 opacity-70 hover:opacity-100"
        ),
        button_next: cn(
          buttonVariants({ variant: "outline" }),
          "pointer-events-auto h-8 w-8 bg-transparent p-0 opacity-70 hover:opacity-100"
        ),
        dropdowns: "flex items-center gap-2",
        dropdown_root: "relative",
        dropdown:
          "rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring",
        months_dropdown: "mr-1 w-[120px]",
        years_dropdown: "w-[90px]",
        month_grid: "w-full border-collapse space-y-1",
        weekdays: "flex",
        weekday: "text-muted-foreground w-9 font-normal text-[0.8rem]",
        weeks: "flex flex-col",
        week: "flex w-full mt-2",
        day: "h-9 w-9 p-0 text-center text-sm relative focus-within:z-20",
        day_button:
          "h-9 w-9 rounded-none border-0 p-0 font-normal hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring aria-selected:opacity-100",
        range_end: "rounded-r-md",
        range_start: "rounded-l-md",
        selected:
          "rounded-md bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
        today: "bg-accent text-accent-foreground",
        outside:
          "day-outside text-muted-foreground opacity-50 aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30",
        disabled: "text-muted-foreground opacity-50",
        range_middle: "aria-selected:bg-accent/60 aria-selected:text-accent-foreground",
        hidden: "invisible",
      }}
      components={{
        Chevron: ({ className: iconClassName, orientation, ...iconProps }) => {
          const Icon =
            orientation === "left"
              ? ChevronLeft
              : orientation === "right"
                ? ChevronRight
                : ChevronDown;
          return <Icon className={cn("h-4 w-4", iconClassName)} {...iconProps} />;
        },
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
