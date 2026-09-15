"""
Claude-powered model card / README analysis.

Static regex/AST scanning catches code-shaped threats. It cannot catch a
README that talks a human into running something unsafe (fake urgency, "just
disable your antivirus for this step", a link dressed up as an official
patch). That's a language-understanding problem, so it goes to Claude instead
of another regex.

Advisory only: never malware_grade, never short-circuits the trust score by
itself (see calculate_trust_score's _INSTANT_THRESHOLD gate) — a model
mistake here should nudge the score, not nuke it.
"""

import logging

import anthropic

from ..config import get_settings
from .scan import PatternMatch

logger = logging.getLogger(__name__)
settings = get_settings()

_README_KEYS = ["README.md", "readme.md", "MODEL_CARD.md"]
_MAX_CHARS = 12_000  # keeps cost/latency bounded; cards are rarely longer
_TIMEOUT_SECONDS = 20

_TOOL = {
    "name": "report_findings",
    "description": "Report suspicious patterns found in a model card / README.",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern_name": {
                            "type": "string",
                            "description": "short_snake_case_slug for this finding",
                        },
                        "description": {"type": "string"},
                        "severity": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                        },
                    },
                    "required": ["pattern_name", "description", "severity"],
                },
            },
        },
        "required": ["findings"],
    },
}

_SYSTEM = """You are a security reviewer reading a Hugging Face / GitHub \
model card or README before a user clones the repo. Flag only content a \
static regex scanner would miss: social engineering ("disable your \
antivirus first"), fake urgency or authority claims, instructions to run \
a script/curl-pipe-to-shell from an unofficial source, claims that don't \
match what the repo actually is, or a README that reads as bait for a \
scam/typosquat rather than documentation. Do not flag ordinary install \
instructions, license text, or legitimate warnings. If nothing is \
suspicious, report zero findings. Call report_findings exactly once."""


def _extract_text(files: dict[str, str]) -> str:
    for key in _README_KEYS:
        text = files.get(key)
        if text:
            return text[:_MAX_CHARS]
    return ""


async def analyze_model_card(repo_name: str, files: dict[str, str]) -> list[PatternMatch]:
    if not settings.anthropic_api_key:
        return []

    text = _extract_text(files)
    if not text.strip():
        return []

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.with_options(timeout=_TIMEOUT_SECONDS).messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=_SYSTEM,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "report_findings"},
            messages=[{
                "role": "user",
                "content": f"Model card for {repo_name}:\n\n{text}",
            }],
        )
    except anthropic.APIError as e:
        logger.warning(f"AI model card analysis skipped for {repo_name}: {e}")
        return []

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        return []

    matches = []
    for finding in tool_use.input.get("findings", []):
        try:
            matches.append(PatternMatch(
                category="ai_analysis",
                pattern_name=finding["pattern_name"],
                description=finding["description"],
                file_path="README.md",
                severity=max(0, min(100, int(finding["severity"]))),
                malware_grade=False,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return matches
