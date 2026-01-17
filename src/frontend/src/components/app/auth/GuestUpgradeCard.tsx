import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { ProviderIcon, type ProviderName } from "./shared";
import { type ProviderFlags } from "./FirebaseProviderButtons";

export function GuestUpgradeCard({
  providers,
  onProvider,
  emailAddress,
  onEmailChange,
  onSendLink,
  actionLoading,
}: {
  providers: ProviderFlags;
  onProvider: (provider: ProviderName) => void;
  emailAddress: string;
  onEmailChange: (value: string) => void;
  onSendLink: () => void;
  actionLoading: boolean;
}) {
  const providerList = [
    { key: "google" as const, enabled: providers.google },
    { key: "apple" as const, enabled: providers.apple },
    { key: "microsoft" as const, enabled: providers.microsoft },
    { key: "facebook" as const, enabled: providers.facebook },
  ].filter((provider) => provider.enabled);

  return (
    <Card className="mb-4 rounded-xl border border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-4 w-4" aria-hidden />
          Upgrade your guest session
        </CardTitle>
        <CardDescription className="text-amber-800/80 dark:text-amber-100/70">
          Link a provider to keep your import history across devices.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {providerList.map((provider) => (
            <Button
              key={provider.key}
              className="h-11 justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900"
              onClick={() => onProvider(provider.key)}
              disabled={actionLoading}
            >
              <ProviderIcon provider={provider.key} />
              Link {provider.key === "google" ? "Google" : provider.key === "apple" ? "Apple" : provider.key === "microsoft" ? "Microsoft" : "Facebook"}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-amber-800/80 dark:text-amber-100/70">
          <ArrowRight className="h-3 w-3" aria-hidden />
          You can also link an email address below.
        </div>
        <div className="flex w-full max-w-xl gap-2">
          <input
            className="h-11 w-full rounded-lg border border-amber-200 bg-white px-3 text-sm text-amber-900 shadow-sm focus:border-amber-300 focus:outline-none"
            placeholder="you@example.com"
            value={emailAddress}
            onChange={(event) => onEmailChange(event.target.value)}
          />
          <Button variant="outline" className="h-11 px-4" onClick={onSendLink}>
            Link email
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
