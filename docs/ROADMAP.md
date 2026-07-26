# RepoGuard Roadmap — from prototype to developer tool

**Target shape:** an installable scanner that runs in CI.
`repoguard scan <repo-or-path>` plus a GitHub Action that annotates pull
requests and fails the build on a dangerous verdict. The web UI stays as the
demo surface; it stops being the product.

**Status today:** a working prototype. FastAPI app with three endpoints, one
SQLite table, a synchronous scan, 35 passing tests. Several settings are
configured but wired to nothing (`rate_limit_*`, `cache_*`, `anthropic_api_key`,
`trusted_domains`); `RateLimitError` has a handler at `app/main.py:40` that
nothing raises. No Docker, no CI, no migrations.

---

## The thing that changes because of the CLI choice

In CI you scan **the checked-out working tree**, not a remote repository.

`app/fetcher/fetcher.py` can only fetch from the GitHub and Hugging Face APIs.
A GitHub Action that re-downloads the repo it is already sitting inside is
wrong on every axis: it burns API rate limit, needs a token to scan a private
repo the runner already has on disk, and — the fatal one — scans the *default
branch* rather than the pull request's code. It would pass a PR that adds
malware.

So `LocalFetcher` is a **prerequisite**, not an enhancement. It is the first
real work item.

The second consequence: the tool becomes a linter, and linters live or die on
their suppression story. One false positive with no way to silence it and the
team deletes the workflow file. `.repoguardignore` ships in v1, not v2.

---

## Phase 0 — Close the credibility gap — **complete**

*Nothing else is worth building until the scanner does what the README says.*

All four items shipped. 105 tests pass; the seven known-good benchmark repos
(requests, pydantic, httpx, fastapi, transformers, gpt2, bert-tiny) all score
safe, and a crafted pickle gadget still scores 15/dangerous.

### 0.1 Pickle and weights detection — **done**

Shipped in `app/scanner/pickle_scanner.py` + `app/fetcher/pickle_fetch.py`:
opcode analysis via `pickletools.genops`, range-request retrieval of the
`data.pkl` member out of torch archives, a `pickle_only_weights` nudge, and
explicit disclosure when a file was too large to read in full. Verified against
10 real Hugging Face models with zero false positives.

Not yet done from the original scope: nothing. Original notes kept below for
context.

<details>
<summary>Original plan</summary>
The fetcher only downloads text extensions (`fetcher.py:14`), so the scanner is
never handed a `.pkl` path and `pickle_checkpoint_detected`
(`static_scanner.py:198`) is unreachable dead code. Meanwhile the README
advertises "Malicious pickle files." Poisoned weights — the attack that has
actually happened on Hugging Face — currently score 100/safe.

- List binary artifacts (`.pkl`, `.bin`, `.pt`, `.pth`, `.h5`, `.ckpt`)
  from the file listing **without downloading them**.
- Flag their presence, weighted by whether a `.safetensors` equivalent exists.
  A repo shipping *only* pickles when safetensors is available is a real signal.
- Optional stretch: parse the pickle opcode stream (`pickletools.genops`)
  without unpickling, and flag `GLOBAL`/`REDUCE` opcodes referencing
  `os`, `subprocess`, `builtins.eval`. This is the actual detection, and it
  never executes anything.

</details>

### 0.2 Persist findings — **done**

`findings` table (`app/models/finding.py`) with a cascade from `scan_records`,
plus `files_scanned` on the scan itself. `GET /api/scans/{id}` returns a past
scan with its findings; `GET /api/scans` now carries `finding_count`.

Alembic is in (`migrations/`), and `init_db` runs `upgrade head` at startup
instead of `create_all`. Databases created by the old `create_all` are
*stamped* at revision 0001 rather than upgraded to it, so an existing dev
database adopts migrations without losing rows — verified against the 57-row
local database and against a fresh one.

This unblocks the diff-aware Action in Phase 3, the Phase 4 benchmark, and
baseline files.

### 0.3 Prioritised file budget — **done**

