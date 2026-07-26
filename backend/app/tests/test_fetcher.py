"""
Fetcher error handling.

The rule these tests protect: RepoGuard must never return a result for a repo
it could not actually read. An unreadable repo scores 100/safe otherwise,
which is worse than no answer at all.
"""

import httpx
import pytest

from app.core.exceptions import FetchError
from app.fetcher.fetcher import RepoFetcher


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── URL parsing ───────────────────────────────────────────────────────────────

def test_parse_url_rejects_other_hosts():
    with pytest.raises(ValueError):
        RepoFetcher().parse_url("https://gitlab.com/owner/repo")


# ── GitHub ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_github_404_raises_not_found():
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="not found on GitHub"):
            await RepoFetcher()._fetch_github(client, {"owner": "psf", "repo": "nope"})


@pytest.mark.asyncio
async def test_github_rate_limit_names_the_token_fix():
    def handler(request):
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={})

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="GITHUB_TOKEN"):
            await RepoFetcher()._fetch_github(client, {"owner": "psf", "repo": "requests"})


@pytest.mark.asyncio
async def test_github_private_repo_is_distinct_from_rate_limit():
    def handler(request):
        return httpx.Response(403, headers={"x-ratelimit-remaining": "4999"}, json={})

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="private"):
            await RepoFetcher()._fetch_github(client, {"owner": "acme", "repo": "secret"})


@pytest.mark.asyncio
async def test_github_repo_with_no_readable_files_is_not_scored_safe():
    """Metadata resolves but every download fails — must raise, not return {}."""
    def handler(request):
        if "api.github.com/repos" in str(request.url) and "/git/trees/" in str(request.url):
            return httpx.Response(200, json={"tree": [{"path": "model.safetensors", "type": "blob"}]})
        if "api.github.com/repos" in str(request.url):
            return httpx.Response(200, json={"stargazers_count": 5})
        return httpx.Response(404)

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="could not read"):
            await RepoFetcher()._fetch_github(client, {"owner": "acme", "repo": "weights"})


@pytest.mark.asyncio
async def test_github_happy_path_returns_files():
    def handler(request):
        url = str(request.url)
        if "/git/trees/" in url:
            return httpx.Response(200, json={"tree": [{"path": "setup.py", "type": "blob"}]})
        if "raw.githubusercontent.com" in url:
            return httpx.Response(200, text="import os\n")
        if "/users/" in url:
            return httpx.Response(200, json={"created_at": "2015-01-01T00:00:00Z", "public_repos": 40})
        return httpx.Response(200, json={"stargazers_count": 100, "watchers_count": 100})

    async with _client(handler) as client:
        data = await RepoFetcher()._fetch_github(client, {"owner": "psf", "repo": "requests"})

    assert data["files"] == {"setup.py": "import os\n"}
    assert data["repo_name"] == "psf/requests"
    assert data["account_info"].is_new_account is False


# ── Hugging Face ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hf_unreadable_repo_raises_after_trying_all_types():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(401, json={"error": "Unauthorized"})

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="private/gated"):
            await RepoFetcher()._fetch_hf(client, {"owner": "fake", "repo": "model"})

    # 401 is inconclusive on HF, so all three repo types must be attempted.
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_hf_falls_through_to_dataset():
    def handler(request):
        url = str(request.url)
        if "/api/models/" in url:
            return httpx.Response(404)
        if "/api/datasets/" in url:
            return httpx.Response(200, json={"siblings": [{"rfilename": "load.py"}], "downloads": 7})
        if "/resolve/main/load.py" in url:
            return httpx.Response(200, text="print('hi')\n")
        if "/overview" in url:
            return httpx.Response(200, json={"createdAt": "2020-01-01T00:00:00.000Z"})
        return httpx.Response(404)

    async with _client(handler) as client:
        data = await RepoFetcher()._fetch_hf(client, {"owner": "org", "repo": "ds"})

    assert "load.py" in data["files"]
    assert data["downloads"] == 7


@pytest.mark.asyncio
async def test_hf_rate_limit_surfaces_immediately():
    def handler(request):
        return httpx.Response(429, json={})

    async with _client(handler) as client:
        with pytest.raises(FetchError, match="rate limit"):
            await RepoFetcher()._fetch_hf(client, {"owner": "org", "repo": "m"})


# ── Typosquat detection ───────────────────────────────────────────────────────

@pytest.mark.parametrize("username,expected", [
    ("openai", None),          # exact match on a trusted org — never a squat
    ("open-ai", None),         # separators are normalised away
    ("0penai", "openai"),      # digit substitution
    ("googIe", "google"),      # capital-I for lowercase-l
    ("randomuser", None),
])
def test_typosquat_detection(username, expected):
    is_typo, target = RepoFetcher()._check_typosquat(username)
    assert target == expected
    assert is_typo is (expected is not None)
