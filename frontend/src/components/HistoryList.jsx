import { trustLevel, formatTimeAgo } from "../lib/severity.js";
import EmptyState from "./EmptyState.jsx";
import { HistorySkeleton } from "./Skeleton.jsx";
import styles from "./HistoryList.module.css";

export default function HistoryList({ scans, loading, onSelect }) {
  if (loading) return <HistorySkeleton />;

  if (!scans.length) {
    return (
      <EmptyState
        glyph="∅"
        title="No scans yet"
        body="Results appear here after your first scan. History is stored locally by the backend."
      />
    );
  }

  return (
    <ul className={styles.list}>
      {scans.map((scan) => {
        const level = trustLevel(scan.trust_level);
        return (
          <li key={scan.id}>
            <button
              type="button"
              className={styles.row}
              data-status={level.status}
              onClick={() => onSelect(scan.repo_url)}
            >
              <span className={styles.badge}>
                <span aria-hidden="true">{level.glyph}</span>
                {level.label}
              </span>

              <span className={styles.meta}>
                <span className={styles.repo}>{scan.repo_name}</span>
                <span className={styles.time}>{formatTimeAgo(scan.scanned_at)}</span>
              </span>

              <span className={styles.score}>
                {scan.trust_score}
                <span className={styles.scoreUnit} aria-hidden="true">
                  /100
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
