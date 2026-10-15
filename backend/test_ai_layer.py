import os
import sys
import json
import pytest
from unittest.mock import MagicMock

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from main import assess_threat, generate_rule_based_assessment


def test_assess_threat_llm_success():
    """Mocked Groq client returns valid JSON threat assessment."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "threat_level": "CRITICAL",
        "score": 95,
        "reasoning": "Drone detected on unauthorized high-speed vector toward primary command post.",
        "recommended_action": "Engage perimeter electronic countermeasures immediately."
    })
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    result = assess_threat(
        trigger_class="drone",
        speed=60.0,
        direction="NE",
        combined_context="[ID: INT-001] Suspected drone activity near north gate.",
        retrieved_reports=[{"id": "INT-001"}],
        client=mock_client
    )

    assert result["threat_level"] == "CRITICAL"
    assert result["score"] == 95
    assert result["assessment_source"] == "llm"
    assert "perimeter electronic countermeasures" in result["recommended_action"]


def test_assess_threat_groq_404_fallback():
    """When Groq returns 404 Model Not Found, falls back to rule-based engine."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Error code: 404 - model_not_found")

    result = assess_threat(
        trigger_class="drone",
        speed=80.0,
        direction="E",
        combined_context="[ID: INT-002] Recon observed.",
        retrieved_reports=[{"id": "INT-002"}],
        client=mock_client
    )

    assert result["assessment_source"] == "rule-based"
    assert result["threat_level"] in ("HIGH", "CRITICAL")
    assert result["threat_level"] != "UNKNOWN"
    assert result["score"] > 0
    assert result["reasoning"].startswith("[Rule-based]")
    assert "LLM processing failed" not in result["reasoning"]


def test_assess_threat_groq_timeout_fallback():
    """When Groq times out, falls back to rule-based engine."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out after 10.0s")

    result = assess_threat(
        trigger_class="vehicle",
        speed=90.0,
        direction="SW",
        combined_context="[ID: INT-003] Armed convoy spotted.",
        retrieved_reports=[{"id": "INT-003"}],
        client=mock_client
    )

    assert result["assessment_source"] == "rule-based"
    assert result["threat_level"] == "HIGH"
    assert result["score"] >= 80
    assert result["reasoning"].startswith("[Rule-based]")
    assert "LLM processing failed" not in result["reasoning"]


def test_assess_threat_groq_none_fallback():
    """When Groq client is None, rule-based engine handles assessment directly."""
    result = assess_threat(
        trigger_class="person",
        speed=5.0,
        direction="N",
        combined_context="",
        retrieved_reports=[],
        client=None
    )

    assert result["assessment_source"] == "rule-based"
    assert result["threat_level"] == "LOW"
    assert result["score"] == 20
    assert result["reasoning"].startswith("[Rule-based]")


def test_rule_based_heuristics():
    """Verify deterministic rule-based threat levels across object classes and speeds."""
    # Fast drone -> CRITICAL
    res = generate_rule_based_assessment("drone", 65.0, "N", [{"id": "EVD-1"}])
    assert res["threat_level"] == "CRITICAL"
    assert res["score"] >= 90
    assert "EVD-1" in res["reasoning"]

    # Slow drone -> HIGH
    res = generate_rule_based_assessment("drone", 20.0, "N", [])
    assert res["threat_level"] == "HIGH"

    # Fast vehicle -> HIGH
    res = generate_rule_based_assessment("truck", 85.0, "S", [])
    assert res["threat_level"] == "HIGH"
    assert res["score"] == 82

    # Medium vehicle -> MED
    res = generate_rule_based_assessment("vehicle", 40.0, "SE", [])
    assert res["threat_level"] == "MED"
    assert res["score"] == 55

    # Stationary/slow vehicle -> LOW
    res = generate_rule_based_assessment("car", 10.0, "W", [])
    assert res["threat_level"] == "LOW"
    assert res["score"] == 25

    # Running person -> MED
    res = generate_rule_based_assessment("person", 20.0, "E", [])
    assert res["threat_level"] == "MED"
    assert res["score"] == 60

    # Walking person -> LOW
    res = generate_rule_based_assessment("person", 4.0, "E", [])
    assert res["threat_level"] == "LOW"
    assert res["score"] == 20
