# Gate 2 Data and Reference-Answer Validation

## Outcome

Gate 2 passed on the current controlled sample. The project can generate a multi-change IFC revision, normalize the known changes into machine-readable records, compare both model versions with IfcDiff, and verify every expected record against the models and tool output.

This result validates a small deterministic data pipeline. It is not evidence that an AI agent, natural-language explanation, or benchmark evaluation is complete.

## Controlled Revision Set

The generator applies three synthetic changes to the Gate 1 source model:

| Category | Entity | GlobalId | Controlled value |
|---|---|---|---|
| Property modified | `IfcBeam` | `2ddLgAnQf4mBfh5IpUp54U` | `Pset_BeamCommon.IsExternal`: `false` to `true` |
| Added | `IfcBeam` | `1yBs77x9XA79IerK62qUGO` | Name `Gate 2 added beam`; tag `GATE2-ADDED-BEAM` |
| Deleted | `IfcWall` | `0DyViLJJ175RvWQi1rE7a6` | Existing wall removed from the revised model |

The added beam is a deep copy of an existing sample beam with a fixed new GlobalId, name, and tag. Its geometry and placement are copied only to make the addition a valid reproducible IFC element; the overlapping placement is synthetic and has no engineering meaning. The deletion uses IfcOpenShell's product-removal API so related IFC objects are handled consistently.

No geometry-change or relationship-change case was added at this gate. Those categories remain future work because the current gate requires a stable reference set, not the largest possible list of change types.

## Minimal Change Record

`schemas/change-record.schema.json` defines version `0.1.0` of the project-specific record contract. Each controlled change records:

- a stable change identifier and category;
- IFC entity type and GlobalId;
- direct spatial container and building storey when one is actually available;
- the changed field for property modifications;
- previous and updated values, using `null` when a side is not applicable;
- the reference generator and exact deterministic result location used as evidence.

The source sample places beams directly under an `IfcBuilding`, so their `building_storey` field is explicitly `null`. The deleted wall is assigned to the model's `IfcBuildingStorey`, which is recorded. The schema does not infer a storey that the IFC relationships do not support.

## Reproducible Verification

Run the complete Gate 2 pipeline on Windows:

```powershell
.\.venv\Scripts\python.exe scripts\run_gate2_diff.py
```

The command:

1. regenerates `data/generated/Building-Structural-gate2-v2.ifc`;
2. writes `data/ground_truth/gate2-change-records.json` from the controlled operations;
3. runs IfcDiff 0.8.5 with property comparison enabled;
4. writes `evals/results/gate2-ifcdiff.json`;
5. validates the records against the JSON Schema;
6. checks file hashes, exact added/deleted/changed GUID sets, property values, entity snapshots, and spatial locations.

A passing run ends with `"status": "PASS"` and `"records_validated": 3`.

The generator fixes the new IFC relationship identifiers, normalizes generated owner-history timestamps to the source fixture's timestamp, and sorts affected IFC `SET` values before serialization. This makes repeated runs byte-for-byte reproducible; the revised IFC SHA-256 is therefore stable rather than merely self-consistent within one run.

## Scope and Limitations

The result covers one addition, one deletion, and one property modification in a small single-storey public sample. It does not validate:

- geometry-change or relationship-change detection;
- generalization to arbitrary IFC files, larger models, or multiple storeys;
- semantic importance, constructability, safety, or regulatory implications;
- natural-language questions, language-model outputs, or agent behavior;
- benchmark accuracy, unsupported-claim rate, latency, or cost.

Gate 3 can now use these records as deterministic evidence for a minimal agent workflow and baseline comparison.
