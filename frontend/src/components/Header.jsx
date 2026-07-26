import styles from "./Header.module.css";

/* SVG rather than ☾/☀ — the Unicode glyphs have inconsistent metrics across
   fonts and clip inside a fixed-size button. */
function ThemeIcon({ theme }) {
  if (theme === "dark") {
    return (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M21 13.2A9 9 0 1 1 10.8 3a7.2 7.2 0 0 0 10.2 10.2Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2.2v2.4M12 19.4v2.4M4.2 12H1.8M22.2 12h-2.4M6.5 6.5 4.8 4.8M19.2 19.2l-1.7-1.7M17.5 6.5l1.7-1.7M4.8 19.2l1.7-1.7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Logo() {
  return (
    <span className={styles.logo} aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2.5 4.5 5.8v6.4c0 4.7 3.2 9.1 7.5 10.2 4.3-1.1 7.5-5.5 7.5-10.2V5.8L12 2.5Z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path
          d="m8.8 12.3 2.3 2.3 4.3-4.5"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export default function Header({ tab, onTabChange, theme, onThemeToggle }) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <Logo />
        <div>
          <h1 className={styles.wordmark}>
            RepoGuard<span className={styles.cursor} aria-hidden="true" />
          </h1>
          <p className={styles.tagline}>Repository security scanner</p>
        </div>
      </div>

      <div className={styles.actions}>
        <nav className={styles.tabs} aria-label="Views">
          {["scan", "history"].map((id) => (
            <button
              key={id}
              type="button"
              className={styles.tab}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => onTabChange(id)}
            >
              {id}
            </button>
          ))}
        </nav>

        <button
          type="button"
          className={styles.themeBtn}
          onClick={onThemeToggle}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <ThemeIcon theme={theme} />
        </button>
      </div>
    </header>
  );
}
