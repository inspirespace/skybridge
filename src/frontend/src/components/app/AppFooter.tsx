import { ThemeToggle } from "@/components/theme-toggle";
import { navigateWithFade } from "@/lib/navigation";

/** Render AppFooter component. */
export function AppFooter() {
  return (
    <footer className="footer-shell relative z-10 border-t border-border/30 bg-background/80 backdrop-blur-sm dark:border-[hsl(var(--sky-accent))]/10">
      <div className="container flex flex-wrap items-center justify-between gap-3 pb-20 pt-6 text-sm text-muted-foreground lg:py-6">
        <div>
          © {new Date().getFullYear()}{" "}
          <a
            className="transition-colors hover:text-foreground dark:hover:text-[hsl(var(--sky-accent))]"
            href="https://www.inspirespace.co"
            target="_blank"
            rel="noreferrer"
          >
            Inspirespace e.U.
          </a>
        </div>
        <div className="flex flex-wrap gap-4">
          <a
            className="transition-colors hover:text-foreground dark:hover:text-[hsl(var(--sky-accent))]"
            href="/imprint/"
            onClick={(event) => navigateWithFade(event, "/imprint/")}
          >
            Imprint
          </a>
          <a
            className="transition-colors hover:text-foreground dark:hover:text-[hsl(var(--sky-accent))]"
            href="/privacy/"
            onClick={(event) => navigateWithFade(event, "/privacy/")}
          >
            Privacy
          </a>
          <a
            className="transition-colors hover:text-foreground dark:hover:text-[hsl(var(--sky-accent))]"
            href="https://github.com/inspirespace/skybridge"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <a
            className="transition-colors hover:text-foreground dark:hover:text-[hsl(var(--sky-accent))]"
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
