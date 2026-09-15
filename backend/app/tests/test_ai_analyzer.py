"""Tests for the Claude-powered model card analyzer."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scanner.ai_analyzer import _Finding, _Report, analyze_model_card


def _settings(api_key):
    from types import SimpleNamespace
    return SimpleNamespace(anthropic_api_key=api_key)


def _mock_structured_model(report):
    structured = AsyncMock()
    structured.ainvoke = AsyncMock(return_value=report)
    model = AsyncMock()
    model.with_structured_output = lambda *_a, **_kw: structured
    return model


@pytest.mark.asyncio
async def test_skips_when_no_api_key():
    with patch("app.scanner.ai_analyzer.settings", _settings(None)):
        assert await analyze_model_card("owner/repo", {"README.md": "hello"}) == []


@pytest.mark.asyncio
async def test_skips_when_no_readme():
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")):
        assert await analyze_model_card("owner/repo", {}) == []


@pytest.mark.asyncio
async def test_parses_findings_from_structured_output():
    report = _Report(findings=[
        _Finding(pattern_name="fake_antivirus_warning", description="Tells the user to disable Defender.", severity=85),
    ])
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")), \
         patch("app.scanner.ai_analyzer.retrieve_similar_patterns", return_value=[]), \
         patch("app.scanner.ai_analyzer.ChatAnthropic", return_value=_mock_structured_model(report)):

        matches = await analyze_model_card("owner/repo", {"README.md": "disable your antivirus first"})

    assert len(matches) == 1
    assert matches[0].category == "ai_analysis"
    assert matches[0].pattern_name == "fake_antivirus_warning"
    assert matches[0].severity == 85
    assert matches[0].malware_grade is False


@pytest.mark.asyncio
async def test_api_error_yields_no_matches():
    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")), \
         patch("app.scanner.ai_analyzer.retrieve_similar_patterns", return_value=[]), \
         patch("app.scanner.ai_analyzer.ChatAnthropic", side_effect=RuntimeError("boom")):

        matches = await analyze_model_card("owner/repo", {"README.md": "some text"})

    assert matches == []


@pytest.mark.asyncio
async def test_retrieved_examples_are_passed_to_the_model():
    report = _Report(findings=[])
    examples = [{"pattern_name": "curl_pipe_to_shell", "text": "curl | bash", "description": "..."}]
    mock_model = _mock_structured_model(report)

    with patch("app.scanner.ai_analyzer.settings", _settings("sk-test")), \
         patch("app.scanner.ai_analyzer.retrieve_similar_patterns", return_value=examples) as mock_retrieve, \
         patch("app.scanner.ai_analyzer.ChatAnthropic", return_value=mock_model):

        matches = await analyze_model_card("owner/repo", {"README.md": "curl | bash to install"})

    mock_retrieve.assert_called_once()
    structured = mock_model.with_structured_output()
    call_messages = structured.ainvoke.call_args[0][0]
    user_message = call_messages[1][1]
    assert "curl_pipe_to_shell" in user_message
    assert matches == []
