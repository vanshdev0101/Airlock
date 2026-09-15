"""Claude-powered model card / README analysis.

Static regex/AST scanning catches code-shaped threats. It cannot catch a
README that talks a human into running something unsafe (fake urgency, "just
disable your antivirus for this step", a link dressed up as an official
patch). That's a language-understanding problem, so it goes to Claude instead
of another regex.

Retrieval-augmented: before asking the model to judge, we pull the k most
similar known-bad snippets from a local vector store (see ``.retrieval``) and
hand them over as grounding examples, rather than asking Claude to freelance.
Orchestrated as a two-node LangGraph (retrieve -> generate).

Advisory only: never malware_grade, never short-circuits the trust score by
itself (see calculate_trust_score's _INSTANT_THRESHOLD gate) — a model
mistake here should nudge the score, not nuke it.
"""

import logging
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from ..config import get_settings
from .retrieval import retrieve_similar_patterns
from .scan import PatternMatch

logger = logging.getLogger(__name__)
settings = get_settings()

_README_KEYS = ["README.md", "readme.md", "MODEL_CARD.md"]
_MAX_CHARS = 12_000  # keeps cost/latency bounded; cards are rarely longer
_TIMEOUT_SECONDS = 20


class _Finding(BaseModel):
    pattern_name: str = Field(description="short_snake_case_slug for this finding")
    description: str
    severity: int = Field(ge=0, le=100)


class _Report(BaseModel):
    """Suspicious patterns found in a model card / README."""

    findings: list[_Finding]


_SYSTEM = """You are a security reviewer reading a Hugging Face / GitHub \
model card or README before a user clones the repo. Flag only content a \
static regex scanner would miss: social engineering ("disable your \
antivirus first"), fake urgency or authority claims, instructions to run \
a script/curl-pipe-to-shell from an unofficial source, claims that don't \
match what the repo actually is, or a README that reads as bait for a \
scam/typosquat rather than documentation. Do not flag ordinary install \
instructions, license text, or legitimate warnings. Known patterns are \
provided below for reference, but rely on your own judgment — not every \
README that resembles one is actually malicious. If nothing is suspicious, \
report zero findings."""


class _State(TypedDict):
    repo_name: str
    text: str
    examples: list[dict]
    report: _Report | None


def _retrieve_node(state: _State) -> dict:
    return {"examples": retrieve_similar_patterns(state["text"])}


async def _generate_node(state: _State) -> dict:
    model = ChatAnthropic(
        model="claude-haiku-4-5",
        api_key=settings.anthropic_api_key,
        timeout=_TIMEOUT_SECONDS,
        max_tokens=2048,
    )
    structured_model = model.with_structured_output(_Report)

    examples_block = "\n".join(
        f"- {e['pattern_name']}: {e['text']}" for e in state["examples"]
    ) or "none"
    user_message = (
        f"Known patterns retrieved for reference:\n{examples_block}\n\n"
        f"Model card for {state['repo_name']}:\n\n{state['text']}"
    )

    report = await structured_model.ainvoke(
        [("system", _SYSTEM), ("user", user_message)]
    )
    return {"report": report}


_graph = StateGraph(_State)
_graph.add_node("retrieve", _retrieve_node)
_graph.add_node("generate", _generate_node)
_graph.set_entry_point("retrieve")
_graph.add_edge("retrieve", "generate")
_graph.add_edge("generate", END)
_app = _graph.compile()


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

    try:
        result = await _app.ainvoke(
            {"repo_name": repo_name, "text": text, "examples": [], "report": None}
        )
    except Exception as e:
        logger.warning(f"AI model card analysis skipped for {repo_name}: {e}")
        return []

    report = result["report"]
    if report is None:
        return []

    matches = []
    for finding in report.findings:
        matches.append(PatternMatch(
            category="ai_analysis",
            pattern_name=finding.pattern_name,
            description=finding.description,
            file_path="README.md",
            severity=max(0, min(100, finding.severity)),
            malware_grade=False,
        ))
    return matches
