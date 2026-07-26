import { useCallback, useEffect, useRef, useState } from "react";

import Header from "./components/Header.jsx";
import ScanForm from "./components/ScanForm.jsx";
import ScanResult from "./components/ScanResult.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import EmptyState from "./components/EmptyState.jsx";
import { ScanResultSkeleton } from "./components/Skeleton.jsx";

import { scanRepo, validateUrl } from "./lib/api.js";
import { useTheme } from "./lib/useTheme.js";
import styles from "./App.module.css";

export default function App() {
  const { theme, toggle } = useTheme();

  const [tab, setTab] = useState("scan");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);

  // Abort an in-flight scan if another starts or the component unmounts.
  const abortRef = useRef(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  const runScan = useCallback(async (target) => {
    const trimmed = (target ?? "").trim();
    const invalid = validateUrl(trimmed);
    if (invalid) {
      setError(invalid);
      setResult(null);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setScanning(true);
    setError(null);
    setResult(null);

    try {
      const scan = await scanRepo(trimmed, { signal: controller.signal });
      setResult(scan);
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message);
    } finally {
      if (abortRef.current === controller) setScanning(false);
    }
  }, []);

  const openFromHistory = useCallback(
    (repoUrl) => {
      setUrl(repoUrl);
      setTab("scan");
      runScan(repoUrl);
    },
    [runScan]
  );

  return (
    <div className={styles.shell}>
      <div className={styles.container}>
        <Header
          tab={tab}
          onTabChange={setTab}
          theme={theme}
          onThemeToggle={toggle}
        />

        <main>
          {tab === "scan" ? (
            <div className={styles.stack}>
              <ScanForm
                url={url}
                onUrlChange={setUrl}
                onSubmit={runScan}
                loading={scanning}
              />

              {error && (
                <EmptyState
                  tone="error"
                  glyph="!"
                  title="Scan failed"
                  body={error}
                />
              )}

              {scanning && <ScanResultSkeleton />}

              {!scanning && result && <ScanResult result={result} />}

              {!scanning && !result && !error && (
                <EmptyState
                  glyph="▮"
                  title="Nothing scanned yet"
                  body="Paste a GitHub or Hugging Face repository URL above. RepoGuard reads the repo's source files and flags malware patterns, typosquatting and supply-chain risks — without executing anything."
                />
              )}
            </div>
          ) : (
            <div className={styles.stack}>
              <h2 className={styles.sectionHeading}>
                <span className={styles.slash}>//</span> recent scans
              </h2>
              <HistoryPanel onSelect={openFromHistory} />
            </div>
          )}
        </main>

        <footer className={styles.footer}>
          <span>
            Static analysis only — RepoGuard never executes the code it scans.
          </span>
        </footer>
      </div>
    </div>
  );
}
