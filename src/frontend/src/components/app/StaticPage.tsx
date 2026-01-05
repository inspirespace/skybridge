import { AppFooter, StaticHeader } from "@/components/app/AppFooter";
import { imprintContent } from "@/content/imprint";
import { buildPrivacyContent } from "@/content/privacy";
import { navigateWithFade } from "@/lib/navigation";

/** Render StaticPage component. */
export function StaticPage({
  page,
  retentionDays,
}: {
  page: "imprint" | "privacy";
  retentionDays: number;
}) {
  return (
    <div className="app-shell min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <StaticHeader />
      <main className="container py-10">
        <div className="max-w-3xl space-y-6">
          {page === "imprint" ? (
            <>
              <div className="space-y-2">
                <h1 className="text-2xl font-semibold">{imprintContent.title}</h1>
                <p className="text-sm text-muted-foreground">{imprintContent.subtitle}</p>
              </div>
              <div className="space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
                {imprintContent.lines.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </>
          ) : (() => {
            const content = buildPrivacyContent(retentionDays);
            return (
              <>
                <div className="space-y-2">
                  <h1 className="text-2xl font-semibold">{content.title}</h1>
                  <p className="text-sm text-muted-foreground">{content.subtitle}</p>
                </div>
                <div className="space-y-4 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
                  {content.sections.map((section) => (
                    <section className="space-y-2" key={section.title}>
                      <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                        {section.title}
                      </h2>
                      {section.paragraphs?.map((paragraph) => (
                        <p key={paragraph}>{paragraph}</p>
                      ))}
                      {section.list && (
                        <ul className="list-disc space-y-1 pl-5">
                          {section.list.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      )}
                    </section>
                  ))}
                </div>
              </>
            );
          })()}
          <div>
            <a
              className="text-sm text-sky-600 hover:underline"
              href="/"
              onClick={(event) => navigateWithFade(event, "/")}
            >
              Back to app
            </a>
          </div>
        </div>
      </main>
      <AppFooter />
    </div>
  );
}
