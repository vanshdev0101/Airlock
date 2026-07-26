import styles from "./StatRow.module.css";

/** Stat tile contract: label (sentence case, no colon) + value. */
function Stat({ label, value, tone = "default" }) {
  return (
    <div className={styles.tile}>
      <div className={styles.value} data-tone={tone}>
        {value}
      </div>
      <div className={styles.label}>{label}</div>
    </div>
  );
}

export default function StatRow({ result }) {
  const { files_scanned, matches, account_info } = result;
  const age = account_info.account_age_days;

  return (
    <div className={styles.row}>
      <Stat label="Files scanned" value={files_scanned} />
      <Stat
        label={matches.length === 1 ? "Finding" : "Findings"}
        value={matches.length}
        tone={matches.length ? "alert" : "ok"}
      />
      <Stat
        label="Account age"
        value={age != null ? `${age}d` : "—"}
        tone={account_info.is_new_account ? "alert" : "default"}
      />
      <Stat label="Repositories" value={account_info.total_repos ?? "—"} />
    </div>
  );
}
