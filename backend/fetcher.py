import httpx
import logging
from datetime import datetime, timezone
from config import get_settings
from scan import AccountInfo

logger = logging.getLogger(__name__)
settings = get_settings()

# File types we actually scan (skip model weights, images, etc.)
SCANNABLE_EXTENSIONS = {
    ".py", ".sh", ".bat", ".ps1", ".js", ".ts",
    ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".json",
}

MAX_FILE_BYTES = settings.max_file_size_kb * 1024


class RepoFetcher:
    """Handles both Hugging Face and GitHub URLs."""

    def __init__(self):
        self.hf_base = "https://huggingface.co/api"
        self.gh_base = "https://api.github.com"
        self.headers = {}
        if settings.github_token:
            self.headers["Authorization"] = f"Bearer {settings.github_token}"

    def parse_url(self, url: str) -> dict:
        """Returns {platform, owner, repo_name}"""
        url = url.rstrip("/")

        if "huggingface.co" in url:
            # https://huggingface.co/owner/repo
            parts = url.split("huggingface.co/")[-1].split("/")
            return {
                "platform": "huggingface",
                "owner": parts[0],
                "repo": parts[1] if len(parts) > 1 else "",
            }

        if "github.com" in url:
            # https://github.com/owner/repo
            parts = url.split("github.com/")[-1].split("/")
            return {
                "platform": "github",
                "owner": parts[0],
                "repo": parts[1] if len(parts) > 1 else "",
            }

        raise ValueError(f"Unsupported URL: {url}. Must be Hugging Face or GitHub.")

    async def fetch_repo(self, url: str) -> dict:
        """
        Main entry point.
        Returns {
            repo_name, platform, account_info,
            files: {path: content}, raw_metadata
        }
        """
        info = self.parse_url(url)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            if info["platform"] == "huggingface":
                return await self._fetch_hf(client, info)
            else:
                return await self._fetch_github(client, info)

    # ── Hugging Face ──────────────────────────────────────────────────────────

    async def _fetch_hf(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner = info["owner"]
        repo = info["repo"]
        repo_id = f"{owner}/{repo}"

        # 1. Repo metadata
        meta_resp = await client.get(f"{self.hf_base}/models/{repo_id}")
        if meta_resp.status_code == 404:
            meta_resp = await client.get(f"{self.hf_base}/spaces/{repo_id}")
        meta = meta_resp.json() if meta_resp.status_code == 200 else {}

        # 2. File list
        files_resp = await client.get(
            f"{self.hf_base}/models/{repo_id}",
            params={"blobs": True},
        )
        file_list = []
        if files_resp.status_code == 200:
            siblings = files_resp.json().get("siblings", [])
            file_list = [s["rfilename"] for s in siblings]

        # 3. Download scannable files
        files_content: dict[str, str] = {}
        count = 0
        for filename in file_list:
            if count >= settings.max_files_per_repo:
                break
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in SCANNABLE_EXTENSIONS:
                continue
            raw_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
            content = await self._download_text(client, raw_url)
            if content:
                files_content[filename] = content
                count += 1

        # 4. Always grab the README / model card
        for readme in ["README.md", "readme.md", "MODEL_CARD.md"]:
            if readme not in files_content:
                raw_url = f"https://huggingface.co/{repo_id}/resolve/main/{readme}"
                content = await self._download_text(client, raw_url)
                if content:
                    files_content[readme] = content

        # 5. Account info
        author_info = await self._fetch_hf_author(client, owner)
        account_info = self._build_account_info(owner, author_info)

        return {
            "repo_name": repo_id,
            "platform": "huggingface",
            "account_info": account_info,
            "files": files_content,
            "raw_metadata": meta,
            "downloads": meta.get("downloads", 0),
            "likes": meta.get("likes", 0),
        }

    async def _fetch_hf_author(self, client: httpx.AsyncClient, owner: str) -> dict:
        resp = await client.get(f"{self.hf_base}/users/{owner}/overview")
        if resp.status_code == 200:
            return resp.json()
        return {}

    # ── GitHub ────────────────────────────────────────────────────────────────

    async def _fetch_github(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner = info["owner"]
        repo = info["repo"]

        # 1. Repo metadata
        meta_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}",
            headers=self.headers,
        )
        meta = meta_resp.json() if meta_resp.status_code == 200 else {}

        # 2. File tree
        tree_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}/git/trees/HEAD",
            params={"recursive": "1"},
            headers=self.headers,
        )
        file_list = []
        if tree_resp.status_code == 200:
            file_list = [
                item["path"]
                for item in tree_resp.json().get("tree", [])
                if item["type"] == "blob"
            ]

        # 3. Download scannable files
        files_content: dict[str, str] = {}
        count = 0
        for filename in file_list:
            if count >= settings.max_files_per_repo:
                break
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in SCANNABLE_EXTENSIONS:
                continue
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{filename}"
            content = await self._download_text(client, raw_url)
            if content:
                files_content[filename] = content
                count += 1

        # 4. Account info
        user_resp = await client.get(
            f"{self.gh_base}/users/{owner}",
            headers=self.headers,
        )
        user_data = user_resp.json() if user_resp.status_code == 200 else {}
        account_info = self._build_account_info(owner, user_data, platform="github")

        return {
            "repo_name": f"{owner}/{repo}",
            "platform": "github",
            "account_info": account_info,
            "files": files_content,
            "raw_metadata": meta,
            "downloads": meta.get("stargazers_count", 0),
            "likes": meta.get("watchers_count", 0),
        }

    # ── Shared helpers ────────────────────────────────────────────────────────

    async def _download_text(
        self, client: httpx.AsyncClient, url: str
    ) -> str | None:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            if len(resp.content) > MAX_FILE_BYTES:
                logger.info(f"Skipping large file: {url}")
                return None
            return resp.text
        except Exception as e:
            logger.warning(f"Failed to download {url}: {e}")
            return None

    def _build_account_info(
        self, username: str, data: dict, platform: str = "huggingface"
    ) -> AccountInfo:
        # Parse account creation date
        created_str = data.get("createdAt") or data.get("created_at", "")
        account_age_days = None
        if created_str:
            try:
                created = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
                age = datetime.now(timezone.utc) - created
                account_age_days = age.days
            except Exception:
                pass

        total_repos = (
            data.get("numModels")
            or data.get("public_repos")
            or data.get("numRepos")
            or 0
        )

        is_new = account_age_days is not None and account_age_days < 30

        # Typosquatting check — edit distance against trusted orgs
        is_typo, typo_target = self._check_typosquat(username)

        return AccountInfo(
            username=username,
            account_age_days=account_age_days,
            total_repos=total_repos,
            is_new_account=is_new,
            is_typosquat=is_typo,
            typosquat_target=typo_target,
        )

    def _check_typosquat(self, username: str) -> tuple[bool, str | None]:
        """
        Checks if username is a typosquat of a trusted org.
        Uses simple Levenshtein distance.
        """
        username_lower = username.lower().replace("-", "").replace("_", "")

        for trusted in settings.trusted_orgs:
            trusted_clean = trusted.lower().replace("-", "").replace("_", "")
            if username_lower == trusted_clean:
                return False, None  # exact match = legitimate
            dist = _levenshtein(username_lower, trusted_clean)
            # Flag if 1-2 character difference and not much shorter/longer
            length_diff = abs(len(username_lower) - len(trusted_clean))
            if dist <= 2 and length_diff <= 3 and dist > 0:
                return True, trusted

        return False, None


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein edit distance."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]
