"""Generate the Gate 4 held-out questions and deterministic reference answers."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_question_artifacts import (  # noqa: E402
    write_production_artifacts,
)


if __name__ == "__main__":
    print(json.dumps(write_production_artifacts(), indent=2))
