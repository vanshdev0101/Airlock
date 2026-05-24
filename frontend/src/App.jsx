import { useState, useRef } from "react";

const C = {
  graphite: "#363635",
  ebony: "#595A4A",
  neon: "#B0FE76",
  green: "#81E979",
  teal: "#8FBB99",
};

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Roboto:wght@300;400;500&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: ${C.graphite};
    color: #e8e8e6;
    font-family: 'Roboto', sans-serif;
    min-height: 100vh;
  }

  .mono { font-family: 'Space Mono', monospace; }

  .app {
    max-width: 860px;
    margin: 0 auto;
    padding: 3rem 2rem;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .app > * { width: 100%; }

  .header {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.85rem;
    margin-bottom: 3rem;
  }

  .brand {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
  }

  .logo-mark {
    width: 48px;
    height: 48px;
    background: ${C.neon};
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .logo-mark svg { width: 26px; height: 26px; }

  .brand h1 {
    font-family: 'Space Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    color: ${C.neon};
    letter-spacing: -0.02em;
    line-height: 1;
  }

  .brand p {
    font-size: 0.75rem;
    color: ${C.teal};
    margin-top: 3px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 400;
  }

  .scan-box {
    background: ${C.ebony};
    border-radius: 14px;
    padding: 2rem;
    margin-bottom: 2rem;
    border: 1px solid rgba(176, 254, 118, 0.1);
  }

  .scan-label {
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: ${C.teal};
    margin-bottom: 0.75rem;
    font-family: 'Space Mono', monospace;
  }

  .input-row {
    display: flex;
    gap: 0.75rem;
  }

  .url-input {
    flex: 1;
    background: ${C.graphite};
    border: 1px solid rgba(143, 187, 153, 0.25);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    color: #e8e8e6;
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    outline: none;
    transition: border-color 0.2s;
  }

  .url-input::placeholder { color: rgba(143,187,153,0.4); }
  .url-input:focus { border-color: ${C.neon}; }

  .scan-btn {
    background: ${C.neon};
    color: ${C.graphite};
    border: none;
    border-radius: 8px;
    padding: 0.85rem 1.5rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s, transform 0.1s;
    letter-spacing: 0.03em;
  }

  .scan-btn:hover { background: ${C.green}; }
  .scan-btn:active { transform: scale(0.97); }
  .scan-btn:disabled {
    background: ${C.ebony};
    color: ${C.teal};
    cursor: not-allowed;
    border: 1px solid rgba(143,187,153,0.2);
  }

  .examples {
    margin-top: 1rem;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .examples span {
    font-size: 0.72rem;
    color: ${C.teal};
    font-family: 'Space Mono', monospace;
  }

  .example-pill {
    background: rgba(143,187,153,0.08);
    border: 1px solid rgba(143,187,153,0.2);
    border-radius: 100px;
    padding: 3px 10px;
    font-size: 0.7rem;
    font-family: 'Space Mono', monospace;
    color: ${C.teal};
    cursor: pointer;
    transition: all 0.15s;
  }

  .example-pill:hover {
    background: rgba(176,254,118,0.1);
    border-color: ${C.neon};
    color: ${C.neon};
  }

  .scanning-bar {
    height: 3px;
    background: rgba(143,187,153,0.1);
    border-radius: 2px;
    margin-top: 1rem;
    overflow: hidden;
  }

  .scanning-bar-inner {
    height: 100%;
    background: ${C.neon};
    border-radius: 2px;
    animation: scan-progress 2.2s ease-in-out infinite;
  }

  @keyframes scan-progress {
    0% { width: 0%; margin-left: 0%; }
    50% { width: 60%; margin-left: 20%; }
    100% { width: 0%; margin-left: 100%; }
  }

  .result-card {
    background: ${C.ebony};
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(176, 254, 118, 0.1);
    animation: fade-up 0.35s ease;
  }

  @keyframes fade-up {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .result-header {
    padding: 1.5rem 2rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  .trust-ring {
    position: relative;
    width: 72px;
    height: 72px;
    flex-shrink: 0;
  }

  .trust-ring svg {
    transform: rotate(-90deg);
    display: block;
  }

  .trust-score-label {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0;
    pointer-events: none;
  }

  .trust-score-num {
    font-family: 'Space Mono', monospace;
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1;
    display: block;
  }

  .trust-score-sub {
    font-size: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: ${C.teal};
    display: block;
    margin-top: 3px;
  }

  .result-meta { flex: 1; min-width: 0; }

  .result-repo {
    font-family: 'Space Mono', monospace;
    font-size: 1rem;
    font-weight: 700;
    color: #e8e8e6;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .result-summary {
    font-size: 0.85rem;
    color: rgba(232,232,230,0.65);
    margin-top: 0.35rem;
    line-height: 1.5;
  }

  .trust-badge {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 5px 12px;
    border-radius: 100px;
    flex-shrink: 0;
  }

  .badge-safe { background: rgba(176,254,118,0.15); color: ${C.neon}; }
  .badge-suspicious { background: rgba(255,193,7,0.12); color: #ffc107; }
  .badge-dangerous { background: rgba(255,82,82,0.12); color: #ff5252; }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  .stat-cell {
    padding: 1.1rem 2rem;
    border-right: 1px solid rgba(255,255,255,0.06);
  }

  .stat-cell:last-child { border-right: none; }

  .stat-val {
    font-family: 'Space Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
    color: ${C.neon};
  }

  .stat-lbl {
    font-size: 0.72rem;
    color: ${C.teal};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 2px;
  }

  .matches-section { padding: 1.5rem 2rem; }

  .section-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: ${C.teal};
    margin-bottom: 1rem;
  }

  .no-threats {
    text-align: center;
    padding: 2rem;
    color: ${C.neon};
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
  }

  .match-item {
    background: rgba(54,54,53,0.6);
    border-radius: 8px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.6rem;
    border-left: 3px solid transparent;
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.75rem;
    align-items: start;
  }

  .match-item.sev-critical { border-left-color: #ff5252; }
  .match-item.sev-high { border-left-color: #ff9100; }
  .match-item.sev-medium { border-left-color: #ffc107; }
  .match-item.sev-low { border-left-color: ${C.teal}; }

  .match-sev {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 4px;
    text-transform: uppercase;
    white-space: nowrap;
    margin-top: 1px;
  }

  .sev-critical .match-sev { background: rgba(255,82,82,0.15); color: #ff5252; }
  .sev-high .match-sev { background: rgba(255,145,0,0.15); color: #ff9100; }
  .sev-medium .match-sev { background: rgba(255,193,7,0.15); color: #ffc107; }
  .sev-low .match-sev { background: rgba(143,187,153,0.15); color: ${C.teal}; }

  .match-body {}

  .match-name {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    color: #e8e8e6;
    margin-bottom: 3px;
  }

  .match-desc {
    font-size: 0.78rem;
    color: rgba(232,232,230,0.6);
    line-height: 1.45;
  }

  .match-file {
    font-family: 'Space Mono', monospace;
    font-size: 0.62rem;
    color: ${C.teal};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
    text-align: right;
    margin-top: 2px;
  }

  .recs-section {
    padding: 0 2rem 1.5rem;
  }

  .rec-item {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    padding: 0.5rem 0;
    font-size: 0.82rem;
    color: rgba(232,232,230,0.75);
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }

  .rec-item:last-child { border-bottom: none; }

  .rec-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${C.teal};
    flex-shrink: 0;
    margin-top: 6px;
  }

  .error-box {
    background: rgba(255,82,82,0.08);
    border: 1px solid rgba(255,82,82,0.2);
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    color: #ff7070;
    font-size: 0.85rem;
    font-family: 'Space Mono', monospace;
  }

  .account-row {
    padding: 1rem 2rem;
    border-top: 1px solid rgba(255,255,255,0.06);
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
  }

  .acct-item {
    font-size: 0.75rem;
  }

  .acct-lbl {
    color: ${C.teal};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.65rem;
    margin-bottom: 2px;
  }

  .acct-val {
    font-family: 'Space Mono', monospace;
    color: #e8e8e6;
  }

  .acct-warn { color: #ffc107; }
`;

const EXAMPLES = [
  "https://github.com/psf/requests",
  "https://github.com/pallets/flask",
  "https://huggingface.co/openai-community/gpt2",
];

function sevClass(s) {
  if (s >= 90) return "sev-critical";
  if (s >= 75) return "sev-high";
  if (s >= 55) return "sev-medium";
  return "sev-low";
}

function sevLabel(s) {
  if (s >= 90) return "critical";
  if (s >= 75) return "high";
  if (s >= 55) return "medium";
  return "low";
}

function TrustRing({ score, level }) {
  const r = 30;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = level === "safe" ? "#B0FE76" : level === "suspicious" ? "#ffc107" : "#ff5252";

  return (
    <div className="trust-ring">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="5" />
        <circle
          cx="36" cy="36" r={r}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeDasharray={`${fill} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="trust-score-label">
        <span className="trust-score-num" style={{ color }}>{score}</span>
        <span className="trust-score-sub">score</span>
      </div>
    </div>
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function runScan(scanUrl) {
    const target = (scanUrl || url).trim();
    if (!target) return;

    // Friendly validation before hitting backend
    if (!target.startsWith("http")) {
      setError("Paste the full link from your browser — it should start with https://");
      return;
    }
    if (!target.includes("github.com") && !target.includes("huggingface.co")) {
      setError("Only GitHub and Hugging Face repos are supported. Example: https://github.com/owner/repo");
      return;
    }
    const parts = target.replace("https://", "").split("/").filter(Boolean);
    if (parts.length < 3) {
      setError("Link needs an owner and repo name. Example: https://github.com/psf/requests");
      return;
    }
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: target.trim() }),
      });
      const data = await res.json();
      if (!data.success) {
        const raw = data.error || "Scan failed";
        const friendly = raw.includes("404") || raw.includes("not found")
          ? "Repo not found — check the link is public and spelled correctly"
          : raw.includes("timeout") || raw.includes("timed out")
          ? "Scan timed out — the repo may be too large or GitHub is slow right now"
          : raw.includes("rate limit")
          ? "GitHub rate limit hit — wait a minute and try again"
          : "Something went wrong. Make sure the repo is public and try again.";
        throw new Error(friendly);
      }
      setResult(data.result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function useExample(ex) {
    setUrl(ex);
    inputRef.current?.focus();
  }

  const r = result;

  return (
    <>
      <style>{styles}</style>
      <div className="app">
        <header style={{ display:"flex", flexDirection:"row", alignItems:"center", justifyContent:"center", gap:"0.9rem", marginBottom:"3rem" }}>
          <div style={{ width:48, height:48, background:"#B0FE76", borderRadius:10, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
              <path d="M13 2L4 6v7c0 5.25 3.8 10.15 9 11.35C18.2 23.15 22 18.25 22 13V6L13 2z" fill="#363635"/>
              <path d="M13 3.5L5.5 7v6c0 4.5 3.25 8.7 7.5 9.75C17.25 21.7 20.5 17.5 20.5 13V7L13 3.5z" fill="#B0FE76" opacity="0.9"/>
              <path d="M9.5 13l2.5 2.5 5-5" stroke="#363635" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <h1 style={{ fontFamily:"'Space Mono',monospace", fontSize:"1.4rem", fontWeight:700, color:"#B0FE76", margin:0, lineHeight:1 }}>RepoGuard</h1>
            <p style={{ fontFamily:"'Roboto',sans-serif", fontSize:"0.72rem", color:"#8FBB99", margin:0, letterSpacing:"0.1em", textTransform:"uppercase" }}>AI-powered security scanner</p>
          </div>
        </header>

        <div className="scan-box">
          <div className="scan-label">// scan target</div>
          <div className="input-row">
            <input
              ref={inputRef}
              className="url-input"
              placeholder="https://github.com/owner/repo  or  https://huggingface.co/org/model"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && runScan()}
            />
            <button className="scan-btn" onClick={() => runScan()} disabled={loading || !url.trim()}>
              {loading ? "scanning..." : "▶ scan"}
            </button>
          </div>
          <div className="examples">
            <span>try:</span>
            {EXAMPLES.map(ex => (
              <button key={ex} className="example-pill" onClick={() => useExample(ex)}>
                {ex.replace("https://", "").split("/").slice(0, 2).join("/")}
              </button>
            ))}
          </div>
          {loading && (
            <div className="scanning-bar">
              <div className="scanning-bar-inner" />
            </div>
          )}
        </div>

        {error && (
          <div className="error-box">⚠ {error}</div>
        )}

        {r && (
          <div className="result-card">
            <div className="result-header">
              <TrustRing score={r.trust_score} level={r.trust_level} />
              <div className="result-meta">
                <div className="result-repo">{r.repo_name}</div>
                <div className="result-summary">{r.summary}</div>
              </div>
              <span className={`trust-badge badge-${r.trust_level}`}>
                {r.trust_level}
              </span>
            </div>

            <div className="stats-row">
              <div className="stat-cell">
                <div className="stat-val">{r.files_scanned}</div>
                <div className="stat-lbl">files scanned</div>
              </div>
              <div className="stat-cell">
                <div className="stat-val" style={{ color: r.matches.length > 0 ? "#ff9100" : "#B0FE76" }}>
                  {r.matches.length}
                </div>
                <div className="stat-lbl">threats found</div>
              </div>
              <div className="stat-cell">
                <div className="stat-val">{r.trust_score}</div>
                <div className="stat-lbl">trust score</div>
              </div>
            </div>

            {r.matches.length > 0 ? (
              <div className="matches-section">
                <div className="section-title">// threat findings</div>
                {r.matches.map((m, i) => (
                  <div key={i} className={`match-item ${sevClass(m.severity)}`}>
                    <span className="match-sev">{sevLabel(m.severity)}</span>
                    <div className="match-body">
                      <div className="match-name">{m.pattern_name}</div>
                      <div className="match-desc">{m.description}</div>
                      {m.snippet && (
                        <div style={{ fontFamily: "Space Mono, monospace", fontSize: "0.68rem", color: "#8FBB99", marginTop: 5, padding: "4px 8px", background: "rgba(54,54,53,0.8)", borderRadius: 4 }}>
                          {m.snippet}
                        </div>
                      )}
                    </div>
                    <div className="match-file">
                      {m.file_path}{m.line_number ? `:${m.line_number}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-threats">✓ no threats detected</div>
            )}

            {r.recommendations?.length > 0 && r.recommendations[0] !== "No major threats detected." && (
              <div className="recs-section">
                <div className="section-title">// recommendations</div>
                {r.recommendations.map((rec, i) => (
                  <div key={i} className="rec-item">
                    <div className="rec-dot" />
                    {rec}
                  </div>
                ))}
              </div>
            )}

            <div className="account-row">
              <div className="acct-item">
                <div className="acct-lbl">account</div>
                <div className="acct-val">{r.account_info.username}</div>
              </div>
              <div className="acct-item">
                <div className="acct-lbl">age</div>
                <div className="acct-val">
                  {r.account_info.account_age_days != null ? `${r.account_info.account_age_days}d` : "—"}
                </div>
              </div>
              <div className="acct-item">
                <div className="acct-lbl">repos</div>
                <div className="acct-val">{r.account_info.total_repos ?? "—"}</div>
              </div>
              {r.account_info.is_typosquat && (
                <div className="acct-item">
                  <div className="acct-lbl">warning</div>
                  <div className="acct-val acct-warn">⚠ typosquat of {r.account_info.typosquat_target}</div>
                </div>
              )}
              {r.account_info.is_new_account && (
                <div className="acct-item">
                  <div className="acct-lbl">flag</div>
                  <div className="acct-val acct-warn">⚠ new account</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}