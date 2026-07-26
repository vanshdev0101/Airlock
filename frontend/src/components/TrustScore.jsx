import { trustLevel } from "../lib/severity.js";
import styles from "./TrustScore.module.css";

/**
 * Trust score is a single ratio against a limit, so the form is a meter with a
 * hero figure — not a donut. The unfilled track is a lighter step of the same
 * hue as the fill, so the state reads across the whole bar rather than only
 * the filled part.
 */
export default function TrustScore({ score, level }) {
  const { label, glyph, status } = trustLevel(level);

  return (
    <div className={styles.wrap} data-status={status}>
      <div className={styles.figure}>
        <span className={styles.score}>{score}</span>
        <span className={styles.outOf}>/100</span>
      </div>

      <div className={styles.meterCol}>
        <div
          className={styles.track}
          role="meter"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Trust score ${score} of 100 — ${label}`}
        >
          <div className={styles.fill} style={{ inlineSize: `${score}%` }} />
        </div>
        <div className={styles.legend}>
          {/* Glyph + label, so the status is never colour-alone. */}
          <span className={styles.badge}>
            <span aria-hidden="true">{glyph}</span>
            {label}
          </span>
          <span className={styles.scale} aria-hidden="true">
            0 · 40 · 70 · 100
          </span>
        </div>
      </div>
    </div>
  );
}
