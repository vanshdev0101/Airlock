"""
Orchestrates a full repo scan:
1. Fetch repo files and metadata
2. Run static analysis
3. Calculate trust score
4. Persist to DB
5. Return structured result
"""

import logging
from datetime import datetime, timezone

import httpx

from app.core.exceptions import RepoGuardError
from app.fetcher.fetcher import RepoFetcher
from app.scanner.scan import PatternMatch, ScanResponse, ScanResult, TrustLevel
from app.scanner.static_scanner import StaticScanner, calculate_trust_score
from app.db.crud import save_scan

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    def __init__(self):
        self.fetcher = RepoFetcher()
        self.static = StaticScanner()

    async def scan(self, url: str) -> ScanResponse:
        try:
            logger.info(f"Fetching repo: {url}")
            repo_data = await self.fetcher.fetch_repo(url)

            logger.info(f"Scanning {len(repo_data['files'])} files")
            matches = self.static.scan_files(repo_data["files"])
            matches.extend(self._account_signals(repo_data))

            score = calculate_trust_score(matches)
            trust_level = self._score_to_level(score)

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

            # Persist to DB (non-blocking failure)
            await save_scan(result)

            return ScanResponse(success=True, result=result)

        except RepoGuardError as e:
            # Fetch/scan failures carry a message meant for the user — pass it
            # through verbatim rather than burying it under "Scan failed:".
            logger.warning(f"Scan aborted for {url}: {e}")
            return ScanResponse(success=False, error=str(e))

        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            return ScanResponse(success=False, error=str(e))

        except httpx.RequestError as e:
            logger.warning(f"Network error for {url}: {e}")
            return ScanResponse(
                success=False,
                error="Could not reach GitHub/Hugging Face. Check your connection and try again.",
            )

        except Exception as e:
            logger.exception(f"Scan failed for {url}")
            return ScanResponse(success=False, error=f"Scan failed: {str(e)}")

    def _account_signals(self, repo_data: dict) -> list[PatternMatch]:
        signals: list[PatternMatch] = []
        info = repo_data["account_info"]

        if info.is_new_account:
            signals.append(PatternMatch(
                category="account", pattern_name="new_account",
                description=f"Account '{info.username}' is only {info.account_age_days} days old",
                file_path="[account metadata]", severity=80,
            ))

        if info.is_typosquat and info.typosquat_target:
            signals.append(PatternMatch(
                category="account", pattern_name="typosquat",
                description=f"Username '{info.username}' resembles '{info.typosquat_target}'",
                file_path="[account metadata]", severity=85,
            ))

        if info.total_repos is not None and info.total_repos <= 2 and info.is_new_account:
            signals.append(PatternMatch(
                category="account", pattern_name="sparse_account",
                description=f"Account has only {info.total_repos} repositories",
                file_path="[account metadata]", severity=50,
            ))

        return signals

    def _score_to_level(self, score: int) -> TrustLevel:
        if score >= 70:
            return TrustLevel.SAFE
        if score >= 40:
            return TrustLevel.SUSPICIOUS
        return TrustLevel.DANGEROUS

    def _build_summary(self, matches, score, trust_level, repo_data) -> str:
        repo = repo_data["repo_name"]
        if not matches:
            return f"No malicious patterns detected in {repo}."

        # Must match the UI's severity chip threshold in App.jsx (sevLabel),
        # or the summary says "Critical findings" next to a "HIGH" badge.
        critical = [m for m in matches if m.severity >= 90]
        parts = [f"RepoGuard detected {len(matches)} suspicious signal(s)."]

        if trust_level == TrustLevel.DANGEROUS:
            parts.append("This repository appears dangerous.")
        elif trust_level == TrustLevel.SUSPICIOUS:
            parts.append("This repository should be reviewed carefully.")

        if critical:
            names = ", ".join(sorted({m.pattern_name for m in critical}))
            parts.append(f"Critical findings: {names}.")

        if repo_data["account_info"].is_new_account:
            parts.append("The uploading account is very new.")
        if repo_data["account_info"].is_typosquat:
            parts.append("Possible account impersonation detected.")

        return " ".join(parts)

    def _build_recommendations(self, matches, trust_level) -> list[str]:
        recs: list[str] = []

        if trust_level == TrustLevel.DANGEROUS:
            recs.append("Do not clone or execute this repository.")
            recs.append("Treat any executed files as potentially malicious.")
        elif trust_level == TrustLevel.SUSPICIOUS:
            recs.append("Review all scripts manually before running.")
            recs.append("Consider using an isolated container or VM.")

        categories = {m.category for m in matches}
        if "network" in categories:
            recs.append("Monitor outbound network connections.")
        if "system_exec" in categories:
            recs.append("Review subprocess and shell execution carefully.")
        if "obfuscation" in categories:
            recs.append("Review all encoded or obfuscated content.")
        if "model_exploit" in categories:
            recs.append("Avoid unsafe pickle-based model loading.")

        return recs or ["No major threats detected."]