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
    FREEZE_MANIFEST_PATH,
    PRE_RUN_AUDIT_PATH,
    REVIEW_STATE_PATH,
    SCHEDULE_PATH,
    budget_policy,
    foundation_paths,
    load_json,
    load_review_state,
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
    review_state = load_review_state()
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

    audit = load_json(PRE_RUN_AUDIT_PATH)
    manifest = load_json(FREEZE_MANIFEST_PATH)
    assert audit["status"] == "HUMAN_REVIEW_COMPLETE"
    assert audit["human_review"]["status"] == "COMPLETE"
    assert set(audit["human_review"]["checklist"].values()) == {"COMPLETE"}
    assert all(
        row["human_check"] == "COMPLETE"
        for row in audit["human_review"]["records"]
    )
    assert all(
        row["human_check"] == "COMPLETE"
        for row in audit["human_review"]["questions"]
    )
    assert manifest["approval_gates"] == review_state["approval_gates"]
    assert manifest["approval_gates"]["separate_live_call_authorization"] == "PENDING"
    assert manifest["live_calls_authorized"] is False

    tampered_state = copy.deepcopy(review_state)
    tampered_state["public_record"]["pull_request"]["merge_commit"] = "0" * 40
    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-review-state-") as directory:
        tampered_path = Path(directory) / REVIEW_STATE_PATH.name
        tampered_path.write_text(
            json.dumps(tampered_state, indent=2) + "\n", encoding="utf-8"
        )
        expect_rejection(lambda: load_review_state(tampered_path))

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
                "human_review_complete": True,
                "public_merge_record_bound": True,
                "tampered_review_state_rejected": True,
                "separate_live_call_authorization": "PENDING",
                "live_calls_authorized": False,
                "budget_currency": "CNY",
                "budget_hard_ceiling": 25.0,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
