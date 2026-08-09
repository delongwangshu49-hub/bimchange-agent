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
    SCHEDULE_PATH,
    artifact_sha256,
    budget_policy,
    foundation_paths,
    load_json,
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


def scan_freeze_files(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible API credential found in {path}")


def verify_manifest(manifest: dict[str, object]) -> None:
    allowed_statuses = {
        "AWAITING_USER_REVIEW_AND_PUBLIC_RECORD",
        "FROZEN_AFTER_USER_REVIEW_AND_PUBLIC_RECORD",
    }
    if manifest["freeze_status"] not in allowed_statuses:
        raise ValueError("Unexpected freeze status")
    if manifest["live_calls_authorized"] is not False:
        raise ValueError("Pre-review manifest must not authorize live calls")
    if manifest["model_calls_made"] != 0:
        raise ValueError("Pre-call manifest must record zero model calls")
    for artifact in manifest["artifacts"].values():
        path = REPOSITORY_ROOT / artifact["path"]
        if artifact_sha256(path) != artifact["sha256"]:
            raise ValueError(f"Manifest hash mismatch: {artifact['path']}")


def main() -> None:
    foundation = verify_gate4_foundation()
    replay = reproduce_gate3_retained_artifacts()
    questions_report = verify_production_question_artifacts()
    paths = foundation_paths()
    questions = load_json(paths["questions"])
    schedule = load_json(SCHEDULE_PATH)
    schedule_report = verify_schedule(schedule, questions)
    audit = load_json(PRE_RUN_AUDIT_PATH)
    if audit["status"] != "READY_FOR_SINGLE_HUMAN_REVIEW":
        raise ValueError("Pre-run audit is not ready for human review")
    if audit["human_review"]["status"] != "PENDING_USER_REVIEW":
        raise ValueError("Local pre-run audit must truthfully remain pending")
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

    freeze_files = [SCHEDULE_PATH, PRE_RUN_AUDIT_PATH]
    if FREEZE_MANIFEST_PATH.exists():
        manifest = load_json(FREEZE_MANIFEST_PATH)
        verify_manifest(manifest)
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
                "human_review_status": "PENDING_USER_REVIEW",
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
