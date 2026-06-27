import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validate_spec import validate_spec


def test_valid_spec_passes():
    with open(os.path.join(os.path.dirname(__file__), "sample_data", "sample_spec.json")) as f:
        spec = json.load(f)
    errors = validate_spec(spec)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_missing_title_fails():
    spec = {"summary": "x", "acceptance_criteria": [{"id": "AC-1", "description": "x", "verification": "test"}]}
    errors = validate_spec(spec)
    assert any("title" in e for e in errors), f"Expected title error, got: {errors}"


def test_empty_acceptance_criteria_fails():
    spec = {
        "title": "Test",
        "summary": "Test",
        "acceptance_criteria": [],
        "likely_files": [],
        "implementation_plan": ["do something"],
        "test_plan": ["test something"],
        "risks": [],
    }
    errors = validate_spec(spec)
    assert any("acceptance_criteria" in e for e in errors)


def test_missing_verification_method_fails():
    spec = {
        "title": "Test",
        "summary": "Test",
        "acceptance_criteria": [{"id": "AC-1", "description": "x"}],
        "likely_files": [],
        "implementation_plan": ["do something"],
        "test_plan": ["test something"],
        "risks": [],
    }
    errors = validate_spec(spec)
    assert any("verification" in e for e in errors)
