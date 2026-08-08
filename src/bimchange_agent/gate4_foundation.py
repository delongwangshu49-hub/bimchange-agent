"""Gate 4 contract guard and held-out path registry validation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FOUNDATION_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "gate4-foundation.json"
EXPECTED_GATE3_BASELINE = "abcb095858ea45a1727d68d91063376ef77381ad"
EXPECTED_GATE4_PUBLIC_START = "2e7d38c53f9c3498875f34f6742164448983660d"
EXPECTED_DATASET_ID = "gate4-controlled-heldout-v0.1.0"
EXPECTED_SPLIT = "held_out"
EXPECTED_GATE4_PATHS = {
    "source_ifc": (
        "data/generated/held_out/gate4-controlled-heldout-v0.1.0/source.ifc"
    ),
    "revised_ifc": (
        "data/generated/held_out/gate4-controlled-heldout-v0.1.0/revised.ifc"
    ),
    "operation_ledger": (
        "data/ground_truth/held_out/gate4-controlled-heldout-v0.1.0/"
        "operation-ledger.json"
    ),
    "change_records": (
        "data/ground_truth/held_out/gate4-controlled-heldout-v0.1.0/"
        "change-records.json"
    ),
    "questions": "evals/questions/held_out/gate4-questions.json",
    "reference_answers": (
        "evals/reference_answers/held_out/gate4-reference-answers.json"
    ),
    "direct_input": "evals/inputs/held_out/gate4-model-pair-summary.json",
    "run_schedule": "evals/schedules/held_out/gate4-run-schedule.json",
    "pre_run_audit": "evals/audits/held_out/gate4-pre-run-audit.json",
    "post_run_audit": "evals/audits/held_out/gate4-post-run-audit.json",
    "freeze_manifest": "evals/manifests/held_out/gate4-freeze-manifest.json",
    "results_directory": (
        "evals/results/held_out/gate4-controlled-heldout-v0.1.0"
    ),
}
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FoundationViolation(RuntimeError):
    """Raised when a frozen contract or path boundary is violated."""


def load_foundation_config(path: Path = FOUNDATION_CONFIG_PATH) -> dict[str, Any]:
    """Load the reviewed Gate 4 foundation configuration."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundationViolation(f"Cannot load foundation config: {exc}") from exc
    if not isinstance(payload, dict):
        raise FoundationViolation("Foundation config must be a JSON object")
    return payload


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise FoundationViolation(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _git_text(repo_root: Path, *args: str) -> str:
    return _git_bytes(repo_root, *args).decode("utf-8").strip()


def _validate_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise FoundationViolation(f"{label} must be a non-empty string")
    if "\\" in value:
        raise FoundationViolation(f"{label} must use repository-style forward slashes")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise FoundationViolation(f"{label} must be a normalized relative path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise FoundationViolation(f"{label} contains an unsafe path component")
    return value


def validate_gate4_paths(
    config: dict[str, Any], protected_paths: set[str]
) -> dict[str, str]:
    """Validate path strings without opening or generating held-out artifacts."""
    gate4_paths = config.get("gate4_paths")
    if gate4_paths != EXPECTED_GATE4_PATHS:
        raise FoundationViolation(
            "Gate 4 path registry differs from the frozen mapping"
        )

    normalized: dict[str, str] = {}
    for key, raw_path in gate4_paths.items():
        path = _validate_relative_path(raw_path, f"gate4_paths.{key}")
        parts = PurePosixPath(path).parts
        if "held_out" not in parts:
            raise FoundationViolation(f"Gate 4 path is not held-out isolated: {path}")
        if "development" in parts or any("gate3" in part.lower() for part in parts):
            raise FoundationViolation(
                f"Gate 4 path overlaps development naming: {path}"
            )
        normalized[key] = path

    if len(set(normalized.values())) != len(normalized):
        raise FoundationViolation("Gate 4 path registry contains duplicate targets")

    protected = [PurePosixPath(path) for path in protected_paths]
    for raw_path in normalized.values():
        candidate = PurePosixPath(raw_path)
        for frozen in protected:
            if (
                candidate == frozen
                or candidate in frozen.parents
                or frozen in candidate.parents
            ):
                raise FoundationViolation(
                    f"Gate 4 target overlaps a protected Gate 3 path: {raw_path}"
                )
    return normalized


def _validate_foundation_identity(config: dict[str, Any], repo_root: Path) -> None:
    expected_values = {
        "schema_version": "0.1.0",
        "gate3_baseline_commit": EXPECTED_GATE3_BASELINE,
        "gate4_public_start_commit": EXPECTED_GATE4_PUBLIC_START,
        "dataset_id": EXPECTED_DATASET_ID,
        "split": EXPECTED_SPLIT,
    }
    for key, expected in expected_values.items():
        if config.get(key) != expected:
            raise FoundationViolation(f"{key} differs from the reviewed value")

    resolved_baseline = _git_text(
        repo_root, "rev-parse", f"{EXPECTED_GATE3_BASELINE}^{{commit}}"
    )
    if resolved_baseline != EXPECTED_GATE3_BASELINE:
        raise FoundationViolation(
            "Gate 3 baseline does not resolve to the pinned commit"
        )
    resolved_start = _git_text(
        repo_root, "rev-parse", f"{EXPECTED_GATE4_PUBLIC_START}^{{commit}}"
    )
    if resolved_start != EXPECTED_GATE4_PUBLIC_START:
        raise FoundationViolation("Gate 4 start does not resolve to the pinned commit")

    _git_bytes(
        repo_root,
        "merge-base",
        "--is-ancestor",
        EXPECTED_GATE4_PUBLIC_START,
        "HEAD",
    )


def verify_protected_gate3_files(
    config: dict[str, Any], repo_root: Path = REPOSITORY_ROOT
) -> list[dict[str, str]]:
    """Compare baseline, HEAD, index, and working-tree canonical Git blobs."""
    entries = config.get("protected_gate3_files")
    if not isinstance(entries, list) or not entries:
        raise FoundationViolation("protected_gate3_files must be a non-empty list")

    paths: list[str] = []
    verified: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "git_blob_oid",
            "sha256",
        }:
            raise FoundationViolation(f"Protected entry {index} has invalid fields")
        path = _validate_relative_path(entry["path"], f"protected entry {index}")
        expected_oid = entry["git_blob_oid"]
        expected_sha256 = entry["sha256"]
        if not isinstance(expected_oid, str) or not SHA1_PATTERN.fullmatch(
            expected_oid
        ):
            raise FoundationViolation(f"Protected entry has invalid Git OID: {path}")
        if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(
            expected_sha256
        ):
            raise FoundationViolation(f"Protected entry has invalid SHA-256: {path}")
        paths.append(path)

        baseline_oid = _git_text(
            repo_root, "rev-parse", f"{EXPECTED_GATE3_BASELINE}:{path}"
        )
        baseline_bytes = _git_bytes(
            repo_root, "show", f"{EXPECTED_GATE3_BASELINE}:{path}"
        )
        baseline_sha256 = hashlib.sha256(baseline_bytes).hexdigest()
        head_oid = _git_text(repo_root, "rev-parse", f"HEAD:{path}")
        index_oid = _git_text(repo_root, "rev-parse", f":{path}")
        worktree_oid = _git_text(repo_root, "hash-object", f"--path={path}", path)

        comparisons = {
            "manifest Git OID": expected_oid,
            "manifest SHA-256": expected_sha256,
            "HEAD Git OID": head_oid,
            "index Git OID": index_oid,
            "working-tree Git OID": worktree_oid,
        }
        expected = {
            "manifest Git OID": baseline_oid,
            "manifest SHA-256": baseline_sha256,
            "HEAD Git OID": baseline_oid,
            "index Git OID": baseline_oid,
            "working-tree Git OID": baseline_oid,
        }
        for label, actual in comparisons.items():
            if actual != expected[label]:
                raise FoundationViolation(
                    f"{label} mismatch for protected file: {path}"
                )

        verified.append(
            {"path": path, "git_blob_oid": baseline_oid, "sha256": baseline_sha256}
        )

    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise FoundationViolation("Protected Gate 3 paths must be sorted and unique")
    return verified


def verify_gate4_foundation(
    repo_root: Path = REPOSITORY_ROOT,
    config_path: Path = FOUNDATION_CONFIG_PATH,
) -> dict[str, Any]:
    """Verify the frozen Gate 3 boundary before any held-out artifact access."""
    config = load_foundation_config(config_path)
    _validate_foundation_identity(config, repo_root)
    verified_files = verify_protected_gate3_files(config, repo_root)
    protected_paths = {entry["path"] for entry in verified_files}
    gate4_paths = validate_gate4_paths(config, protected_paths)
    return {
        "status": "PASS",
        "gate3_baseline_commit": EXPECTED_GATE3_BASELINE,
        "gate4_public_start_commit": EXPECTED_GATE4_PUBLIC_START,
        "dataset_id": EXPECTED_DATASET_ID,
        "split": EXPECTED_SPLIT,
        "protected_gate3_file_count": len(verified_files),
        "gate4_path_count": len(gate4_paths),
        "held_out_artifacts_read": False,
        "held_out_artifacts_generated": False,
        "model_calls_made": 0,
    }


def main() -> int:
    try:
        report = verify_gate4_foundation()
    except FoundationViolation as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0