`_scan_priority` in `app/fetcher/fetcher.py` ranks by tier then directory
depth: install-time entrypoints, then manifests, then shell, Python, JS,
config, docs — with tests/examples and lockfiles pushed to the back. A
`setup.py` now survives truncation in a repo of 150 locale files.

**This change caused a regression and caught two real bugs.** Feeding the
scanner better files surfaced false positives that the old arbitrary budget
had been hiding: pydantic scored 15/dangerous and transformers 49/suspicious.
Both were capabilities being scored as threats —

- `base64_decode` 70 → 35 and `unsafe_pickle_load` 85 → 55. Calling
  `b64decode` *is* pydantic's Base64 type; exposing a pickle parser is a
  documented pydantic API. The malware-grade variants (`base64_decode_exec`,
  `malicious_reduce_payload`, and the opcode scanner) cover the actual attacks.
- A new `prose_severity` on `Pattern`. transformers' only "finding" was inside
  an error message reading "set the option \`trust_remote_code=True\`".
  Matches that fall inside a string literal are downgraded rather than
  dropped, located by `tokenize` with **column** precision — line precision is
  not enough, because `from_pretrained('org/model', trust_remote_code=True)`
  has an unrelated string on the same line.

### 0.4 Dependency scanning — **done**

`app/scanner/dependency_scanner.py` parses `requirements*.txt`,
`pyproject.toml` (PEP 621 and poetry) and `package.json`. Reports:

| Finding | Severity | Why |
|---|---|---|
| `dependency_alternate_index` | 85 | whoever owns the index owns the install; `--extra-index-url` is the dependency-confusion mechanic |
| `dependency_typosquat` | 80 | name one edit from a popular package |
| `npm_install_hook` | 75 | `preinstall`/`postinstall` run automatically on `npm install` |
| `dependency_direct_url` | 70–80 | contents can change without the requirement changing |

Typosquat detection uses **Damerau**-Levenshtein, not plain Levenshtein:
`requests` → `reqeusts` is a transposition, which plain edit distance scores
as 2 and would have missed entirely. Parsing only — nothing is resolved,
downloaded or installed.

---

## Phase 1 — Extract the core

The scanner is already cleanly decoupled: `static_scanner.py` imports only
`.scan`, which is pure Pydantic. The fetcher's only coupling is
`get_settings()`. So this is a move, not a rewrite.

```
repoguard/            # installable core — no FastAPI, no DB
  fetcher/            # RemoteFetcher + LocalFetcher behind one interface
  scanner/
  scoring.py
  models.py
  config.py           # plain dataclass; settings injected, not imported
  cli.py
server/               # FastAPI wrapper that imports repoguard
frontend/
action/
```

The core must not import `pydantic-settings`, `sqlalchemy`, or `fastapi`.
Configuration is passed in. This is the difference between a package and an
app with a CLI bolted on.

**LocalFetcher** walks a directory with the same extension filter, size cap and
budget as the remote path, respecting `.gitignore`. Same interface, so the
scanner cannot tell the difference and the existing tests keep working.

---

## Phase 2 — The CLI

```
repoguard scan .                        # working tree
repoguard scan psf/requests             # remote
repoguard scan --format sarif -o out.sarif
repoguard scan --fail-on dangerous
```

The contract with CI is **exit codes**, and they need to be right from the
first release because changing them later breaks everyone's pipeline:

| Code | Meaning |
|------|---------|
| 0 | scan completed, verdict at or above the `--fail-on` threshold |
| 1 | scan completed, verdict below threshold — this is the build failure |
| 2 | scan could not complete (network, auth, unreadable repo) |

Code 2 must never be confused with code 1. "We couldn't scan it" is not "it's
clean" — the same principle already enforced by `_require_readable_files`.

**Output formats:**
- `human` — default when stdout is a TTY. Colour, grouped by severity.
- `json` — the full result, stable and versioned.
- **`sarif`** — the highest-leverage feature in this entire document.
  GitHub Code Scanning ingests SARIF natively and renders each finding as an
  inline annotation on the changed line of a pull request, with no UI work on
  your side. This is what makes the tool feel native rather than bolted on.

