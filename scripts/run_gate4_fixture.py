"""Generate, compare, and verify the Gate 4 held-out IFC fixture offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_fixture import generate_production_artifacts  # noqa: E402
from bimchange_agent.gate4_fixture_verification import (  # noqa: E402
    DIFF_RELATIVE_PATH,
    verify_production_artifacts,
)
from bimchange_agent.gate4_foundation import (  # noqa: E402
    load_foundation_config,
    verify_gate4_foundation,
)


def main() -> None:
    generation = generate_production_artifacts()

    # Re-run the guard immediately before the retained IfcDiff path is accessed.
    verify_gate4_foundation()
    paths = load_foundation_config()["gate4_paths"]
    source_path = REPOSITORY_ROOT / paths["source_ifc"]
    revised_path = REPOSITORY_ROOT / paths["revised_ifc"]
    diff_path = REPOSITORY_ROOT / DIFF_RELATIVE_PATH
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ifcdiff",
            str(source_path),
            str(revised_path),
            "--relationships",
            "property",
            "--output",
            str(diff_path),
        ],
        check=True,
    )

    verification = verify_production_artifacts()
    print(
        json.dumps(
            {
                "status": "PASS",
                "generation": generation,
                "verification": verification,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
