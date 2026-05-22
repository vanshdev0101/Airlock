"""
Orchestrates a full repo scan:
1. Fetch repo files and metadata
2. Run static analysis
3. Calculate trust score
4. Return structured result
"""

import logging
from datetime import datetime, timezone
from ..fetcher import RepoFetcher
from ..scanner import StaticScanner, calculate_trust_score
from ..scanner import ScanResult, ScanResponse, TrustLevel, PatternMatch

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    def __init__(self):
        self.fetcher = RepoFetcher()
        self.static = StaticScanner()

    async def scan(self, url: str) -> ScanResponse:
        try:
            # Step 1 — Fetch
            logger.info(f"Fetching repo: {url}")
            repo_data = await self.fetcher.fetch_repo(url)

            # Step 2 — Static scan
            logger.info(f"Scanning {len(repo_data['files'])} files")
            matches = self.static.scan_files(repo_data["files"])

            # Step 3 — Account signal matches
            account_matches = self._account_signals(repo_data)
            matches.extend(account_matches)

            # Step 4 — Score
            score = calculate_trust_score(matches)
            trust_level = self._score_to_level(score)

            # Step 5 — Build result
            result = ScanResult(
                url=url,
                repo_name=repo_data["repo_name"],
                scanned_at=datetime.now(timezone.utc),
                trust_level=trust_level,
                trust_score=score,
                account_info=repo_data["account_info"],
                matches=matches,
                files_scanned=len(repo_data["files"]),
                summary=self._build_summary(matches, score, trust_level, repo_data),
                recommendations=self._build_recommendations(matches, trust_level),
            )
            return ScanResponse(success=True, result=result)

        except ValueError as e:
            return ScanResponse(success=False, error=str(e))
        except Exception as e:
            logger.exception(f"Scan failed for {url}")
            return ScanResponse(success=False, error=f"Scan failed: {str(e)}")

    def _account_signals(self, repo_data: dict) -> list[PatternMatch]:
        """Convert account metadata into PatternMatch signals."""
        signals = []
        info = repo_data["account_info"]

        if info.is_new_account:
            signals.append(PatternMatch(
                category="account",
                pattern_name="new_account",
                description=f"Account '{info.username}' is only {info.account_age_days} days old — new accounts pushing trending repos is a major red flag",
                file_path="[account metadata]",
                severity=80,
            ))

        if info.is_typosquat and info.typosquat_target:
            signals.append(PatternMatch(
                category="account",
                pattern_name="typosquat",
                description=f"Username '{info.username}' looks like a typosquat of '{info.typosquat_target}' — 1-2 character difference from a trusted org",
                file_path="[account metadata]",
                severity=85,
            ))

        if info.total_repos is not None and info.total_repos <= 2 and info.is_new_account:
            signals.append(PatternMatch(
                category="account",
                pattern_name="sparse_account",
                description=f"Account has only {info.total_repos} repo(s) total — no established history",
                file_path="[account metadata]",
                severity=50,
            ))

        return signals

    def _score_to_level(self, score: int) -> TrustLevel:
        if score >= 70:
            return TrustLevel.SAFE
        if score >= 40:
            return TrustLevel.SUSPICIOUS
        return TrustLevel.DANGEROUS

    def _build_summary(
        self,
        matches: list[PatternMatch],
        score: int,
        trust_level: TrustLevel,
        repo_data: dict,
    ) -> str:
        repo = repo_data["repo_name"]

        if not matches:
            return f"No malicious patterns detected in {repo}. The repository appears safe to use."

        critical = [m for m in matches if m.severity >= 85]
        high = [m for m in matches if 65 <= m.severity < 85]

        parts = [f"RepoGuard detected {len(matches)} suspicious signal(s) in {repo}."]

        if trust_level == TrustLevel.DANGEROUS:
            parts.append("This repository is DANGEROUS and should NOT be cloned or executed.")
        elif trust_level == TrustLevel.SUSPICIOUS:
            parts.append("This repository is SUSPICIOUS. Review carefully before use.")

        if critical:
            names = ", ".join(set(m.pattern_name for m in critical))
            parts.append(f"Critical findings: {names}.")

        if repo_data["account_info"].is_new_account:
            parts.append("The uploading account was created very recently.")

        if repo_data["account_info"].is_typosquat:
            parts.append(
                f"The account name closely resembles '{repo_data['account_info'].typosquat_target}' — possible impersonation."
            )

        return " ".join(parts)

    def _build_recommendations(
        self, matches: list[PatternMatch], trust_level: TrustLevel
    ) -> list[str]:
        recs = []

        if trust_level == TrustLevel.DANGEROUS:
            recs.append("Do NOT clone or run any files from this repository")
            recs.append("Report the repository to Hugging Face or GitHub immediately")
            recs.append("If you already ran files from this repo, treat your system as compromised — rotate all credentials and SSH keys")

        if trust_level == TrustLevel.SUSPICIOUS:
            recs.append("Do not run any scripts (.py, .sh, .bat, .ps1) without reading them carefully first")
            recs.append("Consider scanning in an isolated VM or container")

        cats = {m.category for m in matches}

        if "network" in cats:
            recs.append("Monitor network traffic if you run this code — unexpected outbound connections are a strong indicator of malware")

        if "system_exec" in cats:
            recs.append("This code attempts to execute system commands — review every subprocess and os.system call before running")

        if "obfuscation" in cats:
            recs.append("Obfuscated code is present — decode and review all Base64 strings manually before trusting this repo")

        if "model_exploit" in cats:
            recs.append("Use torch.load(..., weights_only=True) instead of loading pickle files directly")

        if not recs:
            recs.append("Repository appears safe — standard precautions still apply when running third-party code")

        return recs
