import TrustScore from "./TrustScore.jsx";
import StatRow from "./StatRow.jsx";
import FindingsList from "./FindingsList.jsx";
import ExportMenu from "./ExportMenu.jsx";
import styles from "./ScanResult.module.css";

function AccountFlags({ account }) {
  const flags = [];
  if (account.is_typosquat) {
    flags.push({
      id: "typosquat",
      text: `Username resembles “${account.typosquat_target}”`,
    });
  }
  if (account.is_new_account) {
    flags.push({
      id: "new",
      text: `Account is only ${account.account_age_days} days old`,
    });
  }
  if (!flags.length) return null;

  return (
    <ul className={styles.flags}>
      {flags.map((f) => (
        <li key={f.id} className={styles.flag}>
          <span aria-hidden="true">▲</span>
          {f.text}
        </li>
      ))}
    </ul>
  );
}

export default function ScanResult({ result }) {
  const recs = result.recommendations ?? [];
  const hasRecs = recs.length && recs[0] !== "No major threats detected.";

  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <div className={styles.identity}>
            <a
              className={styles.repo}
              href={result.url}
              target="_blank"
              rel="noreferrer noopener"
            >
              {result.repo_name}
              <span aria-hidden="true" className={styles.ext}>
                ↗
              </span>
            </a>
            <p className={styles.summary}>{result.summary}</p>
          </div>
          <ExportMenu result={result} />
        </div>

        <TrustScore score={result.trust_score} level={result.trust_level} />
        <AccountFlags account={result.account_info} />
      </header>

      <StatRow result={result} />

      <FindingsList matches={result.matches} />

      {hasRecs && (
        <section className={styles.recs}>
          <h2 className={styles.recsHeading}>
            <span className={styles.slash}>//</span> recommendations
          </h2>
          <ul className={styles.recsList}>
            {recs.map((rec) => (
              <li key={rec} className={styles.rec}>
                <span aria-hidden="true" className={styles.recMark}>
                  →
                </span>
                {rec}
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
