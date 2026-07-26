import styles from "./Skeleton.module.css";

const Bar = ({ w, h = 12 }) => (
  <span className={styles.bar} style={{ inlineSize: w, blockSize: h }} />
);

/** Mirrors the shape of ScanResult so the layout does not jump on arrival. */
export function ScanResultSkeleton() {
  return (
    <div className={styles.card} role="status" aria-live="polite">
      <span className="sr-only">Scanning repository…</span>

      <div className={styles.header}>
        <Bar w="40%" h={18} />
        <Bar w="72%" />
        <div className={styles.meterRow}>
          <Bar w="86px" h={48} />
          <div className={styles.meterCol}>
            <Bar w="100%" h={10} />
            <Bar w="35%" h={10} />
          </div>
        </div>
      </div>

      <div className={styles.stats}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={styles.stat}>
            <Bar w="42px" h={18} />
            <Bar w="70px" h={10} />
          </div>
        ))}
      </div>

      <div className={styles.body}>
        <Bar w="120px" h={12} />
        {[0, 1].map((i) => (
          <div key={i} className={styles.item}>
            <Bar w="55%" h={13} />
            <Bar w="85%" h={11} />
            <Bar w="30%" h={11} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function HistorySkeleton({ rows = 4 }) {
  return (
    <div className={styles.list} role="status" aria-live="polite">
      <span className="sr-only">Loading scan history…</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles.row}>
          <Bar w="74px" h={20} />
          <div className={styles.rowCol}>
            <Bar w="180px" h={13} />
            <Bar w="60px" h={10} />
          </div>
          <Bar w="34px" h={18} />
        </div>
      ))}
    </div>
  );
}
