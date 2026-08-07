"""Run the Gate 1 IFC loading smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import ifcopenshell


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IFC_PATH = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
ENTITY_TYPES = (
    "IfcProject",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcBeam",
    "IfcColumn",
    "IfcSlab",
    "IfcWall",
    "IfcFooting",
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_ifc(path: Path) -> dict[str, object]:
    """Open an IFC file and return a small, deterministic summary."""
    model = ifcopenshell.open(path)
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "ifcopenshell_version": ifcopenshell.version,
        "schema": model.schema,
        "entity_count": sum(1 for _ in model),
        "selected_entity_counts": {
            entity_type: len(model.by_type(entity_type))
            for entity_type in ENTITY_TYPES
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ifc_path",
        nargs="?",
        type=Path,
        default=DEFAULT_IFC_PATH,
        help="IFC file to inspect (defaults to the Gate 1 sample).",
    )
    args = parser.parse_args()

    if not args.ifc_path.is_file():
        parser.error(f"IFC file not found: {args.ifc_path}")

    print(json.dumps(inspect_ifc(args.ifc_path), indent=2))


if __name__ == "__main__":
    main()
