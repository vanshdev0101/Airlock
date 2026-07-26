import { useEffect, useRef, useState } from "react";
import { toMarkdown, toJson, copyText } from "../lib/report.js";
import styles from "./ExportMenu.module.css";

export default function ExportMenu({ result }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(null), 2000);
    return () => clearTimeout(t);
  }, [copied]);

  async function copy(kind) {
    const text = kind === "json" ? toJson(result) : toMarkdown(result);
    const ok = await copyText(text);
    setCopied(ok ? kind : "failed");
    setOpen(false);
  }

  function download() {
    const blob = new Blob([toMarkdown(result)], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `repoguard-${result.repo_name.replace("/", "-")}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
    setOpen(false);
  }

  const message =
    copied === "failed"
      ? "Copy failed"
      : copied === "json"
        ? "JSON copied"
        : copied
          ? "Markdown copied"
          : null;

  return (
    <div className={styles.wrap} ref={wrapRef}>
      {message && (
        <span className={styles.toast} role="status">
          {message}
        </span>
      )}
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((o) => !o)}
      >
        Export
        <span aria-hidden="true" className={styles.caret}>
          ▾
        </span>
      </button>

      {open && (
        <div className={styles.menu} role="menu">
          <button type="button" role="menuitem" onClick={() => copy("markdown")}>
            Copy as Markdown
          </button>
          <button type="button" role="menuitem" onClick={() => copy("json")}>
            Copy as JSON
          </button>
          <button type="button" role="menuitem" onClick={download}>
            Download .md
          </button>
        </div>
      )}
    </div>
  );
}
