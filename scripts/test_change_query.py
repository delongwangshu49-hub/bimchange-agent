"""Exercise the Gate 3 Change Record query interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import ValidationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.change_query import query_change_records  # noqa: E402


def request(filters: dict[str, object]) -> dict[str, object]:
    """Build one valid query request."""
    return {"schema_version": "0.1.0", "filters": filters}


def main() -> None:
    all_changes = query_change_records(request({}))
    assert all_changes["result_count"] == 3

    added = query_change_records(request({"change_types": ["added"]}))
    assert added["result_count"] == 1
    assert added["results"][0]["change_id"] == "gate2-added-001"

    groundfloor_walls = query_change_records(
        request(
            {
                "change_types": ["deleted"],
                "entity_types": ["IfcWall"],
                "building_storey_names": ["00 groundfloor"],
            }
        )
    )
    assert groundfloor_walls["result_count"] == 1
    assert groundfloor_walls["results"][0]["change_id"] == "gate2-deleted-001"

    arbitrary_wall_query = query_change_records(
        request({"entity_types": ["IfcWall"]})
    )
    assert arbitrary_wall_query["result_count"] == 1

    geometry = query_change_records(
        request({"change_types": ["geometry_modified"]})
    )
    assert geometry["result_count"] == 0

    try:
        query_change_records(request({"change_types": ["ADDED"]}))
    except ValidationError:
        invalid_change_type_rejected = True
    else:
        raise AssertionError("Invalid change-type casing was accepted")

    try:
        query_change_records(request({"unsupported_filter": ["value"]}))
    except ValidationError:
        invalid_request_rejected = True
    else:
        raise AssertionError("Schema-invalid query was accepted")

    print(
        json.dumps(
            {
                "status": "PASS",
                "all_change_count": all_changes["result_count"],
                "combined_filter_count": groundfloor_walls["result_count"],
                "empty_result_count": geometry["result_count"],
                "invalid_request_rejected": invalid_request_rejected,
                "invalid_change_type_rejected": invalid_change_type_rejected,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
