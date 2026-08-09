"""Generate the Gate 4 pre-call freeze manifest after implementation commit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_orchestration import (  # noqa: E402
    FREEZE_MANIFEST_PATH,
    SCHEDULE_PATH,
    artifact_sha256,
    build_freeze_manifest,
    foundation_paths,
    load_json,
    reproduce_gate3_retained_artifacts,
    stage_frozen_gate3_runtime,
    verify_schedule,
    write_json,
)
from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_fixture_verification import (  # noqa: E402
    verify_production_artifacts,
)
from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_production_question_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    implementation_commit = args.implementation_commit or subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    foundation = verify_gate4_foundation()
    replay = reproduce_gate3_retained_artifacts()
    fixture = verify_production_artifacts()
    questions = verify_production_question_artifacts()
    paths = foundation_paths()
    schedule = verify_schedule(
        load_json(SCHEDULE_PATH), load_json(paths["questions"])
    )
    import tempfile

    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-manifest-stage-") as directory:
        staged = stage_frozen_gate3_runtime(Path(directory))
    verification = {
        "status": "PASS_BEFORE_MANIFEST_GENERATION",
        "foundation_guard": foundation["status"],
        "fixture_verifier": fixture["status"],
        "question_verifier": questions["status"],
        "gate3_isolated_replay": replay["status"],
        "schedule_verifier": schedule["status"],
        "frozen_runtime_stage": staged["status"],
        "positive_and_negative_tests": "PASS_RECORDED_IN_PRE_RUN_AUDIT",
        "leakage_and_sensitive_content_scan": "PASS_RECORDED_IN_PRE_RUN_AUDIT",
        "model_calls_made": 0,
    }
    write_json(
        FREEZE_MANIFEST_PATH,
        build_freeze_manifest(implementation_commit, verification),
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "path": FREEZE_MANIFEST_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "freeze_manifest_sha256": artifact_sha256(FREEZE_MANIFEST_PATH),
                "implementation_commit": implementation_commit,
                "live_calls_authorized": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
