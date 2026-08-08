"""Verify the Gate 4 held-out questions, references, and Direct input."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_production_question_artifacts,
)


if __name__ == "__main__":
    print(json.dumps(verify_production_question_artifacts(), indent=2))