**Suppression** — non-negotiable:
- `.repoguardignore` — glob paths and pattern names.
- `# repoguard: ignore[pattern_name] — reason` inline comments.
- Require the reason. A suppression without a justification is a silent hole.

**Packaging:** `pyproject.toml`, `repoguard` console entry point, publish to
PyPI. `pipx install repoguard` and `uvx repoguard scan .` should both work.

---

## Phase 3 — The GitHub Action

`action.yml` + a thin container. Behaviour:

- Runs on `pull_request`, scans the checked-out tree via `LocalFetcher`.
- Uploads SARIF to `github/codeql-action/upload-sarif` → inline PR annotations
  for free.
- **Diff-aware:** only fail on findings *introduced by the PR*. Scanning main
  and the head, then reporting the delta, is what makes the tool adoptable on
  an existing codebase — otherwise the first run reports 200 legacy findings
  and gets disabled the same day. This is why Phase 0.2 comes first.
- Inputs: `fail-on`, `paths`, `config`.

Ship alongside: a pre-commit hook definition, and a `docker run` one-liner.

---

## Phase 4 — Make the verdict defensible

The score is currently a hand-tuned heuristic — the 95 instant-fail cut, the
quadratic curve, the category weights were calibrated against roughly seven
known-good repos and one synthetic attack chain. That is calibration by
anecdote, and for a tool that fails people's builds it is not enough.

- **A labelled corpus.** ~50 known-good repos, plus known-malicious samples.
  Committed as a manifest of repo IDs and pinned commit SHAs, not vendored code.
- **A benchmark command** that runs the corpus and reports precision and recall.
  Run it in CI and fail on regression. This turns "I tuned it and it felt right"
  into a number that moves in a direction.
- **Publish the number** in the README. A security tool that will not state its
  own false-positive rate is asking for trust it has not earned.

---

## Phase 5 — Production hygiene

Needed for the server, which survives as the demo and as the hosted API:

- Async scans (`202 + scan_id`, poll or SSE). `POST /scan` currently holds the
  HTTP connection through the entire fetch, which is what caps the file budget.
- Wire up the cache and rate limiting that are already configured and unused.
- Shareable `/scan/:id` URLs with frontend routing. A result cannot be linked
  today.
- Postgres, Docker Compose, structured logging.
- GitHub Actions CI: pytest, ruff, eslint, frontend build, and the Phase 4
  benchmark.
- Dependabot, and a `SECURITY.md` — a security tool without a disclosure policy
  is a bad look.

---

## Sequencing

Phase 0 is complete, so the next step is Phase 1 (extract the core), which
Phase 2 depends on. Original reasoning below.

Phase 0.1 and 0.2 first — they are self-contained, and 0.2 unblocks the
diff-aware Action which is the whole point of Phase 3. Phase 1 must land before
Phase 2, since a CLI that imports FastAPI to scan a local folder is the kind of
thing that gets a package uninstalled.

```
0.1 pickle detection      ──┐
0.2 persist findings      ──┼──> 1 extract core ──> 2 CLI ──> 3 Action
0.3 file budget           ──┤                                   ▲
0.4 dependency scanning   ──┘                     4 benchmark ──┘
                                                  5 hygiene (parallel)
```

**Minimum viable "real tool":** 0.1 + 0.2 + 1 + 2 + 3, with `--format sarif`
and `.repoguardignore`. That is the point where someone other than you can
install it and get value on day one.

---

## Deliberately not doing

- **User accounts and multi-tenancy.** The CLI shape needs no auth. Adding it
  now buys nothing and costs a permissions model.
- **The Claude model-card layer.** `anthropic_api_key` is a dead setting. An
  LLM pass over model cards is a plausible Phase 6, but it makes scans slow,
  costly and non-deterministic — all three are disqualifying inside CI. If it
  returns, it belongs behind an explicit `--deep` flag on the server path only.
- **Sandboxed execution.** Detonating untrusted code is a different product with
  a different risk profile. Static analysis is the honest scope.
