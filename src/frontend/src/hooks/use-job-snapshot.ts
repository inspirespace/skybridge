import * as React from "react";

import { getJob, type AuthContext, type JobRecord, type JobStatus } from "@/api/client";
import { patchFirebaseEmulatorRequests } from "@/lib/firebase-emulator";
import { resolveFirestoreEmulatorHostPort } from "@/lib/runtime-endpoints";

const AUTH_MODE = import.meta.env.VITE_AUTH_MODE ?? "header";
const FIRESTORE_LISTEN =
  (import.meta.env.VITE_FIRESTORE_LISTEN ?? "") === "1";
const FIREBASE_API_KEY = import.meta.env.VITE_FIREBASE_API_KEY ?? "";
const FIREBASE_PROJECT_ID = import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "";
const FIREBASE_AUTH_DOMAIN =
  import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ??
  (FIREBASE_PROJECT_ID ? `${FIREBASE_PROJECT_ID}.firebaseapp.com` : "");
const FIREBASE_APP_ID = import.meta.env.VITE_FIREBASE_APP_ID ?? "";
const FIREBASE_EMULATOR_HOST =
  import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST ?? "";
const FIREBASE_USE_EMULATOR =
  (import.meta.env.VITE_FIREBASE_USE_EMULATOR ?? "") === "1";
const FIRESTORE_JOBS_COLLECTION =
  import.meta.env.VITE_FIRESTORE_JOBS_COLLECTION ?? "skybridge-jobs";

const POLLABLE_STATUSES: JobStatus[] = [
  "review_queued",
  "review_running",
  "import_queued",
  "import_running",
];

// Poll job updates in serverless mode.
/** Hook for jobsnapshot. */
export function useJobSnapshot(jobId: string | null, auth: AuthContext) {
  const [data, setData] = React.useState<JobRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);
  const [listenerFailed, setListenerFailed] = React.useState(false);
  const [listenerActive, setListenerActive] = React.useState(false);
  const [lastSnapshotAt, setLastSnapshotAt] = React.useState<number | null>(null);
  const lastListenerState = React.useRef<string | null>(null);
  const firestoreListenEnabled =
    AUTH_MODE === "firebase" &&
    FIRESTORE_LISTEN &&
    Boolean(FIREBASE_PROJECT_ID) &&
    Boolean(FIREBASE_AUTH_DOMAIN);

  const load = React.useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const job = await getJob(jobId, auth);
      setData(job);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to load job"));
    } finally {
      setLoading(false);
    }
  }, [jobId, auth]);

  React.useEffect(() => {
    if (!jobId) {
      setData(null);
      setError(null);
      return;
    }
    setListenerFailed(false);
    setListenerActive(false);
    setLastSnapshotAt(null);
    load();
  }, [jobId, load]);

  React.useEffect(() => {
    if (!firestoreListenEnabled) return;
    const state = listenerFailed
      ? "polling"
      : listenerActive
        ? "connected"
        : "connecting";
    if (lastListenerState.current === state) return;
    lastListenerState.current = state;
    console.info(`[skybridge] live updates ${state}`);
  }, [firestoreListenEnabled, listenerFailed, listenerActive]);

  React.useEffect(() => {
    if (!jobId || !firestoreListenEnabled || listenerFailed) return;
    let unsubscribe: (() => void) | undefined;
    let cancelled = false;
    setListenerActive(true);
    setLastSnapshotAt(null);
    (async () => {
      const { initializeApp, getApps } = await import("firebase/app");
      const {
        getFirestore,
        doc,
        onSnapshot,
        connectFirestoreEmulator,
      } = await import(
        "firebase/firestore"
      );
      const app =
        getApps().length > 0
          ? getApps()[0]
          : initializeApp({
              apiKey: FIREBASE_API_KEY,
              authDomain: FIREBASE_AUTH_DOMAIN,
              projectId: FIREBASE_PROJECT_ID,
              appId: FIREBASE_APP_ID || undefined,
            });
      const db = getFirestore(app);
      if (FIREBASE_USE_EMULATOR) {
        const connection = resolveFirestoreEmulatorHostPort({
          useEmulator: FIREBASE_USE_EMULATOR,
          explicitHost: FIREBASE_EMULATOR_HOST,
        });
        if (!connection) return;
        patchFirebaseEmulatorRequests();
        connectFirestoreEmulator(db, connection.host, connection.port);
      }
      const ref = doc(db, FIRESTORE_JOBS_COLLECTION, jobId);
      unsubscribe = onSnapshot(
        ref,
        (snapshot) => {
          if (cancelled) return;
          if (!snapshot.exists()) return;
          setListenerActive(true);
          setLastSnapshotAt(Date.now());
          const payload = snapshot.data()?.payload ?? snapshot.data();
          setData(payload as JobRecord);
          setError(null);
        },
        (err) => {
          if (cancelled) return;
          unsubscribe?.();
          setListenerFailed(true);
          setListenerActive(false);
          setError(err instanceof Error ? err : new Error("Failed to subscribe"));
        }
      );
    })();
    return () => {
      cancelled = true;
      setListenerActive(false);
      unsubscribe?.();
    };
  }, [jobId, firestoreListenEnabled, listenerFailed]);

  React.useEffect(() => {
    if (!jobId || !firestoreListenEnabled || listenerFailed) return;
    if (!data?.status || !POLLABLE_STATUSES.includes(data.status)) return;
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      const now = Date.now();
      const last = lastSnapshotAt ?? startedAt;
      if (now - last > 12000) {
        setListenerFailed(true);
      }
    }, 4000);
    return () => window.clearInterval(interval);
  }, [jobId, firestoreListenEnabled, listenerFailed, data?.status, lastSnapshotAt]);

  React.useEffect(() => {
    if (!jobId || !data?.status) return;
    if (!POLLABLE_STATUSES.includes(data.status)) return;
    if (firestoreListenEnabled && !listenerFailed) return;
    const interval = window.setInterval(() => {
      load();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [jobId, data?.status, auth, load, firestoreListenEnabled, listenerFailed]);

  return {
    data,
    loading,
    error,
    refresh: load,
    listenerFailed,
    listenerActive: firestoreListenEnabled && !listenerFailed && listenerActive,
    lastSnapshotAt,
  };
}
