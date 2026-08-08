"""Offline checks for the Gate 4 foundation guard."""

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
    FoundationViolation,
    load_foundation_config,
    validate_gate4_paths,
    verify_gate4_foundation,
    verify_protected_gate3_files,
)


def expect_violation(action: Callable[[], object]) -> None:
    try:
        action()
    except FoundationViolation:
        return
    raise AssertionError("Expected a FoundationViolation")


def main() -> None:
    config = load_foundation_config()
    report = verify_gate4_foundation()
    assert report["status"] == "PASS"
    assert report["protected_gate3_file_count"] == 37
    assert report["gate4_path_count"] == 12
    assert report["held_out_artifacts_read"] is False
    assert report["held_out_artifacts_generated"] is False
    assert report["model_calls_made"] == 0

    tampered_hash = copy.deepcopy(config)
    tampered_hash["protected_gate3_files"][0]["sha256"] = "0" * 64
    expect_violation(
        lambda: verify_protected_gate3_files(tampered_hash, REPOSITORY_ROOT)
    )

    tampered_path = copy.deepcopy(config)
    tampered_path["gate4_paths"]["questions"] = (
        "evals/questions/development/gate4-questions.json"
    )
    protected_paths = {
        entry["path"] for entry in config["protected_gate3_files"]
    }
    expect_violation(lambda: validate_gate4_paths(tampered_path, protected_paths))

    duplicate_path = copy.deepcopy(config)
    duplicate_path["gate4_paths"]["revised_ifc"] = duplicate_path["gate4_paths"][
        "source_ifc"
    ]
    expect_violation(lambda: validate_gate4_paths(duplicate_path, protected_paths))

    print(
        json.dumps(
            {
                "status": "PASS",
                "protected_gate3_file_count": report[
                    "protected_gate3_file_count"
                ],
                "gate4_path_count": report["gate4_path_count"],
                "tampered_hash_rejected": True,
                "development_path_rejected": True,
                "duplicate_path_rejected": True,
                "held_out_artifacts_read": False,
                "held_out_artifacts_generated": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
