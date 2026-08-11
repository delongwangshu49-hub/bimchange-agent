"""Verify the documented offline quickstart from a repository checkout."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_json(*arguments: str) -> dict[str, object]:
    """Run a repository script and parse its JSON stdout."""
    completed = subprocess.run(
        [sys.executable, *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise TypeError("Quickstart command did not return a JSON object")
    return value


def main() -> None:
    ifc_summary = run_json("scripts/check_ifc.py")
    assert ifc_summary["schema"] == "IFC4"
    assert int(ifc_summary["entity_count"]) > 0

    query_response = run_json(
        "scripts/query_change_records.py",
        "examples/query-added-beams.json",
        "--change-records",
        "data/ground_truth/gate2-change-records.json",
    )
    assert query_response["result_count"] == 1
    results = query_response["results"]
    assert isinstance(results, list)
    assert results[0]["change_id"] == "gate2-added-001"

    print(
        json.dumps(
            {
                "status": "PASS",
                "ifc_schema": ifc_summary["schema"],
                "ifc_entity_count": ifc_summary["entity_count"],
                "query_result_count": query_response["result_count"],
                "query_change_id": results[0]["change_id"],
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
