# Airlock🛡️

AI-powered security scanner for Hugging Face and GitHub repositories.
Detects malware, typosquatting, and supply chain attacks before you clone.

## Motivation

In May 2026, a fake OpenAI repository on Hugging Face was downloaded 244,000 times.
It contained a multi-stage infostealer that bypassed Windows Defender.
RepoGuard would have flagged it with a score of < 10 / 100.

## What it detects

- Base64 encoded payloads and eval/exec chains
- SSL verification disabled (allows C2 connections)
- PowerShell execution from Python loaders
- Windows Defender exclusion commands
- Privilege escalation and UAC bypass
- Persistence mechanisms (scheduled tasks, registry)
- Data exfiltration (SSH keys, browser data, crypto wallets)
- Self-deleting scripts
- Dead drop resolver patterns (jsonkeeper, pastebin)
- Malicious pickle files — see below
- VM/sandbox evasion techniques
- Typosquatted account names and dependency names
- Dependencies from non-official indexes, direct URLs, and npm install hooks
- New accounts with artificially trending repos

### Supply chain

`requirements*.txt`, `pyproject.toml` and `package.json` are parsed (never
resolved or installed). The scanner reports packages that come from somewhere
other than the official index, packages installed straight from a URL, npm
`preinstall`/`postinstall` hooks — which run automatically on `npm install` —
and names one edit from a popular package. Typosquat matching uses
Damerau-Levenshtein so that transpositions like `reqeusts` count as a single
edit, because that is how squatting actually looks.

### Pickle scanning

`torch.save()` writes pickles, so `pytorch_model.bin`, `.pt` and `.ckpt` files
are programs, not data: loading one runs whatever it names. RepoGuard reads the
pickle **opcode stream** with `pickletools.genops` and reports the callables the
file would import — it never unpickles anything.

Weight files are usually enormous and the pickle inside them is not, so the
scanner reads a torch archive's central directory over HTTP range requests and
pulls only the `data.pkl` member: roughly 12 KB out of a 90 MB checkpoint. Files
too large to retrieve whole are reported as **partially scanned** rather than
silently passed.

A repo that ships pickle weights with no `.safetensors` equivalent is flagged
as informational — safetensors cannot execute code, so publishing only the
executable format is worth a look.

## Stack

- Backend: Python + FastAPI
- Scanning: regex pattern registry + Python AST + pickle opcode analysis
  (no code execution — nothing scanned is ever imported, loaded or unpickled)
- AI layer: Claude API for model card analysis — planned, not yet wired
- Frontend: React + Vite
- Database: SQLite (dev) / PostgreSQL (prod)
- Deploy: Railway or Render

## Quick start

```bash
cd backend
cp .env.example .env          # add your API keys
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Run tests

```bash
cd backend
pytest app/tests/ -v
```

## API

```
POST /api/scan
{ "repo_url": "https://huggingface.co/owner/repo" }

GET  /api/scans?limit=20     # recent scan history, with finding counts
GET  /api/scans/{id}         # one past scan and the findings it recorded
GET  /api/health
```

Returns a trust score (0-100), trust level (safe/suspicious/dangerous),
detailed pattern matches with file locations and line numbers,
and plain English recommendations.

## Database

Schema changes go through Alembic (`backend/migrations/`). The app runs
`alembic upgrade head` on startup, so no manual step is needed in development;
a database created before migrations existed is stamped at the baseline
revision and upgraded from there without losing rows.

```bash
alembic revision --autogenerate -m "what changed"   # from backend/
alembic upgrade head
```
