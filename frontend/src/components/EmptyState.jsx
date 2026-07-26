import styles from "./EmptyState.module.css";

export default function EmptyState({ glyph, title, body, action, tone = "neutral" }) {
  return (
    <div className={styles.wrap} data-tone={tone}>
      <span className={styles.glyph} aria-hidden="true">
        {glyph}
      </span>
      <p className={styles.title}>{title}</p>
      {body && <p className={styles.body}>{body}</p>}
      {action}
    </div>
  );
}
