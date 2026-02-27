import * as React from "react";

import { cn } from "@/lib/utils";

const STORAGE_KEY = "skybridge-theme";

/** Render ThemeToggle component. */
export function ThemeToggle({ className }: { className?: string }) {
  const [isDark, setIsDark] = React.useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return document.documentElement.classList.contains("dark");
  });

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "dark") {
      document.documentElement.classList.add("dark");
      setIsDark(true);
      return;
    }
    if (stored === "light") {
      document.documentElement.classList.remove("dark");
      setIsDark(false);
    }
  }, []);

  /** Handle handleToggle. */
  const handleToggle = (checked: boolean) => {
    setIsDark(checked);
    document.documentElement.classList.toggle("dark", checked);
    window.localStorage.setItem(STORAGE_KEY, checked ? "dark" : "light");
  };

  return (
    <div className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <span>Light</span>
      <button
        type="button"
        role="switch"
        aria-checked={isDark}
        aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
        onClick={() => handleToggle(!isDark)}
        className={cn(
          "inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent",
          "bg-input p-0.5 transition-colors duration-200 focus-visible:outline-none",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          isDark && "bg-primary"
        )}
      >
        <span
          aria-hidden
          className={cn(
            "block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform duration-200",
            isDark ? "translate-x-5" : "translate-x-0"
          )}
        />
      </button>
      <span>Dark</span>
    </div>
  );
}
