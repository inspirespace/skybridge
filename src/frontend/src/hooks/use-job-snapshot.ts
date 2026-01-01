import * as React from "react";

import { fetchJobSnapshot, type JobSnapshot } from "@/api/client";

export function useJobSnapshot() {
  const [data, setData] = React.useState<JobSnapshot | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      const snapshot = await fetchJobSnapshot();
      if (active) {
        setData(snapshot);
        setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  return { data, loading };
}
