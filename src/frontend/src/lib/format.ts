import type { DateRange } from "react-day-picker";
import type { ProgressEvent } from "@/api/client";

/** Format date. */
export function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toISOString().slice(0, 10);
}

/** Format daterange. */
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

/** Format isodate. */
export function formatISODate(value: Date) {
  return value.toISOString().slice(0, 10);
}

/** Format elapsed. */
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

/** Format lastupdate. */
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

/** Get phaseevents. */
function getPhaseEvents(log?: ProgressEvent[], phase?: ProgressEvent["phase"]) {
  if (!log || !phase) return [];
  return log.filter((event) => event?.phase === phase && event?.created_at);
}

/** Format phaseelapsed. */
export function formatPhaseElapsed(
  log: ProgressEvent[] | undefined,
  phase: ProgressEvent["phase"],
  now: Date,
  running: boolean
) {
  const events = getPhaseEvents(log, phase);
  if (!events.length) return "";
  const sorted = [...events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  const start = sorted[0].created_at;
  const end = running ? now.toISOString() : sorted[sorted.length - 1].created_at;
  return formatElapsed(start, end);
}

/** Format phaselastupdate.
 *
 * Uses the most recent of either a progress_log entry for the phase or the
 * job-level heartbeat_at, so background heartbeats keep the UI ticking
 * even when no new progress event is emitted (e.g. during a slow FlySto
 * PUT inside a reconcile pass).
 */
export function formatPhaseLastUpdate(
  log: ProgressEvent[] | undefined,
  phase: ProgressEvent["phase"],
  now: Date,
  heartbeatAt?: string | null
) {
  const events = getPhaseEvents(log, phase);
  let latestTimestamp: string | null = null;
  if (events.length) {
    const latest = events.reduce((acc, event) =>
      new Date(event.created_at).getTime() > new Date(acc.created_at).getTime()
        ? event
        : acc
    );
    latestTimestamp = latest.created_at;
  }
  if (heartbeatAt) {
    if (
      !latestTimestamp ||
      new Date(heartbeatAt).getTime() > new Date(latestTimestamp).getTime()
    ) {
      latestTimestamp = heartbeatAt;
    }
  }
  if (!latestTimestamp) return "-";
  return formatLastUpdate(latestTimestamp, now);
}

/** Format flightid. */
export function formatFlightId(value?: string | null) {
  const id = value ?? "";
  if (!id) return "-";
  if (id.length <= 16) return id;
  return `...${id.slice(-12)}`;
}
