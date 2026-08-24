# R3 complete controlled research gate

This isolated path preserves the research gate used to promote three bounded R3 slices into the v0.9.0 product contract:

- `extrusion_dimension_change` for one `IfcExtrudedAreaSolid` using one `IfcRectangleProfileDef`, with independent `profile_x_m`, `profile_y_m`, and `extrusion_depth_m` reconstruction;
- `tessellated_vertex_geometry_change` for an `IfcTriangulatedFaceSet` whose topology, placement, identity, openings, and projections stay unchanged;
- `relationship_modified` for direct spatial containment, aggregation/decomposition, type assignment, and material association.

The primary detector is direct comparison of the relevant IFC entity chain. IfcDiff 0.8.5 is retained as supplemental raw evidence, not used as the sole proof. Controlled audit found that its geometry summary can miss an XDim-only symmetric profile change, its relationship comparisons can emit unrelated flags or miss the requested flag, and it has no material relationship mode.

Run the complete gate:

```powershell
python -m research.r3_complete.acceptance
```

The gate uses only generated IFC4 plus the repository-controlled R3-A tessellated fixture. It performs two clean builds, reconstructs every record, and runs a fixed 16-case tamper matrix. It makes zero model/API calls and does not establish general IFC, arbitrary geometry, exporter, or professional engineering validity.

The minimal one-pass local acceptance bundle deliberately contains exactly three files: one synthetic IFC4 source, one revised IFC4 model, and one self-contained bilingual HTML report. It covers addition, deletion, property modification, placement translation, rectangular-extrusion dimensions, topology-preserving tessellated shape change, and all four bounded relationship subtypes in a single comparison:

```powershell
python -m research.r3_complete.minimal_acceptance <new-output-directory> --bundle
```
