from __future__ import annotations

import json

REQUIRED_KEYS = ["title", "summary", "acceptance_criteria", "likely_files", "implementation_plan", "test_plan"]
VALID_VERIFICATIONS = {"test", "browser", "manual"}


def validate_spec(spec: dict) -> list[str]:
    errors = []

    for key in REQUIRED_KEYS:
        if key not in spec:
            errors.append(f"Missing required key: {key}")

    if "title" in spec and not spec["title"].strip():
        errors.append("title is empty")

    if "summary" in spec and not spec["summary"].strip():
        errors.append("summary is empty")

    acs = spec.get("acceptance_criteria", [])
    if len(acs) < 1:
        errors.append("acceptance_criteria must have at least 1 entry")

    for i, ac in enumerate(acs):
        if "id" not in ac:
            errors.append(f"acceptance_criteria[{i}] missing 'id'")
        if "description" not in ac:
            errors.append(f"acceptance_criteria[{i}] missing 'description'")
        if "verification" not in ac:
            errors.append(f"acceptance_criteria[{i}] missing 'verification' method")
        elif ac["verification"] not in VALID_VERIFICATIONS:
            errors.append(
                f"acceptance_criteria[{i}] invalid verification '{ac['verification']}', "
                f"must be one of {VALID_VERIFICATIONS}"
            )

    plan = spec.get("implementation_plan", [])
    if len(plan) < 1:
        errors.append("implementation_plan must have at least 1 step")

    test_plan = spec.get("test_plan", [])
    if len(test_plan) < 1:
        errors.append("test_plan must have at least 1 entry")

    return errors


def parse_and_validate(text: str) -> tuple[dict | None, list[str]]:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None, ["No JSON object found in LLM output"]
        spec = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]

    errors = validate_spec(spec)
    if errors:
        return None, errors
    return spec, []


if __name__ == "__main__":
    import sys

    with open(sys.argv[1]) as f:
        text = f.read()
    spec, errors = parse_and_validate(text)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("VALIDATION PASSED")
    print(json.dumps(spec, indent=2))
