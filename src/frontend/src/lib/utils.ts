import { twMerge } from "tailwind-merge"

type ClassValue =
  | string
  | number
  | null
  | false
  | undefined
  | ClassValue[]
  | { [key: string]: boolean };

/** Handle cn. */
export function cn(...inputs: ClassValue[]) {
  const classes: string[] = [];
  /** Handle push. */
  const push = (value: ClassValue) => {
    if (!value) return;
    if (typeof value === "string" || typeof value === "number") {
      classes.push(String(value));
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(push);
      return;
    }
    if (typeof value === "object") {
      Object.entries(value).forEach(([key, enabled]) => {
        if (enabled) classes.push(key);
      });
    }
  };
  inputs.forEach(push);
  return twMerge(classes.join(" "));
}
