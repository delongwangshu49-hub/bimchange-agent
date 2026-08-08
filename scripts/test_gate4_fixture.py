"""Offline regression test for the Gate 4 held-out fixture contract."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_fixture_verification import (  # noqa: E402
    DIFF_RELATIVE_PATH,
    _validate_ifcdiff,
    _validate_spatial_model,
    verify_production_artifacts,
)
from bimchange_agent.gate4_fixture import build_source_model  # noqa: E402
from bimchange_agent.gate4_foundation import (  # noqa: E402
    load_foundation_config,
    verify_gate4_foundation,
)


def expect_assertion(action: Callable[[], object]) -> None:
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("Expected the tampered fixture to be rejected")


def main() -> None:
    report = verify_production_artifacts()
    assert report["status"] == "PASS"
    assert report["source_element_count"] == 48
    assert report["revised_element_count"] == 48
    assert report["unchanged_element_count"] == 40
    assert report["change_count"] == 12
    assert report["ifcdiff_exact_change_count"] == 12
    assert report["clean_regeneration_byte_identical"] is True
    assert report["model_calls_made"] == 0

    # Guard again before the negative test reads registered held-out artifacts.
    verify_gate4_foundation()
    paths = load_foundation_config()["gate4_paths"]
    records = json.loads(
        (REPOSITORY_ROOT / paths["change_records"]).read_text(encoding="utf-8")
    )["changes"]
    diff = json.loads(
        (REPOSITORY_ROOT / DIFF_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    tampered_diff = copy.deepcopy(diff)
    tampered_diff["added"].append("0000000000000000000000")
    expect_assertion(lambda: _validate_ifcdiff(tampered_diff, records))

    leaking_model = build_source_model()
    leaking_model.by_type("IfcBeam")[0].Name = "Added answer beam"
    expect_assertion(lambda: _validate_spatial_model(leaking_model))

    report["tampered_ifcdiff_rejected"] = True
    report["answer_bearing_name_rejected"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
