import { severityTier, trustLevel, categoryLabel } from "./severity.js";

/** A scan result as Markdown — meant to be pasted into a PR or a ticket. */
export function toMarkdown(r) {
  const level = trustLevel(r.trust_level);
  const lines = [
    `## RepoGuard scan — \`${r.repo_name}\``,
    "",
    `**${level.label}** · trust score **${r.trust_score}/100** · ${r.files_scanned} files scanned`,
    "",
    r.summary,
    "",
  ];

  if (r.matches.length) {
    lines.push(`### Findings (${r.matches.length})`, "");
    lines.push("| Severity | Pattern | Location | Detail |");
    lines.push("| --- | --- | --- | --- |");
    for (const m of [...r.matches].sort((a, b) => b.severity - a.severity)) {
      const where = m.line_number ? `${m.file_path}:${m.line_number}` : m.file_path;
      lines.push(
        `| ${severityTier(m.severity).label} (${m.severity}) | \`${m.pattern_name}\` | \`${where}\` | ${m.description} |`
      );
    }
    lines.push("");
  } else {
    lines.push("No malicious patterns detected.", "");
  }

  if (r.recommendations?.length) {
    lines.push("### Recommendations", "");
    for (const rec of r.recommendations) lines.push(`- ${rec}`);
    lines.push("");
  }

  const a = r.account_info;
  lines.push(
    "### Account",
    "",
    `- Username: \`${a.username}\``,
    `- Age: ${a.account_age_days != null ? `${a.account_age_days} days` : "unknown"}`,
    `- Repositories: ${a.total_repos ?? "unknown"}`
  );
  if (a.is_typosquat) lines.push(`- ⚠ Resembles \`${a.typosquat_target}\``);
  if (a.is_new_account) lines.push("- ⚠ New account");

  lines.push("", `_Scanned ${new Date(r.scanned_at).toLocaleString()} · ${r.url}_`);
  return lines.join("\n");
}

export const toJson = (r) => JSON.stringify(r, null, 2);

export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  // Fallback for non-secure contexts, where the async API is unavailable.
  const el = document.createElement("textarea");
  el.value = text;
  el.setAttribute("readonly", "");
  el.style.position = "fixed";
  el.style.opacity = "0";
  document.body.appendChild(el);
  el.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(el);
  return ok;
}

export { categoryLabel };
