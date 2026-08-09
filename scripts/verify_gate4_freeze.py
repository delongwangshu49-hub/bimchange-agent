"""Verify every Gate 4 pre-call freeze artifact without model access."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_orchestration import (  # noqa: E402
    FREEZE_MANIFEST_PATH,
    PRE_RUN_AUDIT_PATH,
    REVIEW_STATE_PATH,
    SCHEDULE_PATH,
    artifact_sha256,
    budget_policy,
    foundation_paths,
    load_json,
    load_review_state,
    reproduce_gate3_retained_artifacts,
    stage_frozen_gate3_runtime,
    verify_schedule,
)
from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_production_question_artifacts,
)


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
)
RUNNER_PATH = REPOSITORY_ROOT / "scripts" / "run_gate4_workflows.py"


def scan_freeze_files(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible API credential found in {path}")


def verify_live_lock_order() -> None:
    """Ensure approvals always run immediately before local key loading."""
    source = RUNNER_PATH.read_text(encoding="utf-8")
    pairs = re.findall(
        r"^([ \t]+)require_live_approvals\(args\)\r?\n\1load_local_key\(\)",
        source,
        flags=re.MULTILINE,
    )
    if len(pairs) != 2:
        raise ValueError("Live approval must precede both local-key load paths")
    authorization_check = source.find(
        "if args.authorization_phrase != AUTHORIZATION_PHRASE:"
    )
    public_freeze_check = source.find(
        "manifest = load_completed_public_freeze()", authorization_check
    )
    if authorization_check < 0 or public_freeze_check < authorization_check:
        raise ValueError("Exact live authorization is not the first live-path gate")


def verify_completed_audit(
    audit: dict[str, object], review_state: dict[str, object]
) -> None:
    if audit["status"] != "HUMAN_REVIEW_COMPLETE":
        raise ValueError("Pre-run audit has not completed human review")
    human = audit["human_review"]
    if human["status"] != "COMPLETE" or human["reviewer_count"] != 1:
        raise ValueError("Single-human pre-run review is incomplete")
    if human["inter_rater_agreement_claimed"] is not False:
        raise ValueError("Single-reviewer audit must not claim inter-rater agreement")
    if set(human["checklist"].values()) != {"COMPLETE"}:
        raise ValueError("Human review checklist is incomplete")
    if len(human["records"]) != 12 or any(
        row["human_check"] != "COMPLETE" for row in human["records"]
    ):
        raise ValueError("Change Record human review is incomplete")
    if len(human["questions"]) != 40 or any(
        row["human_check"] != "COMPLETE" for row in human["questions"]
    ):
        raise ValueError("Question human review is incomplete")
    transition = audit["review_transition"]
    if transition["status"] != review_state["transition_status"]:
        raise ValueError("Audit review transition status mismatch")
    if transition["public_record"] != review_state["public_record"]:
        raise ValueError("Audit public record mismatch")
    if transition["separate_live_call_authorization"] != "PENDING":
        raise ValueError("Audit must not pre-authorize live calls")
    if transition["live_calls_authorized"] is not False:
        raise ValueError("Audit must keep live calls locked")


def verify_manifest(
    manifest: dict[str, object], review_state: dict[str, object]
) -> None:
    if manifest["freeze_status"] != "FROZEN_AFTER_USER_REVIEW_AND_PUBLIC_RECORD":
        raise ValueError("Freeze manifest has not completed the public transition")
    if manifest["live_calls_authorized"] is not False:
        raise ValueError("Pre-call manifest must not authorize live calls")
    if manifest["model_calls_made"] != 0:
        raise ValueError("Pre-call manifest must record zero model calls")
    if manifest["approval_gates"] != review_state["approval_gates"]:
        raise ValueError("Manifest approval gates differ from the review state")
    if manifest["gate4_public_freeze_merge_commit"] != review_state[
        "public_record"
    ]["pull_request"]["merge_commit"]:
        raise ValueError("Manifest is not bound to the PR #8 merge commit")
    if manifest["review_transition"]["public_record"] != review_state[
        "public_record"
    ]:
        raise ValueError("Manifest public record mismatch")
    expected_state_hash = artifact_sha256(REVIEW_STATE_PATH)
    if manifest["review_transition"]["sha256"] != expected_state_hash:
        raise ValueError("Manifest review-state hash mismatch")
    for artifact in manifest["artifacts"].values():
        path = REPOSITORY_ROOT / artifact["path"]
        if artifact_sha256(path) != artifact["sha256"]:
            raise ValueError(f"Manifest hash mismatch: {artifact['path']}")


def main() -> None:
    review_state = load_review_state()
    verify_live_lock_order()
    foundation = verify_gate4_foundation()
    replay = reproduce_gate3_retained_artifacts()
    questions_report = verify_production_question_artifacts()
    paths = foundation_paths()
    questions = load_json(paths["questions"])
    schedule = load_json(SCHEDULE_PATH)
    schedule_report = verify_schedule(schedule, questions)
    audit = load_json(PRE_RUN_AUDIT_PATH)
    verify_completed_audit(audit, review_state)
    if audit["model_calls_made"] != 0 or audit["model_outputs_present"]:
        raise ValueError("Pre-run audit contains model activity")
    if paths["post_run_audit"].exists():
        raise ValueError("Post-run audit must not exist before model execution")
    results_directory = REPOSITORY_ROOT / load_json(
        REPOSITORY_ROOT / "configs/gate4-foundation.json"
    )["gate4_paths"]["results_directory"]
    existing_result_files = list(results_directory.glob("**/*")) if results_directory.exists() else []
    allowed_existing = {REPOSITORY_ROOT / "evals/results/held_out/gate4-controlled-heldout-v0.1.0/ifcdiff.json"}
    unexpected_results = [
        path for path in existing_result_files if path.is_file() and path not in allowed_existing
    ]
    if unexpected_results:
        raise ValueError(f"Unexpected held-out model results: {unexpected_results}")

    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-stage-") as directory:
        staging = stage_frozen_gate3_runtime(Path(directory))
        compiled = subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(Path(directory) / "src/bimchange_agent/gate3_runner.py"),
                str(Path(directory) / "src/bimchange_agent/change_query.py"),
                str(Path(directory) / "src/bimchange_agent/evidence_validation.py"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        del compiled

    freeze_files = [SCHEDULE_PATH, PRE_RUN_AUDIT_PATH, REVIEW_STATE_PATH]
    if FREEZE_MANIFEST_PATH.exists():
        manifest = load_json(FREEZE_MANIFEST_PATH)
        verify_manifest(manifest, review_state)
        freeze_files.append(FREEZE_MANIFEST_PATH)
        manifest_status = "PASS"
    else:
        manifest_status = "NOT_YET_GENERATED"
    scan_freeze_files(freeze_files)
    policy = budget_policy()
    if policy["hard_ceiling"] != {"currency": "CNY", "amount": 25.0}:
        raise ValueError("CNY 25 hard ceiling changed")
    print(
        json.dumps(
            {
                "status": "PASS",
                "foundation_status": foundation["status"],
                "gate3_replay_status": replay["status"],
                "question_verifier_status": questions_report["status"],
                "schedule": schedule_report,
                "staged_runtime": staging,
                "freeze_manifest_status": manifest_status,
                "budget_currency": "CNY",
                "budget_hard_ceiling": 25.0,
                "unexpected_model_result_count": 0,
                "post_run_audit_present": False,
                "human_review_status": "COMPLETE",
                "separate_live_call_authorization": "PENDING",
                "live_calls_authorized": False,
                "live_lock_call_order": "PASS",
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
