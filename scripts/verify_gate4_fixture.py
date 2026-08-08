"""Verify the deterministic Gate 4 held-out IFC fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_fixture_verification import (  # noqa: E402
    verify_production_artifacts,
)


def main() -> None:
    print(json.dumps(verify_production_artifacts(), indent=2))


if __name__ == "__main__":
    main()
