import * as React from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker, type DropdownProps } from "react-day-picker";

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
      className={cn("min-w-[320px] px-8 py-4", className)}
      classNames={{
        months: "flex flex-col space-y-4",
        month: "space-y-4",
        month_caption: "flex justify-center pt-1 relative items-center",
        caption_label: "sr-only !hidden",
        nav: "pointer-events-none absolute left-0 right-0 top-1/2 flex -translate-y-1/2 items-center justify-between px-2",
        button_previous: cn(
          buttonVariants({ variant: "outline" }),
          "pointer-events-auto h-7 w-7 bg-transparent p-0 opacity-60 hover:opacity-100"
        ),
        button_next: cn(
          buttonVariants({ variant: "outline" }),
          "pointer-events-auto h-7 w-7 bg-transparent p-0 opacity-60 hover:opacity-100"
        ),
        dropdowns: "flex items-center gap-2",
        months_dropdown: "mr-1 w-[140px]",
        years_dropdown: "w-[110px]",
        month_grid: "w-full border-collapse space-y-1",
        weekdays: "flex",
        weekday: "text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]",
        weeks: "flex w-full flex-col",
        week: "flex w-full mt-2",
        day: "h-9 w-9 text-center text-sm p-0 relative focus-within:z-20",
        day_button:
          "h-9 w-9 p-0 font-normal hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        selected:
          "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
        today: "bg-accent text-accent-foreground",
        outside: "text-muted-foreground opacity-50",
        disabled: "text-muted-foreground opacity-50",
        range_middle: "bg-accent/60 text-accent-foreground",
        range_end: "rounded-r-md",
        range_start: "rounded-l-md",
        hidden: "invisible",
      }}
      components={{
        Dropdown: ({ className: dropdownClassName, options, ...selectProps }: DropdownProps) => (
          <div className={cn("relative", dropdownClassName)}>
            <select
              className="h-9 w-full appearance-none rounded-md border border-input bg-background px-3 pr-9 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              {...selectProps}
            >
              {options?.map(({ value, label, disabled }) => (
                <option key={value} value={value} disabled={disabled}>
                  {label}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
          </div>
        ),
        Chevron: ({ className: iconClassName, orientation, ...iconProps }) => {
          if (orientation !== "left" && orientation !== "right") {
            return <span className="hidden" aria-hidden />;
          }
          const Icon = orientation === "left" ? ChevronLeft : ChevronRight;
          return <Icon className={cn("h-4 w-4", iconClassName)} {...iconProps} />;
        },
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
