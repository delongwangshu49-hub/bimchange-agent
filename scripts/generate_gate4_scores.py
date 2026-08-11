"""Score every frozen Gate 4 execution with the byte-frozen Gate 3 scorer."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_orchestration import (  # noqa: E402
    SCHEDULE_PATH,
    artifact_sha256,
    canonical_hash,
    foundation_paths,
    load_json,
    sha256_file,
    stage_frozen_gate3_runtime,
    write_json,
)
from generate_gate3_reference_answers import (  # noqa: E402
    build_canonical_predictions,
)
from generate_gate4_blind_audit_packet import (  # noqa: E402
    EXPECTED_SCHEDULE_SHA256,
    RESULT_MANIFEST_PATH,
    RESULTS_ROOT,
    build_result_manifest,
    require_equal,
)
from generate_gate4_unblinding_mapping import (  # noqa: E402
    EXPECTED_IMPORTED_PACKET_SHA256,
    EXPECTED_RESULT_MANIFEST_SHA256,
    MAPPING_PATH,
)
import score_gate3_predictions as frozen_scorer  # noqa: E402


EXPECTED_MAPPING_SHA256 = (
    "baa683480af050669e7523ab2339f56e787784b5eaa94e6628d71cf73dc13f4a"
)
EXPECTED_REFERENCE_ARTIFACT_SHA256 = (
    "4f7ef0e3a87ee7a35f1089ee1d7d9b199140c1cd66d4bc8f67a1dce44082ef1a"
)
EXPECTED_REFERENCE_RAW_SHA256 = (
    "7a36081063c735e69b7290722f71b24b87546c49c6af32ec4ba60d2a6a8e9a8c"
)
SCORES_PATH = RESULTS_ROOT / "gate4-scored-executions.json"


def load_staged_evidence_module(stage: Path):
    """Load the copied evidence validator so its fixed paths resolve in staging."""
    path = stage / "src/bimchange_agent/evidence_validation.py"
    spec = importlib.util.spec_from_file_location(
        "gate4_frozen_evidence_validation", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load staged frozen evidence validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_staged_evidence_validator(stage: Path) -> None:
    """Bind the frozen scorer to the unchanged validator loaded from staging."""
    evidence = load_staged_evidence_module(stage)
    frozen_scorer.validate_candidate_schema = evidence.validate_candidate_schema
    frozen_scorer.validate_evidence = evidence.validate_evidence
    frozen_scorer.prediction_fact = evidence.prediction_fact


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    verify_gate4_foundation()
    require_equal(
        artifact_sha256(SCHEDULE_PATH), EXPECTED_SCHEDULE_SHA256, "schedule hash"
    )
    require_equal(
        artifact_sha256(RESULT_MANIFEST_PATH),
        EXPECTED_RESULT_MANIFEST_SHA256,
        "result manifest hash",
    )
    require_equal(
        load_json(RESULT_MANIFEST_PATH), build_result_manifest(), "result manifest"
    )
    require_equal(
        artifact_sha256(MAPPING_PATH), EXPECTED_MAPPING_SHA256, "mapping hash"
    )
    mapping = load_json(MAPPING_PATH)
    require_equal(
        mapping["completed_audit_packet_sha256"],
        EXPECTED_IMPORTED_PACKET_SHA256,
        "completed audit packet lineage",
    )
    reference_path = foundation_paths()["reference_answers"]
    require_equal(
        artifact_sha256(reference_path),
        EXPECTED_REFERENCE_ARTIFACT_SHA256,
        "reference artifact hash",
    )
    require_equal(
        sha256_file(reference_path),
        EXPECTED_REFERENCE_RAW_SHA256,
        "reference raw hash",
    )
    schedule = load_json(SCHEDULE_PATH)
    reference_answers = load_json(reference_path)
    canonical_reference = build_canonical_predictions(reference_answers)
    require_equal(len(canonical_reference["answers"]), 40, "reference count")
    return schedule, reference_answers, canonical_reference


def candidate_group(workflow: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    answers = [candidate["answers"][0] for candidate in candidates]
    return {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "question_split": "held_out",
        "workflow": workflow,
        "answers": answers,
    }


def build_scores() -> dict[str, Any]:
    schedule, reference_answers, canonical_reference = validate_inputs()
    candidates_by_group: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    execution_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-score-stage-") as directory:
        stage = Path(directory)
        staging = stage_frozen_gate3_runtime(stage)
        bind_staged_evidence_validator(stage)

        for execution in schedule["executions"]:
            execution_id = execution["execution_id"]
            directory_path = RESULTS_ROOT / "primary" / execution_id
            run_path = directory_path / "run.json"
            candidate_path = directory_path / "candidate.json"
            run = load_json(run_path)
            require_equal(run["execution_id"], execution_id, "run execution ID")
            require_equal(run["workflow"], execution["workflow"], "run workflow")
            require_equal(run["repetition"], execution["repetition"], "repetition")
            require_equal(run["question_id"], execution["question_id"], "question ID")

            row: dict[str, Any] = {
                "execution_id": execution_id,
                "ordinal": execution["ordinal"],
                "workflow": execution["workflow"],
                "repetition": execution["repetition"],
                "question_id": execution["question_id"],
                "category": execution["category"],
                "run_sha256": sha256_file(run_path),
                "candidate_available": candidate_path.is_file(),
            }
            if candidate_path.is_file():
                candidate = load_json(candidate_path)
                require_equal(len(candidate["answers"]), 1, "candidate answer count")
                require_equal(
                    candidate["answers"][0]["question_id"],
                    execution["question_id"],
                    "candidate question ID",
                )
                score = frozen_scorer.score_candidate(
                    canonical_reference, candidate, allow_subset=True
                )
                row["candidate_sha256"] = sha256_file(candidate_path)
                row["score"] = score
                row["experimental_failure"] = None
                candidates_by_group[
                    (execution["workflow"], execution["repetition"])
                ].append(candidate)
            else:
                require_equal(run["status"], "EXPERIMENTAL_FAILURE", "run status")
                row["candidate_sha256"] = None
                row["score"] = None
                row["experimental_failure"] = {
                    "category": run["failure"]["category"],
                    "retry_allowed": run["failure"]["retry_allowed"],
                    "retry_performed": run["failure"]["retry_performed"],
                }
            execution_rows.append(row)

        group_rows: list[dict[str, Any]] = []
        for repetition in (1, 2, 3):
            for workflow in ("direct_llm", "tool_using_agent", "proposed"):
                candidates = candidates_by_group[(workflow, repetition)]
                combined = candidate_group(workflow, candidates)
                metrics = frozen_scorer.score_candidate(
                    canonical_reference,
                    combined,
                    count_missing_as_failure=True,
                )
                group_rows.append(
                    {
                        "workflow": workflow,
                        "repetition": repetition,
                        "candidate_count": len(candidates),
                        "experimental_failure_count": 40 - len(candidates),
                        "metrics": metrics,
                    }
                )

    require_equal(len(execution_rows), 360, "scored execution count")
    require_equal(
        sum(row["candidate_available"] for row in execution_rows),
        348,
        "scored candidate count",
    )
    return {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "split": "held_out",
        "status": "FROZEN_OFFLINE_SCORING_COMPLETE",
        "scorer": {
            "authoritative_file": "scripts/score_gate3_predictions.py",
            "evidence_validator_file": "src/bimchange_agent/evidence_validation.py",
            "gate3_baseline_commit": "abcb095858ea45a1727d68d91063376ef77381ad",
            "per_answer_identity_or_rule_changed": False,
            "held_out_inputs_mapped_in_isolated_staging": True,
        },
        "lineage": {
            "schedule_sha256": EXPECTED_SCHEDULE_SHA256,
            "result_manifest_sha256": EXPECTED_RESULT_MANIFEST_SHA256,
            "completed_audit_packet_sha256": EXPECTED_IMPORTED_PACKET_SHA256,
            "mapping_sha256": EXPECTED_MAPPING_SHA256,
            "reference_answer_artifact_sha256": EXPECTED_REFERENCE_ARTIFACT_SHA256,
            "reference_answer_raw_sha256": EXPECTED_REFERENCE_RAW_SHA256,
            "canonical_reference_sha256": canonical_hash(canonical_reference),
        },
        "reference_answer_count": len(reference_answers["answers"]),
        "primary_execution_count": len(execution_rows),
        "candidate_count": sum(row["candidate_available"] for row in execution_rows),
        "experimental_failure_count": sum(
            not row["candidate_available"] for row in execution_rows
        ),
        "execution_scores": execution_rows,
        "workflow_repetition_scores": group_rows,
        "free_text_scored": False,
        "model_calls_made": 0,
    }


def main() -> None:
    report = build_scores()
    write_json(SCORES_PATH, report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "scores_path": SCORES_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "scores_sha256": artifact_sha256(SCORES_PATH),
                "primary_execution_count": report["primary_execution_count"],
                "candidate_count": report["candidate_count"],
                "experimental_failure_count": report["experimental_failure_count"],
                "workflow_repetition_group_count": len(
                    report["workflow_repetition_scores"]
                ),
                "free_text_scored": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
