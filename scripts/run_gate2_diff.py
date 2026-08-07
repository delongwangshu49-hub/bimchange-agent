"""Generate, compare, and verify the controlled Gate 2 IFC revision."""

from __future__ import annotations

import subprocess
import sys

import generate_gate2_revision
import verify_gate2_diff


def main() -> None:
    generate_gate2_revision.main()
    generate_gate2_revision.DIFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ifcdiff",
            str(generate_gate2_revision.SOURCE_PATH),
            str(generate_gate2_revision.REVISED_PATH),
            "--relationships",
            "property",
            "--output",
            str(generate_gate2_revision.DIFF_PATH),
        ],
        check=True,
    )
    verify_gate2_diff.main()


if __name__ == "__main__":
    main()
