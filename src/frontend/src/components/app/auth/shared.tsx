import { Mail, UserRound } from "lucide-react";

export type ProviderName =
  | "google"
  | "apple"
  | "facebook"
  | "microsoft"
  | "anonymous"
  | "email";

export const ProviderIcon = ({ provider }: { provider: ProviderName }) => {
  switch (provider) {
    case "google":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/5">
          <svg aria-hidden viewBox="0 0 48 48" className="h-4 w-4">
            <path
              fill="#EA4335"
              d="M24 9.5c3.2 0 6 .9 8.2 2.7l6.1-6.1C34.7 2.6 29.7 0 24 0 14.6 0 6.5 5.4 2.4 13.2l7.3 5.7C11.4 13 17.1 9.5 24 9.5z"
            />
            <path
              fill="#4285F4"
              d="M46.1 24.5c0-1.6-.1-2.8-.4-4.1H24v7.8h12.5c-.5 2.7-2.1 5.1-4.7 6.7l7.2 5.6c4.2-3.9 6.6-9.6 6.6-16z"
            />
            <path
              fill="#FBBC05"
              d="M9.7 28.9c-1-2.7-1-5.7 0-8.4l-7.3-5.7c-3.1 6.2-3.1 13.6 0 19.8l7.3-5.7z"
            />
            <path
              fill="#34A853"
              d="M24 48c5.7 0 10.6-1.9 14.1-5.1l-7.2-5.6c-2 1.4-4.6 2.2-6.9 2.2-6.9 0-12.6-3.5-14.3-9.4l-7.3 5.7C6.5 42.6 14.6 48 24 48z"
            />
          </svg>
        </span>
      );
    case "apple":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-black text-white">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path
              fill="currentColor"
              d="M16.3 1.5c0 1-.4 2-1 2.7-.7.9-1.9 1.6-3 1.5-.1-1 .4-2 .9-2.7.7-.8 1.9-1.5 3.1-1.5ZM19.7 17.4c-.4.9-.6 1.3-1.1 2.1-.7 1-1.6 2.2-2.8 2.2-1.1 0-1.4-.7-2.9-.7-1.5 0-1.9.7-3 .7-1.2 0-2-1.1-2.7-2.1-1.5-2.2-2.6-6.1-1.1-8.8.8-1.4 2.2-2.3 3.7-2.3 1.2 0 2.3.8 3 .8.7 0 2.1-.9 3.5-.8.6 0 2.3.2 3.4 1.7-2.9 1.6-2.4 5.7 1 7.2Z"
            />
          </svg>
        </span>
      );
    case "facebook":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#1877F2] text-white">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path
              fill="currentColor"
              d="M22 12a10 10 0 1 0-11.6 9.9v-7H8v-2.9h2.4V9.8c0-2.4 1.4-3.7 3.6-3.7 1 0 2.1.2 2.1.2v2.3h-1.2c-1.2 0-1.6.7-1.6 1.5v1.9h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12Z"
            />
          </svg>
        </span>
      );
    case "microsoft":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/5">
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
            <path fill="#F25022" d="M1 1h10v10H1z" />
            <path fill="#7FBA00" d="M13 1h10v10H13z" />
            <path fill="#00A4EF" d="M1 13h10v10H1z" />
            <path fill="#FFB900" d="M13 13h10v10H13z" />
          </svg>
        </span>
      );
    case "email":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-sky-700">
          <Mail className="h-4 w-4" aria-hidden />
        </span>
      );
    case "anonymous":
      return (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-slate-700">
          <UserRound className="h-4 w-4" aria-hidden />
        </span>
      );
    default:
      return null;
  }
};

export const AuthDivider = () => (
  <div className="relative my-3 flex items-center">
    <div className="h-px w-full bg-slate-200 dark:bg-slate-800" />
    <span className="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-xs uppercase tracking-[0.3em] text-slate-400 dark:bg-slate-950 dark:text-slate-600">
      Or
    </span>
  </div>
);
