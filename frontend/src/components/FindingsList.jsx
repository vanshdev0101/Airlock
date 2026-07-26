import { useMemo, useState } from "react";
import { severityTier, categoryLabel, SEVERITY_TIERS } from "../lib/severity.js";
import styles from "./FindingsList.module.css";

const SORTS = {
  severity: { label: "Severity", fn: (a, b) => b.severity - a.severity },
  file: {
    label: "File",
    fn: (a, b) =>
      a.file_path.localeCompare(b.file_path) ||
      (a.line_number ?? 0) - (b.line_number ?? 0),
  },
  category: {
    label: "Category",
    fn: (a, b) =>
      a.category.localeCompare(b.category) || b.severity - a.severity,
  },
};

function Finding({ match }) {
  const tier = severityTier(match.severity);
  const where = match.line_number
    ? `${match.file_path}:${match.line_number}`
    : match.file_path;

  return (
    <li className={styles.item} data-tier={tier.id}>
      <div className={styles.head}>
        {/* Glyph + text label, so severity is never colour-alone. */}
        <span className={styles.tier}>
          <span aria-hidden="true">{tier.glyph}</span>
          {tier.label}
        </span>
        <code className={styles.name}>{match.pattern_name}</code>
        <span className={styles.category}>{categoryLabel(match.category)}</span>
        <span className={styles.severityNum} title="Severity score">
          {match.severity}
        </span>
      </div>

      <p className={styles.desc}>{match.description}</p>

      {match.snippet && <pre className={styles.snippet}><code>{match.snippet}</code></pre>}

      <div className={styles.where}>
        <span aria-hidden="true">↳</span>
        <code>{where}</code>
      </div>
    </li>
  );
}

export default function FindingsList({ matches }) {
  const [tier, setTier] = useState("all");
  const [sort, setSort] = useState("severity");

  // Only offer filters that would actually match something.
  const counts = useMemo(() => {
    const c = {};
    for (const m of matches) {
      const id = severityTier(m.severity).id;
      c[id] = (c[id] ?? 0) + 1;
    }
    return c;
  }, [matches]);

  const visible = useMemo(() => {
    const filtered =
      tier === "all"
        ? matches
        : matches.filter((m) => severityTier(m.severity).id === tier);
    return [...filtered].sort(SORTS[sort].fn);
  }, [matches, tier, sort]);

  if (!matches.length) {
    return (
      <section className={styles.section}>
        <div className={styles.clear}>
          <span className={styles.clearGlyph} aria-hidden="true">
            ✓
          </span>
          <p className={styles.clearTitle}>No threats detected</p>
          <p className={styles.clearBody}>
            Nothing in the scanned files matched a known malicious pattern.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.section}>
      <div className={styles.toolbar}>
        <h2 className={styles.heading}>
          <span className={styles.slash}>//</span> findings
        </h2>

        <div className={styles.controls}>
          <div className={styles.filters} role="group" aria-label="Filter by severity">
            <button
              type="button"
              className={styles.filter}
              aria-pressed={tier === "all"}
              onClick={() => setTier("all")}
            >
              All {matches.length}
            </button>
            {SEVERITY_TIERS.filter((t) => counts[t.id]).map((t) => (
              <button
                key={t.id}
                type="button"
                className={styles.filter}
                data-tier={t.id}
                aria-pressed={tier === t.id}
                onClick={() => setTier(t.id)}
              >
                {t.label} {counts[t.id]}
              </button>
            ))}
          </div>

          <label className={styles.sort}>
            <span className={styles.sortLabel}>sort</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              {Object.entries(SORTS).map(([id, s]) => (
                <option key={id} value={id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className={styles.noMatch}>No findings at this severity.</p>
      ) : (
        <ul className={styles.list}>
          {visible.map((m, i) => (
            <Finding key={`${m.pattern_name}-${m.file_path}-${m.line_number ?? i}`} match={m} />
          ))}
        </ul>
      )}
    </section>
  );
}
