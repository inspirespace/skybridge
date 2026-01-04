import { ThemeToggle } from "@/components/theme-toggle";

export function AppFooter() {
  return (
    <footer className="border-t bg-background/80">
      <div className="container flex flex-wrap items-center justify-between gap-3 pb-20 pt-6 text-sm text-muted-foreground lg:py-6">
        <div>© {new Date().getFullYear()} Inspirespace e.U.</div>
        <div className="flex flex-wrap gap-4">
          <a className="hover:text-foreground" href="/imprint">
            Imprint
          </a>
          <a className="hover:text-foreground" href="/privacy">
            Privacy
          </a>
          <a
            className="hover:text-foreground"
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

export function StaticHeader() {
  return (
    <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur dark:border-slate-800/70 dark:bg-slate-950/80">
      <div className="container flex items-center justify-between py-5">
        <a
          href="/"
          className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-600 dark:text-slate-300"
        >
          Skybridge
        </a>
        <ThemeToggle />
      </div>
    </header>
  );
}
