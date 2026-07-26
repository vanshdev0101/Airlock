const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

/** Thrown for anything the user should read verbatim. */
export class ScanError extends Error {}

/**
 * The API returns messages written for humans, so they are surfaced as-is.
 * Only the backend's internal catch-all ("Scan failed: <traceback text>")
 * gets reworded here.
 */
function humanise(raw) {
  if (!raw || raw.startsWith("Scan failed:")) {
    return "Something went wrong. Make sure the repo is public and try again.";
  }
  return raw;
}

export async function scanRepo(repoUrl, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${API}/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl }),
      signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ScanError(
      "Could not reach the RepoGuard API. Is the backend running on port 8000?"
    );
  }

  if (res.status === 422) {
    throw new ScanError(
      "That does not look like a repo URL. Example: https://github.com/owner/repo"
    );
  }

  const data = await res.json().catch(() => null);
  if (!data) throw new ScanError("The API returned a response we could not read.");
  if (!data.success) throw new ScanError(humanise(data.error));
  return data.result;
}

export async function fetchHistory({ limit = 20, signal } = {}) {
  const res = await fetch(`${API}/scans?limit=${limit}`, { signal });
  const data = await res.json();
  return data.scans ?? [];
}

/** Client-side guard so obvious mistakes never cost a round trip. */
export function validateUrl(input) {
  const target = input.trim().replace(/\/+$/, "");
  if (!target) return "Enter a repository URL.";
  if (!/^https?:\/\//.test(target)) {
    return "Paste the full link from your browser — it should start with https://";
  }
  if (!/(github\.com|huggingface\.co)/.test(target)) {
    return "Only GitHub and Hugging Face repositories are supported.";
  }
  const parts = target.replace(/^https?:\/\//, "").split("/").filter(Boolean);
  if (parts.length < 3) {
    return "The link needs an owner and a repo name — e.g. github.com/psf/requests";
  }
  return null;
}
