import asyncio
import logging
from datetime import datetime, timezone

import httpx

from ..config import get_settings
from ..scanner.scan import AccountInfo

logger = logging.getLogger(__name__)
settings = get_settings()

SCANNABLE_EXTENSIONS = {
    ".py", ".sh", ".bat", ".ps1", ".js", ".ts",
    ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".json",
}

MAX_FILE_BYTES = settings.max_file_size_kb * 1024
_SEMAPHORE = asyncio.Semaphore(10)


class RepoFetcher:

    def __init__(self):
        self.hf_base = "https://huggingface.co/api"
        self.gh_base = "https://api.github.com"
        self.gh_headers = {}
        if settings.github_token:
            self.gh_headers["Authorization"] = f"Bearer {settings.github_token}"

    def parse_url(self, url: str) -> dict:
        url = url.rstrip("/")
        if "huggingface.co" in url:
            parts = url.split("huggingface.co/")[-1].split("/")
            return {"platform": "huggingface", "owner": parts[0],
                    "repo": parts[1] if len(parts) > 1 else ""}
        if "github.com" in url:
            parts = url.split("github.com/")[-1].split("/")
            return {"platform": "github", "owner": parts[0],
                    "repo": parts[1] if len(parts) > 1 else ""}
        raise ValueError(f"Unsupported URL: {url}")

    async def fetch_repo(self, url: str) -> dict:
        info = self.parse_url(url)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            if info["platform"] == "huggingface":
                return await self._fetch_hf(client, info)
            return await self._fetch_github(client, info)

    async def _fetch_hf(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner, repo = info["owner"], info["repo"]
        repo_id = f"{owner}/{repo}"

        # Try model → dataset → space in order
        meta = {}
        repo_type = "models"
        for rtype in ("models", "datasets", "spaces"):
            resp = await client.get(f"{self.hf_base}/{rtype}/{repo_id}")
            if resp.status_code == 200:
                meta = resp.json()
                repo_type = rtype
                break

        # Get file list — siblings key works for all repo types
        files_resp = await client.get(
            f"{self.hf_base}/{repo_type}/{repo_id}",
            params={"blobs": True}
        )
        file_list = []
        if files_resp.status_code == 200:
            file_list = [s["rfilename"] for s in files_resp.json().get("siblings", [])]

        scannable = [f for f in file_list if self._ext(f) in SCANNABLE_EXTENSIONS][:settings.max_files_per_scan]

        # Always try README
        for readme in ["README.md", "readme.md", "MODEL_CARD.md"]:
            if readme not in scannable:
                scannable.append(readme)

        files_content = await self._download_many(
            client,
            {f: f"https://huggingface.co/{repo_id}/resolve/main/{f}" for f in scannable}
        )

        author_info = await self._fetch_hf_author(client, owner)
        return {
            "repo_name": repo_id, "platform": "huggingface",
            "account_info": self._build_account_info(owner, author_info),
            "files": files_content, "raw_metadata": meta,
            "downloads": meta.get("downloads", 0), "likes": meta.get("likes", 0),
        }

    async def _fetch_hf_author(self, client, owner):
        resp = await client.get(f"{self.hf_base}/users/{owner}/overview")
        return resp.json() if resp.status_code == 200 else {}

    async def _fetch_github(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner, repo = info["owner"], info["repo"]

        meta_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}", headers=self.gh_headers)
        meta = meta_resp.json() if meta_resp.status_code == 200 else {}

        tree_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}/git/trees/HEAD",
            params={"recursive": "1"}, headers=self.gh_headers)
        file_list = []
        if tree_resp.status_code == 200:
            file_list = [i["path"] for i in tree_resp.json().get("tree", []) if i["type"] == "blob"]

        scannable = [f for f in file_list if self._ext(f) in SCANNABLE_EXTENSIONS][:settings.max_files_per_scan]
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD"
        files_content = await self._download_many(client, {f: f"{base}/{f}" for f in scannable})

        user_resp = await client.get(f"{self.gh_base}/users/{owner}", headers=self.gh_headers)
        user_data = user_resp.json() if user_resp.status_code == 200 else {}

        return {
            "repo_name": f"{owner}/{repo}", "platform": "github",
            "account_info": self._build_account_info(owner, user_data, platform="github"),
            "files": files_content, "raw_metadata": meta,
            "downloads": meta.get("stargazers_count", 0),
            "likes": meta.get("watchers_count", 0),
        }

    async def _download_many(self, client, url_map: dict[str, str]) -> dict[str, str]:
        async def fetch_one(filename, url):
            async with _SEMAPHORE:
                return filename, await self._download_text(client, url)

        results = await asyncio.gather(
            *[fetch_one(f, u) for f, u in url_map.items()],
            return_exceptions=True
        )
        return {
            fname: content
            for r in results
            if not isinstance(r, Exception)
            for fname, content in [r]
            if content is not None
        }

    async def _download_text(self, client, url) -> str | None:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            if len(resp.content) > MAX_FILE_BYTES:
                return None
            return resp.text
        except Exception as e:
            logger.warning(f"Failed: {url}: {e}")
            return None

    def _build_account_info(self, username, data, platform="huggingface") -> AccountInfo:
        created_str = data.get("createdAt") or data.get("created_at", "")
        account_age_days = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                account_age_days = (datetime.now(timezone.utc) - created).days
            except Exception:
                pass
        total_repos = data.get("numModels") or data.get("public_repos") or data.get("numRepos") or 0
        is_new = account_age_days is not None and account_age_days < 30
        is_typo, typo_target = self._check_typosquat(username)
        return AccountInfo(
            username=username, account_age_days=account_age_days, total_repos=total_repos,
            is_new_account=is_new, is_typosquat=is_typo, typosquat_target=typo_target,
        )

    def _check_typosquat(self, username):
        clean = username.lower().replace("-", "").replace("_", "")
        for trusted in settings.trusted_orgs:
            t = trusted.lower().replace("-", "").replace("_", "")
            if clean == t:
                return False, None
            dist = _levenshtein(clean, t)
            if dist <= 2 and abs(len(clean) - len(t)) <= 3 and dist > 0:
                return True, trusted
        return False, None

    def _ext(self, path):
        return ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""


def _levenshtein(a, b):
    if len(a) < len(b): return _levenshtein(b, a)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(ca != cb)))
        prev = curr
    return prev[-1]