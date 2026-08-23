# R3-A placement-translation research slice

This isolated, offline research path tests one deliberately narrow geometry semantic: the same IFC element keeps its GlobalId, type, rotation, local canonical mesh, openings, and projections while its world ObjectPlacement translates.

IfcDiff 0.8.5 supplies only the raw `geometry_changed: true` detector flag. The candidate record independently reconstructs the old/new world origins and delta from the IFC placement graph and the shape transformation, and rejects any disagreement, rotation, local-shape change, unresolved shape, or below-threshold displacement.

Run the full gate:

```powershell
.\.venv\Scripts\python.exe -m research.r3_geometry.acceptance `
  --output research\r3_geometry\artifacts\r3a-placement-translation-acceptance.json
```

The gate includes two clean builds, exact/no-op controls, two supported translations, detector-threshold diagnostics, rotation/local-shape/missing-body negatives, and a fixed 16-case tamper matrix. It reads only the repository-controlled IFC4 fixture, writes no real paths into evidence artifacts, and makes zero model/API calls.

Passing this research gate does not modify the product Schema or establish support for general movement, dimensions, arbitrary shape changes, exporters, schemas, or professional engineering semantics.

After the research gate passes, the repository also exposes an isolated product candidate without changing the default v0.2 path:

```powershell
.\.venv\Scripts\python.exe -m bimchange_agent.cli diff-geometry-candidate source.ifc revised.ifc --output-dir candidate-output
.\.venv\Scripts\python.exe -m bimchange_agent.cli query-geometry-candidate candidate-output\geometry-change-records.json --geometry-subtype placement_translation
.\.venv\Scripts\python.exe -m bimchange_agent.cli report-geometry-candidate candidate-output\geometry-change-records.json --output candidate-report.html --language en
```

These commands remain explicit candidate entry points. They do not change the default desktop application or v0.7.0 support claim.
