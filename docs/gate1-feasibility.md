# Gate 1 Technical Feasibility

## Outcome

Gate 1 passed on Windows. The project can load a public IFC4 model, generate a controlled second version, detect a deterministic property difference with the official IfcDiff tool, and verify the detected result against generated ground truth.

This is a feasibility result, not an evaluation of the proposed agent workflow.

## Environment

- Windows
- Python 3.13.15 (64-bit)
- IfcOpenShell 0.8.5
- IfcDiff 0.8.5

## Input

The source model is buildingSMART's `Building-Structural.ifc` sample. Its source, CC BY 4.0 attribution, retrieval date, and checksum are recorded in [`data/README.md`](../data/README.md).

The model uses the IFC4 schema and contains 407 entities. It is small and has only one building storey, so it is suitable for a loading and tooling smoke test but is not yet the final benchmark model.

## Controlled Change

`scripts/generate_gate1_revision.py` selects an existing `IfcBeam` by GlobalId and modifies one property:

| Field | Value |
|---|---|
| GlobalId | `2ddLgAnQf4mBfh5IpUp54U` |
| Property | `Pset_BeamCommon.IsExternal` |
| Previous value | `false` |
| Updated value | `true` |

The generator checks the expected entity type and previous value before writing the revised model. It also records both file hashes and the expected change in `data/ground_truth/gate1-property-change.json`.

## Deterministic Comparison

IfcDiff is run with property comparison enabled. The resulting JSON reports:

- zero added elements;
- zero deleted elements;
- exactly one changed GlobalId;
- the expected property path;
- the expected previous and updated values.

`scripts/verify_gate1_diff.py` checks the file hashes, IfcDiff output, and property values in both IFC files. `scripts/run_gate1_diff.py` executes generation, comparison, and verification as one reproducible command.

```powershell
.\.venv\Scripts\python.exe scripts\run_gate1_diff.py
```

A successful run ends with `"status": "PASS"`.

## Negative Result

The first exploratory revision changed only the target beam's direct `Name` attribute. With the default IfcDiff invocation used in that test, no change was reported. The result was treated as a failed detection attempt, not as evidence of success.

The retained Gate 1 test therefore uses an existing property-set value and explicitly enables IfcDiff's `property` relationship comparison. Future work must distinguish tool configuration limits from unsupported change categories instead of assuming that every IFC attribute is detected automatically.

## Limitations and Next Gate

Gate 1 covers one property modification only. It does not yet validate:

- added or deleted elements;
- geometry changes;
- spatial-container or aggregation changes;
- multiple simultaneous revisions;
- larger or multi-storey models;
- a normalized project-specific change schema;
- natural-language queries or agent behavior.

Gate 2 will expand the controlled revision set and determine whether reference answers can be generated automatically without subjective engineering judgments.
