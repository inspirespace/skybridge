import { formatISODate } from "@/lib/format";

export const parseISODateInput = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return null;
  const date = new Date(`${trimmed}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  return formatISODate(date) === trimmed ? date : null;
};
