import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AuthDivider, ProviderIcon, type ProviderName } from "./shared";

const PROVIDERS: Array<{ key: ProviderName; label: string; enabledKey: string }> = [
  { key: "google", label: "Google", enabledKey: "google" },
  { key: "apple", label: "Apple", enabledKey: "apple" },
  { key: "facebook", label: "Facebook", enabledKey: "facebook" },
  { key: "microsoft", label: "Microsoft", enabledKey: "microsoft" },
  { key: "anonymous", label: "guest", enabledKey: "anonymous" },
];

export type ProviderFlags = {
  google?: boolean;
  apple?: boolean;
  facebook?: boolean;
  microsoft?: boolean;
  anonymous?: boolean;
};

export function FirebaseProviderButtons({
  enabled,
  labelPrefix,
  onSelect,
  disabled,
  showDivider = false,
  buttonClassName,
  className,
}: {
  enabled: ProviderFlags;
  labelPrefix: "Continue with" | "Link";
  onSelect: (provider: ProviderName) => void;
  disabled?: boolean;
  showDivider?: boolean;
  buttonClassName?: string;
  className?: string;
}) {
  const visibleProviders = PROVIDERS.filter((provider) => {
    if (provider.key === "anonymous") return Boolean(enabled.anonymous);
    return Boolean((enabled as Record<string, boolean | undefined>)[provider.enabledKey]);
  });

  if (visibleProviders.length === 0) return null;

  return (
    <div className={className}>
      {showDivider && <AuthDivider />}
      <div className="grid gap-2">
        {visibleProviders.map((provider) => {
          const isGuest = provider.key === "anonymous";
          const label = isGuest
            ? "Continue as guest"
            : `${labelPrefix} ${provider.label}`;
          return (
            <Button
              key={provider.key}
              className={cn(
                "h-11 w-full justify-start gap-3 rounded-xl border border-slate-700/60 bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.35)] hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60",
                buttonClassName
              )}
              onClick={() => onSelect(provider.key)}
              disabled={disabled}
            >
              <ProviderIcon provider={provider.key} />
              {label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
