"""Generate the controlled IFC revision used for the Gate 1 diff test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import get_pset


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
REVISED_PATH = (
    REPOSITORY_ROOT / "data" / "generated" / "Building-Structural-gate1-v2.ifc"
)
GROUND_TRUTH_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate1-property-change.json"
)
TARGET_GLOBAL_ID = "2ddLgAnQf4mBfh5IpUp54U"
PROPERTY_SET = "Pset_BeamCommon"
PROPERTY = "IsExternal"
EXPECTED_OLD_VALUE = False
NEW_VALUE = True


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    model = ifcopenshell.open(SOURCE_PATH)
    target = model.by_guid(TARGET_GLOBAL_ID)

    if not target.is_a("IfcBeam"):
        raise RuntimeError(
            f"Expected {TARGET_GLOBAL_ID} to be an IfcBeam, got {target.is_a()}"
        )

    pset_data = get_pset(target, PROPERTY_SET)
    if not pset_data or "id" not in pset_data:
        raise RuntimeError(f"Property set not found: {PROPERTY_SET}")

    old_value = pset_data.get(PROPERTY)
    if old_value != EXPECTED_OLD_VALUE:
        raise RuntimeError(
            f"Expected {PROPERTY_SET}.{PROPERTY}={EXPECTED_OLD_VALUE!r}, "
            f"got {old_value!r}"
        )

    pset = model.by_id(pset_data["id"])
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset,
        properties={PROPERTY: NEW_VALUE},
    )
    REVISED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.write(REVISED_PATH)

    ground_truth = {
        "source_ifc": SOURCE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "source_sha256": sha256(SOURCE_PATH),
        "revised_ifc": REVISED_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "revised_sha256": sha256(REVISED_PATH),
        "changes": [
            {
                "change_type": "property_modified",
                "entity_type": target.is_a(),
                "global_id": target.GlobalId,
                "property_set": PROPERTY_SET,
                "property": PROPERTY,
                "old_value": old_value,
                "new_value": NEW_VALUE,
            }
        ],
    }
    GROUND_TRUTH_PATH.write_text(
        json.dumps(ground_truth, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(ground_truth, indent=2))


if __name__ == "__main__":
    main()
