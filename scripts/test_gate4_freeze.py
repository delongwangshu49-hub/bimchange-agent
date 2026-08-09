"""Positive and negative offline tests for Gate 4 pre-call freeze logic."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_orchestration import (  # noqa: E402
    SCHEDULE_PATH,
    budget_policy,
    foundation_paths,
    load_json,
    stage_frozen_gate3_runtime,
    verify_schedule,
)


def expect_rejection(callback) -> None:
    try:
        callback()
    except (KeyError, TypeError, ValueError):
        return
    raise AssertionError("Invalid Gate 4 freeze artifact was accepted")


def main() -> None:
    paths = foundation_paths()
    questions = load_json(paths["questions"])
    schedule = load_json(SCHEDULE_PATH)
    report = verify_schedule(schedule, questions)

    missing_execution = copy.deepcopy(schedule)
    missing_execution["executions"].pop()
    expect_rejection(lambda: verify_schedule(missing_execution, questions))

    duplicate_execution = copy.deepcopy(schedule)
    duplicate_execution["executions"][1]["execution_id"] = duplicate_execution[
        "executions"
    ][0]["execution_id"]
    expect_rejection(lambda: verify_schedule(duplicate_execution, questions))

    changed_rotation = copy.deepcopy(schedule)
    changed_rotation["blocks"][0]["workflow_order"].reverse()
    expect_rejection(lambda: verify_schedule(changed_rotation, questions))

    changed_order_hash = copy.deepcopy(schedule)
    changed_order_hash["blocks"][0]["question_order_sha256"] = "0" * 64
    expect_rejection(lambda: verify_schedule(changed_order_hash, questions))

    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-test-stage-") as directory:
        staging = stage_frozen_gate3_runtime(Path(directory))
        assert staging["reference_answers_staged"] is False
        assert not (Path(directory) / "evals/reference_answers").exists()

    policy = budget_policy()
    assert policy["hard_ceiling"] == {"currency": "CNY", "amount": 25.0}
    assert policy["automated_estimate"]["runner_budget_usd"] == 2.25
    assert policy["automated_estimate"]["contingency_reserve_cny"] == 2.5
    assert schedule["audit_selection"]["expected_audited_answer_count"] == 135

    print(
        json.dumps(
            {
                "status": "PASS",
                **report,
                "missing_execution_rejected": True,
                "duplicate_execution_id_rejected": True,
                "workflow_rotation_change_rejected": True,
                "question_order_hash_change_rejected": True,
                "reference_answers_excluded_from_stage": True,
                "budget_currency": "CNY",
                "budget_hard_ceiling": 25.0,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
