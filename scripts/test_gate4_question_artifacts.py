"""Offline positive and tamper tests for Gate 4 pre-call content artifacts."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import (  # noqa: E402
    load_foundation_config,
    verify_gate4_foundation,
)
from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_direct_input_contract,
    verify_production_question_artifacts,
    verify_question_and_reference_contract,
)


def expect_rejection(action: Callable[[], object]) -> None:
    try:
        action()
    except (AssertionError, ValueError):
        return
    except Exception as exc:
        if exc.__class__.__module__.startswith("jsonschema"):
            return
        raise
    raise AssertionError("Expected the tampered Gate 4 artifact to be rejected")


def main() -> None:
    report = verify_production_question_artifacts()
    assert report["status"] == "PASS"
    assert report["question_count"] == 40
    assert report["minimum_non_summary_coverage"] >= 2
    assert report["clean_regeneration_byte_identical"] is True
    assert report["model_calls_made"] == 0

    verify_gate4_foundation()
    paths = load_foundation_config()["gate4_paths"]
    questions = json.loads((REPOSITORY_ROOT / paths["questions"]).read_text(encoding="utf-8"))
    references = json.loads((REPOSITORY_ROOT / paths["reference_answers"]).read_text(encoding="utf-8"))
    direct_input = json.loads((REPOSITORY_ROOT / paths["direct_input"]).read_text(encoding="utf-8"))
    records = json.loads((REPOSITORY_ROOT / paths["change_records"]).read_text(encoding="utf-8"))["changes"]

    duplicate_id = copy.deepcopy(questions)
    duplicate_id["questions"][1]["question_id"] = duplicate_id["questions"][0]["question_id"]
    expect_rejection(lambda: verify_question_and_reference_contract(duplicate_id, references, records))

    development_repeat = copy.deepcopy(questions)
    development_repeat["questions"][0]["question"] = "Summarize all verified changes between the two controlled IFC versions."
    expect_rejection(lambda: verify_question_and_reference_contract(development_repeat, references, records))

    answer_leak = copy.deepcopy(direct_input)
    answer_leak["scope"]["included"].append(references["answers"][0]["answer"])
    expect_rejection(lambda: verify_direct_input_contract(answer_leak, references, records))

    change_key_leak = copy.deepcopy(direct_input)
    change_key_leak["versions"][0]["change_type"] = "added"
    expect_rejection(lambda: verify_direct_input_contract(change_key_leak, references, records))

    report.update(
        {
            "duplicate_question_id_rejected": True,
            "development_question_repeat_rejected": True,
            "reference_answer_leak_rejected": True,
            "precomputed_change_key_rejected": True,
        }
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
