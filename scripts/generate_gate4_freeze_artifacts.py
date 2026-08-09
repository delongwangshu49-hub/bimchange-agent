"""Generate the deterministic Gate 4 schedule and pre-run audit offline."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_orchestration import (  # noqa: E402
    PRE_RUN_AUDIT_PATH,
    SCHEDULE_PATH,
    build_pre_run_audit,
    artifact_sha256,
    build_schedule,
    foundation_paths,
    load_json,
    reproduce_gate3_retained_artifacts,
    write_json,
)
from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_production_question_artifacts,
)


def main() -> None:
    foundation_report = verify_gate4_foundation()
    gate3_replay = reproduce_gate3_retained_artifacts()
    question_report = verify_production_question_artifacts()
    paths = foundation_paths()
    questions = load_json(paths["questions"])
    changes = load_json(paths["change_records"])
    schedule = build_schedule(questions)
    write_json(SCHEDULE_PATH, schedule)
    pre_run_audit = build_pre_run_audit(
        questions,
        changes,
        schedule,
        {
            "foundation_guard": foundation_report,
            "gate3_retained_artifact_replay": gate3_replay,
            "held_out_question_verifier": question_report,
        },
    )
    write_json(PRE_RUN_AUDIT_PATH, pre_run_audit)
    print(
        json.dumps(
            {
                "status": "PASS",
                "written": [
                    SCHEDULE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                    PRE_RUN_AUDIT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                ],
                "schedule_sha256": artifact_sha256(SCHEDULE_PATH),
                "pre_run_audit_sha256": artifact_sha256(PRE_RUN_AUDIT_PATH),
                "primary_execution_count": 360,
                "human_review_status": "PENDING_USER_REVIEW",
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
