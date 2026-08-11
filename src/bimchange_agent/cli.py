"""Installable command-line boundary used by tests and the future desktop UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from jsonschema import ValidationError

from .product_core import ProductBoundaryError, diff_ifc_pair, inspect_ifc
from .product_query import query_product_artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bimchange")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inspect one bounded IFC4 file")
    inspect_parser.add_argument("ifc_path", type=Path)

    diff_parser = subparsers.add_parser(
        "diff", help="diff two bounded IFC4 files and write JSON artifacts"
    )
    diff_parser.add_argument("source_ifc", type=Path)
    diff_parser.add_argument("revised_ifc", type=Path)
    diff_parser.add_argument("--output-dir", type=Path, required=True)

    query_parser = subparsers.add_parser(
        "query", help="filter one normalized v0.2 preview artifact"
    )
    query_parser.add_argument("artifact", type=Path)
    query_parser.add_argument("--change-type", action="append", dest="change_types")
    query_parser.add_argument("--entity-type", action="append", dest="entity_types")
    query_parser.add_argument("--global-id", action="append", dest="global_ids")
    query_parser.add_argument(
        "--storey", action="append", dest="building_storey_names"
    )
    query_parser.add_argument("--property-set")
    query_parser.add_argument("--property-name")
    return parser


def _filters(namespace: argparse.Namespace) -> dict[str, object]:
    keys = (
        "change_types",
        "entity_types",
        "global_ids",
        "building_storey_names",
        "property_set",
        "property_name",
    )
    return {
        key: value
        for key in keys
        if (value := getattr(namespace, key, None)) is not None
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and return a process-compatible status code."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_ifc(args.ifc_path)
        elif args.command == "diff":
            result = diff_ifc_pair(
                args.source_ifc, args.revised_ifc, args.output_dir
            )
        else:
            result = query_product_artifact(args.artifact, _filters(args))
    except (
        FileNotFoundError,
        OSError,
        ProductBoundaryError,
        TypeError,
        ValidationError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {"status": "ERROR", "error": str(error)}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
