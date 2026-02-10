import { ThemeToggle } from "@/components/theme-toggle";
import { navigateWithFade } from "@/lib/navigation";

/** Render AppFooter component. */
export function AppFooter() {
  return (
    <footer className="footer-shell mt-auto border-t border-border/50 bg-background/50 backdrop-blur-sm">
      <div className="container flex flex-wrap items-center justify-between gap-4 py-6 text-sm text-muted-foreground lg:py-8">
        <div className="flex items-center gap-3">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-primary/10 text-primary">
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
            </svg>
          </div>
          <span>
            © {new Date().getFullYear()}{" "}
            <a
              className="hover:text-foreground transition-colors"
              href="https://www.inspirespace.co"
              target="_blank"
              rel="noreferrer"
            >
              Inspirespace e.U.
            </a>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-4 sm:gap-6">
          <a
            className="hover:text-foreground transition-colors"
            href="/imprint/"
            onClick={(event) => navigateWithFade(event, "/imprint/")}
          >
            Imprint
          </a>
          <a
            className="hover:text-foreground transition-colors"
            href="/privacy/"
            onClick={(event) => navigateWithFade(event, "/privacy/")}
          >
            Privacy
          </a>
          <a
            className="hover:text-foreground transition-colors inline-flex items-center gap-1.5"
            href="https://github.com/inspirespace/skybridge"
            target="_blank"
            rel="noreferrer"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
            GitHub
          </a>
          <a
            className="hover:text-foreground transition-colors"
            href="https://github.com/inspirespace/skybridge/issues"
            target="_blank"
            rel="noreferrer"
          >
            Support
          </a>
        </div>
      </div>
    </footer>
  );
}

/** Render StaticHeader component. */
export function StaticHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur dark:border-slate-800/70 dark:bg-slate-950/80">
      <div className="container flex items-center justify-between py-5">
        <a
          href="/"
          className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-600 dark:text-slate-300"
          onClick={(event) => navigateWithFade(event, "/")}
        >
          Skybridge
        </a>
        <ThemeToggle />
      </div>
    </header>
  );
}
