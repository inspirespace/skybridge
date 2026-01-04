import type { DateRange } from "react-day-picker";

export function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toISOString().slice(0, 10);
}

export function formatDateRange(range?: DateRange) {
  if (!range?.from && !range?.to) return "Any date";
  if (range?.from && range?.to) {
    return `${formatISODate(range.from)} - ${formatISODate(range.to)}`;
  }
  if (range?.from) {
    return `${formatISODate(range.from)} -`;
  }
  return `- ${formatISODate(range.to!)}`;
}

export function formatISODate(value: Date) {
  return value.toISOString().slice(0, 10);
}

export function formatElapsed(start?: string | null, end?: string | null) {
  if (!start) return "-";
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  const delta = Math.max(0, endMs - startMs);
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  if (!remaining) return `${hours}h`;
  return `${hours}h ${remaining}m`;
}

export function formatLastUpdate(value?: string | null, now: Date = new Date()) {
  if (!value) return "-";
  const date = new Date(value);
  const delta = Math.max(0, now.getTime() - date.getTime());
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatFlightId(value?: string | null) {
  const id = value ?? "";
  if (!id) return "-";
  if (id.length <= 16) return id;
  return `...${id.slice(-12)}`;
}
