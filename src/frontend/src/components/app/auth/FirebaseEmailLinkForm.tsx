import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FirebaseEmailLinkForm({
  label,
  email,
  onEmailChange,
  onSend,
  disabled,
  buttonLabel,
  notice,
  linkUrl,
  inputClassName,
  buttonClassName,
  noticeClassName,
}: {
  label: string;
  email: string;
  onEmailChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  buttonLabel: string;
  notice?: string | null;
  linkUrl?: string | null;
  inputClassName?: string;
  buttonClassName?: string;
  noticeClassName?: string;
}) {
  const inputId = "firebase-email-link-address";
  const handleSubmit = () => {
    if (disabled) return;
    onSend();
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-slate-500" htmlFor={inputId}>
        {label}
      </label>
      <div className="flex w-full max-w-xl gap-2">
        <input
          id={inputId}
          name="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="send"
          className={cn(
            "h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500",
            inputClassName
          )}
          placeholder="you@example.com"
          disabled={disabled}
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            handleSubmit();
          }}
        />
        <Button
          variant="outline"
          className={cn("h-11 px-4", buttonClassName)}
          onClick={handleSubmit}
          disabled={disabled}
        >
          {buttonLabel}
        </Button>
      </div>
      {notice && <p className={cn("text-xs text-slate-500", noticeClassName)}>{notice}</p>}
      {linkUrl && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Emulator link (click to sign in):
          <a className="ml-1 break-all text-sky-600 hover:underline" href={linkUrl}>
            {linkUrl}
          </a>
        </div>
      )}
    </div>
  );
}
