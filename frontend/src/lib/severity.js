/*
 * Severity and trust-level vocabulary.
 *
 * Status colour never carries meaning on its own — every consumer of these
 * helpers renders the `label` (and a glyph) alongside the colour.
 *
 * The `critical` cut at 90 matches the backend's own threshold in
 * orchestrator._build_summary; if one moves, move the other.
 */

export const SEVERITY_TIERS = [
  { id: "critical", label: "Critical", glyph: "▲", min: 90 },
  { id: "high", label: "High", glyph: "▲", min: 75 },
  { id: "medium", label: "Medium", glyph: "■", min: 55 },
  { id: "low", label: "Low", glyph: "●", min: 0 },
];

export function severityTier(severity) {
  return SEVERITY_TIERS.find((t) => severity >= t.min) ?? SEVERITY_TIERS.at(-1);
}

export const TRUST_LEVELS = {
  safe: { label: "Safe", glyph: "✓", status: "good" },
  suspicious: { label: "Suspicious", glyph: "!", status: "warning" },
  dangerous: { label: "Dangerous", glyph: "✕", status: "critical" },
};

export function trustLevel(level) {
  return TRUST_LEVELS[level] ?? TRUST_LEVELS.suspicious;
}

/** Human label for a backend match category. */
const CATEGORY_LABELS = {
  obfuscation: "Obfuscation",
  network: "Network",
  system_exec: "System execution",
  file_behaviour: "File behaviour",
  evasion: "Evasion",
  model_exploit: "Model exploit",
  hf_exploit: "Hugging Face",
  supply_chain: "Supply chain",
  account: "Account",
};

export const categoryLabel = (c) =>
  CATEGORY_LABELS[c] ?? c.replace(/_/g, " ");

export function formatTimeAgo(iso) {
  if (!iso) return "";
  // SQLite stores naive timestamps; force UTC so "just now" isn't hours off.
  const stamp = !iso.endsWith("Z") && !iso.includes("+") ? `${iso}Z` : iso;
  const diff = Date.now() - new Date(stamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days < 30 ? `${days}d ago` : `${Math.floor(days / 30)}mo ago`;
}
