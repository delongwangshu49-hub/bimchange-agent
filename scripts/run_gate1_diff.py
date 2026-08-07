"""Generate, compare, and verify the controlled Gate 1 IFC revision."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import generate_gate1_revision
import verify_gate1_diff


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DIFF_PATH = REPOSITORY_ROOT / "evals" / "results" / "gate1-ifcdiff.json"


def main() -> None:
    generate_gate1_revision.main()
    DIFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ifcdiff",
            str(generate_gate1_revision.SOURCE_PATH),
            str(generate_gate1_revision.REVISED_PATH),
            "--relationships",
            "property",
            "--output",
            str(DIFF_PATH),
        ],
        check=True,
    )
    verify_gate1_diff.main()


if __name__ == "__main__":
    main()
