"""Tests for the Claude-powered model card analyzer."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anthropic
import pytest

from app.scanner.ai_analyzer import analyze_model_card


def _tool_response(findings):
    block = SimpleNamespace(type="tool_use", input={"findings": findings})
    return SimpleNamespace(content=[block])


def _settings(api_key):
    return SimpleNamespace(anthropic_api_key=api_key)


@pytest.mark.asyncio
async def test_skips_when_no_api_key():
    with patch("app.scanner.ai_analyzer.settings", _settings(None)):
        assert await analyze_model_card("owner/repo", {"README.md": "hello"}) == []


@pytest.mark.asyncio
async def test_skips_when_no_readme():
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")):
        assert await analyze_model_card("owner/repo", {}) == []


@pytest.mark.asyncio
async def test_parses_findings_from_tool_call():
    response = _tool_response([
        {"pattern_name": "fake_antivirus_warning", "description": "Tells the user to disable Defender.", "severity": 85},
    ])
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")), \
         patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.with_options.return_value.messages.create = AsyncMock(return_value=response)

        matches = await analyze_model_card("owner/repo", {"README.md": "disable your antivirus first"})

    assert len(matches) == 1
    assert matches[0].category == "ai_analysis"
    assert matches[0].pattern_name == "fake_antivirus_warning"
    assert matches[0].severity == 85
    assert matches[0].malware_grade is False


@pytest.mark.asyncio
async def test_api_error_yields_no_matches():
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")), \
         patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.with_options.return_value.messages.create = AsyncMock(
            side_effect=anthropic.APIConnectionError(request=SimpleNamespace())
        )

        matches = await analyze_model_card("owner/repo", {"README.md": "some text"})

    assert matches == []
