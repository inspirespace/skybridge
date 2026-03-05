import * as React from "react";

import { cn } from "@/lib/utils";

const STORAGE_KEY = "skybridge-theme";
type ThemePreference = "dark" | "light" | null;
const DARK_MODE_MEDIA_QUERY = "(prefers-color-scheme: dark)";

function getStoredThemePreference(): ThemePreference {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "dark" || stored === "light" ? stored : null;
  } catch {
    return null;
  }
}

function getSystemPrefersDarkMode() {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia(DARK_MODE_MEDIA_QUERY).matches;
  }
  if (typeof document === "undefined") {
    return false;
  }
  return document.documentElement.classList.contains("dark");
}

function resolveThemeSelection(preference: ThemePreference) {
  if (preference === "dark") return true;
  if (preference === "light") return false;
  return getSystemPrefersDarkMode();
}

/** Render ThemeToggle component. */
export function ThemeToggle({ className }: { className?: string }) {
  const [themePreference, setThemePreference] = React.useState<ThemePreference>(() =>
    getStoredThemePreference()
  );
  const [isDark, setIsDark] = React.useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    const root = document.documentElement;
    const prefersDark = resolveThemeSelection(getStoredThemePreference());
    root.classList.toggle("dark", prefersDark);
    return prefersDark;
  });

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const root = document.documentElement;
    const nextIsDark = resolveThemeSelection(themePreference);
    root.classList.toggle("dark", nextIsDark);
    setIsDark(nextIsDark);
  }, [themePreference]);

  React.useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mediaQuery = window.matchMedia(DARK_MODE_MEDIA_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      if (themePreference !== null) return;
      document.documentElement.classList.toggle("dark", event.matches);
      setIsDark(event.matches);
    };
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
    } else if (typeof mediaQuery.addListener === "function") {
      mediaQuery.addListener(handleChange);
    }
    return () => {
      if (typeof mediaQuery.removeEventListener === "function") {
        mediaQuery.removeEventListener("change", handleChange);
      } else if (typeof mediaQuery.removeListener === "function") {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, [themePreference]);

  /** Handle handleToggle. */
  const handleToggle = (checked: boolean) => {
    setThemePreference(checked ? "dark" : "light");
    try {
      window.localStorage.setItem(STORAGE_KEY, checked ? "dark" : "light");
    } catch {
      // Ignore storage access failures and keep runtime toggle behavior.
    }
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
