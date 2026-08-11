"""Query any schema-valid BIMChange-Agent Change Record artifact offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.change_query import (  # noqa: E402
    DEFAULT_CHANGE_RECORD_PATH,
    load_json,
    query_change_records,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="JSON query request")
    parser.add_argument(
        "--change-records",
        type=Path,
        default=DEFAULT_CHANGE_RECORD_PATH,
        help=(
            "Change Record JSON artifact to query "
            "(defaults to data/ground_truth/gate2-change-records.json)"
        ),
    )
    parser.add_argument("--output", type=Path, help="Optional JSON response path")
    args = parser.parse_args()

    response = query_change_records(
        load_json(args.request),
        change_record_path=args.change_records,
    )
    rendered = json.dumps(response, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")


if __name__ == "__main__":
    main()
