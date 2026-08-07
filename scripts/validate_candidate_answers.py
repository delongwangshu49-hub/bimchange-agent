"""Validate structured evidence in a common Gate 3 candidate answer artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.evidence_validation import (  # noqa: E402
    load_json,
    validate_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="Candidate answer JSON")
    args = parser.parse_args()
    print(json.dumps(validate_evidence(load_json(args.candidate)), indent=2))


if __name__ == "__main__":
    main()
