import { useRef } from "react";
import styles from "./ScanForm.module.css";

const EXAMPLES = [
  "https://github.com/psf/requests",
  "https://github.com/pallets/flask",
  "https://huggingface.co/openai-community/gpt2",
];

const shortLabel = (url) =>
  url.replace(/^https?:\/\//, "").split("/").slice(1).join("/");

export default function ScanForm({ url, onUrlChange, onSubmit, loading }) {
  const inputRef = useRef(null);

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit(url);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="scan-url">
        <span className={styles.slash}>//</span> scan target
      </label>

      <div className={styles.inputRow}>
        <div className={styles.inputWrap}>
          <span className={styles.prompt} aria-hidden="true">
            &gt;
          </span>
          <input
            id="scan-url"
            ref={inputRef}
            className={styles.input}
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck="false"
            placeholder="github.com/owner/repo  ·  huggingface.co/org/model"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          className={styles.submit}
          disabled={loading || !url.trim()}
        >
          {loading ? "scanning…" : "scan"}
        </button>
      </div>

      <div className={styles.examples}>
        <span className={styles.examplesLabel}>try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            className={styles.pill}
            disabled={loading}
            onClick={() => {
              onUrlChange(ex);
              inputRef.current?.focus();
            }}
          >
            {shortLabel(ex)}
          </button>
        ))}
      </div>
    </form>
  );
}
