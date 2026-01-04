import { AppFooter, StaticHeader } from "@/components/app/AppFooter";
import { navigateWithFade } from "@/lib/navigation";

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
                <h1 className="text-2xl font-semibold">Imprint</h1>
                <p className="text-sm text-muted-foreground">
                  Skybridge is operated by Inspirespace e.U.
                </p>
              </div>
              <div className="space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
                <p>Inspirespace e.U.</p>
                <p>Eingetragenes Einzelunternehmen</p>
                <p>Inhaber: Ulrich Lehner</p>
                <p>
                  Gewerbewortlaut: Dienstleistungen in der automatischen
                  Datenverarbeitung und Informationstechnik
                </p>
                <p>
                  Geschäftszweig: IT- und Marketing-Dienstleistungen, Konzeption,
                  Entwicklung und Vermarktung von Software und Prototypen
                </p>
                <p>Firmensitz: Golfplatzstraße 32/5, 4048 Puchenau, Austria</p>
                <p>E-Mail: hello@inspirespace.co</p>
                <p>Telefon: +43 660 3243257</p>
                <p>UID-Nr: ATU76178226</p>
                <p>Firmenbuchnummer (FN): 542815h</p>
                <p>Firmenbuchgericht: Landesgericht Linz</p>
                <p>Aufsichtsbehörde: Bezirkshauptmannschaft Urfahr Umgebung</p>
                <p>
                  Kammerzugehörigkeit: WKO Oberösterreich Sparte Information und
                  Consulting
                </p>
                <p>Gewerbeordnung: www.ris.bka.gv.at</p>
                <p>
                  Verbraucher haben die Möglichkeit, Beschwerden an die
                  Online-Streitbeilegungsplattform der EU zu richten:
                  http://ec.europa.eu/odr. Sie können allfällige Beschwerde auch
                  an die oben angegebene E-Mail-Adresse richten.
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <h1 className="text-2xl font-semibold">Privacy policy</h1>
                <p className="text-sm text-muted-foreground">
                  This policy applies to Skybridge (Austria / EU).
                </p>
              </div>
              <div className="space-y-4 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Controller
                  </h2>
                  <p>
                    Inspirespace e.U., Golfplatzstraße 32/5, 4048 Puchenau,
                    Austria, hello@inspirespace.co.
                  </p>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Purpose of processing
                  </h2>
                  <p>
                    Skybridge enables the import of flight data from CloudAhoy to
                    FlySto. We process credentials only to execute the specific
                    import requested by you and to display the review before
                    import.
                  </p>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Data we process (minimal by design)
                  </h2>
                  <ul className="list-disc space-y-1 pl-5">
                    <li>Account identifiers (e.g., email address).</li>
                    <li>
                      CloudAhoy / FlySto credentials (used only for the current
                      job; not stored).
                    </li>
                    <li>
                      Flight data including times, routes, crew, trajectory data,
                      and remarks.
                    </li>
                    <li>
                      Basic technical logs (e.g., IP address, request metadata) for
                      security and troubleshooting.
                    </li>
                  </ul>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Legal basis
                  </h2>
                  <ul className="list-disc space-y-1 pl-5">
                    <li>Art. 6(1)(b) GDPR (contract performance).</li>
                    <li>Art. 6(1)(f) GDPR (security and fault analysis).</li>
                  </ul>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Hosting and processors
                  </h2>
                  <p>
                    Production hosting is on AWS (EU). Authentication uses Amazon
                    Cognito. For data transfer and import, CloudAhoy and FlySto are
                    used as external services. If data is transferred outside the
                    EU/EEA, appropriate safeguards (e.g., SCCs) are used.
                  </p>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Retention
                  </h2>
                  <p>
                    Import artifacts are retained for {retentionDays} days and then
                    automatically deleted. You can delete results earlier from the
                    app. Access logs are kept only as long as necessary for
                    security and diagnostics.
                  </p>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Your rights
                  </h2>
                  <p>
                    You have the right of access, rectification, deletion,
                    restriction of processing, data portability, and objection.
                    You may also lodge a complaint with your supervisory authority.
                  </p>
                </section>
                <section className="space-y-2">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    Contact
                  </h2>
                  <p>For privacy requests, contact hello@inspirespace.co.</p>
                </section>
              </div>
            </>
          )}
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
