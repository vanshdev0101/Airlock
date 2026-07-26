import { useEffect, useState } from "react";
import { fetchHistory } from "../lib/api.js";
import HistoryList from "./HistoryList.jsx";

/**
 * Owns its own fetch so the initial "loading" state comes from useState rather
 * than a setState inside an effect body. App mounts this fresh each time the
 * history tab opens, which is also what refreshes the list.
 */
export default function HistoryPanel({ onSelect }) {
  const [state, setState] = useState({ loading: true, scans: [] });

  useEffect(() => {
    const controller = new AbortController();

    fetchHistory({ limit: 25, signal: controller.signal })
      .then((scans) => setState({ loading: false, scans }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ loading: false, scans: [] });
      });

    return () => controller.abort();
  }, []);

  return (
    <HistoryList
      scans={state.scans}
      loading={state.loading}
      onSelect={onSelect}
    />
  );
}
