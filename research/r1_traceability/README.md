# R1 traceability slice

This isolated research path builds and verifies a deterministic evidence manifest for the bounded product Change Records without changing the frozen v0.1.0 contracts.

The first slice covers `added`, `deleted`, and `property_modified`. Verification re-runs IfcDiff with the frozen configuration, rejects duplicate JSON keys, reconstructs facts independently from the raw result and IFC models, and writes no real input paths into the manifest.

```powershell
.\.venv\Scripts\python.exe -m research.r1_traceability.cli bundle `
  --source data\raw\Building-Structural.ifc `
  --revised data\generated\Building-Structural-gate2-v2.ifc `
  --output research\r1_traceability\artifacts\gate2-controlled

.\.venv\Scripts\python.exe -m research.r1_traceability.cli verify `
  --source data\raw\Building-Structural.ifc `
  --revised data\generated\Building-Structural-gate2-v2.ifc `
  --change-records research\r1_traceability\artifacts\gate2-controlled\change-records.json `
  --raw-result research\r1_traceability\artifacts\gate2-controlled\ifcdiff.json `
  --manifest research\r1_traceability\artifacts\gate2-controlled\trace-manifest.json
```

Both commands are offline and make zero model/API calls. The acceptance evidence is technical evidence on a controlled IFC4 fixture, not a user study or a general IFC compatibility claim.
