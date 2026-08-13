"""Offline command line for the isolated R1 traceability slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME,
    RAW_DIFF_FILE_NAME,
    diff_ifc_pair,
)

from .traceability import (
    MANIFEST_FILE_NAME,
    generate_trace_manifest,
    verify_trace_manifest,
    write_json,
)


def _path(value: str) -> Path:
    return Path(value)


def _common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, type=_path)
    parser.add_argument("--revised", required=True, type=_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify deterministic R1 evidence manifests."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle = subparsers.add_parser(
        "bundle", help="Run the bounded product diff and add an R1 manifest."
    )
    _common_inputs(bundle)
    bundle.add_argument("--output", required=True, type=_path)

    generate = subparsers.add_parser(
        "generate", help="Generate a manifest for existing product artifacts."
    )
    _common_inputs(generate)
    generate.add_argument("--change-records", required=True, type=_path)
    generate.add_argument("--raw-result", required=True, type=_path)
    generate.add_argument("--manifest", required=True, type=_path)

    verify = subparsers.add_parser("verify", help="Fail-closed manifest verification.")
    _common_inputs(verify)
    verify.add_argument("--change-records", required=True, type=_path)
    verify.add_argument("--raw-result", required=True, type=_path)
    verify.add_argument("--manifest", required=True, type=_path)
    return parser


def _generate(args: argparse.Namespace) -> dict[str, object]:
    manifest = generate_trace_manifest(
        args.source,
        args.revised,
        args.change_records,
        args.raw_result,
    )
    write_json(args.manifest, manifest)
    report = verify_trace_manifest(
        args.manifest,
        args.source,
        args.revised,
        args.change_records,
        args.raw_result,
    )
    report["manifest_role_name"] = MANIFEST_FILE_NAME
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bundle":
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        diff_ifc_pair(args.source, args.revised, output)
        args.change_records = output / CHANGE_RECORD_FILE_NAME
        args.raw_result = output / RAW_DIFF_FILE_NAME
        args.manifest = output / MANIFEST_FILE_NAME
        report = _generate(args)
    elif args.command == "generate":
        report = _generate(args)
    else:
        report = verify_trace_manifest(
            args.manifest,
            args.source,
            args.revised,
            args.change_records,
            args.raw_result,
        )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
