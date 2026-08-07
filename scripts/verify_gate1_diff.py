"""Verify the Gate 1 IfcDiff result against the generated ground truth."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ifcopenshell
from ifcopenshell.util.element import get_pset


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate1-property-change.json"
)
DIFF_PATH = REPOSITORY_ROOT / "evals" / "results" / "gate1-ifcdiff.json"


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    diff = json.loads(DIFF_PATH.read_text(encoding="utf-8"))
    expected = ground_truth["changes"][0]

    source_path = REPOSITORY_ROOT / ground_truth["source_ifc"]
    revised_path = REPOSITORY_ROOT / ground_truth["revised_ifc"]
    assert sha256(source_path) == ground_truth["source_sha256"]
    assert sha256(revised_path) == ground_truth["revised_sha256"]

    assert diff["added"] == []
    assert diff["deleted"] == []
    assert set(diff["changed"]) == {expected["global_id"]}

    property_path = (
        f"root['{expected['property_set']}']['{expected['property']}']"
    )
    values_changed = diff["changed"][expected["global_id"]][
        "properties_changed"
    ]["values_changed"]
    actual = values_changed[property_path]
    assert actual["old_value"] == expected["old_value"]
    assert actual["new_value"] == expected["new_value"]

    source_model = ifcopenshell.open(source_path)
    revised_model = ifcopenshell.open(revised_path)
    source_value = get_pset(
        source_model.by_guid(expected["global_id"]),
        expected["property_set"],
        expected["property"],
    )
    revised_value = get_pset(
        revised_model.by_guid(expected["global_id"]),
        expected["property_set"],
        expected["property"],
    )
    assert source_value == expected["old_value"]
    assert revised_value == expected["new_value"]

    print(
        json.dumps(
            {
                "status": "PASS",
                "global_id": expected["global_id"],
                "property": property_path,
                "old_value": actual["old_value"],
                "new_value": actual["new_value"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
