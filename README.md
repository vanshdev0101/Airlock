# RepoGuard 🛡️

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
- Malicious pickle files
- VM/sandbox evasion techniques
- Typosquatted account names
- New accounts with artificially trending repos

## Stack

- Backend: Python + FastAPI
- AI layer: Claude API (model card analysis)
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
pytest tests/ -v
```

## API

```
POST /api/scan
{ "url": "https://huggingface.co/owner/repo" }
```

Returns a trust score (0-100), trust level (safe/suspicious/dangerous),
detailed pattern matches with file locations and line numbers,
and plain English recommendations.
