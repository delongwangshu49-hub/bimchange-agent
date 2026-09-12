# R4 local spatial context proof

Status: `STANDALONE_RESEARCH_GATE_PASSED`

This directory is an isolated research proof for mapping already-verified Change
Records to small, fully local 3D scenes. It does not modify the stable R3 fact
contract and does not claim to be a general BIM viewer, a geometry-difference
viewer, or professional spatial interpretation.

## Frozen question

Can a verified Change Record be mapped to exactly one rendered object with the
same `GlobalId`, while showing only a bounded same-storey context and keeping the
model, viewer assets, and validation fully offline?

## Frozen first slice

- Inputs are two program-generated exact-IFC4 files only.
- The three target records are one deletion, one addition, and one property
  modification. They are synthetic review facts, not engineering findings.
- A deletion selects the source IFC. An addition or modification selects the
  revised IFC.
- The scene contains the target plus at most two directly-contained elements on
  the same storey, within 6 metres by world-space AABB-centre distance.
- Other changed targets are never used as context. Ties are resolved by
  `distance_m`, then `GlobalId`.
- Missing, duplicate, wrong-version, or non-unique target mappings fail closed.
- GLB nodes carry the authoritative mapping in `node.extras.global_id`; node
  names are informational only.
- The browser viewer uses repository-local Three.js assets. CDN references,
  uploads, model/API calls, absolute paths, and external project files are
  forbidden.

The machine-readable contract is in `protocol.json`, the pre-registered
synthetic changes are in `operation-ledger.json`, and the proof manifest must
validate against `spatial-context.schema.json` plus the semantic acceptance
checks.

## Technology decision

The first proof uses bounded GLB 2.0 plus Three.js, not XKT.

- IfcOpenShell 0.8.5 is already the deterministic local IFC geometry dependency.
  Its public IfcConvert documentation confirms GLB output and GlobalId-based
  inclusion, but this proof does not assume that exported GLB metadata preserves
  GlobalId. The proof exporter writes and verifies `node.extras.global_id`
  explicitly.
- glTF 2.0 defines `extras` as application-specific data. This is used only for
  traceable local mapping; geometry remains ordinary glTF.
- Three.js is MIT-licensed and its GLTFLoader supports glTF 2.0. The exact local
  distribution and license text must be pinned in the proof bundle.
- xeokit SDK/XKT remains a future scale candidate, but the current SDK is
  AGPLv3 and the direct IFC conversion route is described upstream as alpha.
  It is therefore excluded from this first permissive-license product proof.
- Qt WebEngine is not added during this research gate. Its Qt and Chromium
  redistribution obligations and package-size impact require a separate product
  decision after the standalone proof passes.

## Upstream sources checked on 2026-08-25

- IfcConvert 0.8.5: https://docs.ifcopenshell.org/ifcconvert.html
- IfcOpenShell repository and LGPL status: https://github.com/IfcOpenShell/IfcOpenShell
- glTF 2.0 specification: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- Three.js license: https://github.com/mrdoob/three.js/blob/dev/LICENSE
- Three.js GLTFLoader: https://threejs.org/docs/pages/GLTFLoader.html
- xeokit SDK licensing: https://github.com/xeokit/xeokit-sdk
- xeokit converter alpha IFC note: https://github.com/xeokit/xeokit-convert
- Qt WebEngine licensing: https://doc.qt.io/qtforpython-6/overviews/qtwebengine-licensing.html

## Gate

The standalone proof may pass only if:

1. all three pre-registered rows select the correct IFC role;
2. every scene resolves its target `GlobalId` exactly once;
3. all context nodes satisfy the frozen same-storey and distance policy;
4. two clean runs produce byte-identical IFC, GLB, manifest, and viewer assets;
5. every fixed tamper case is rejected with zero false acceptance;
6. all paths in the manifest are relative and all declared hashes verify;
7. the bundle contains no CDN/upload endpoint, credential, or model/API call;
8. the synthetic budgets in `protocol.json` pass on the recorded Windows host;
9. an actual local browser renders each row and highlights the mapped target;
10. product embedding remains `NOT_PERMITTED` until the gate result is recorded.

## Recorded result

The standalone gate passed on 2026-08-25. Two clean builds produced 17
byte-identical files. All three target GlobalIds resolved exactly once, the
fixed 10-case tamper matrix rejected 10/10 with zero false acceptance, and the
2,312,356-byte payload stayed below the frozen budget. The in-app Chromium
browser rendered the deletion from the source IFC and the addition and property
modification from the revised IFC at 1380×1080, with target/context counts of
1+2, 1+2, and 1+1 respectively and no console warning or error. The detailed
observations are in `browser-qa.json`.

This result permits freezing an isolated product-candidate mapping contract. It
does not itself permit a stable-product claim or public release.

## Product-candidate follow-on

The isolated Qt WebEngine vertical slice subsequently passed its local source,
native viewer, and private portable-package gates. Its authoritative result is
recorded in `product-candidate-acceptance.json` and
`qt-webengine-assessment.md`. Public distribution remains blocked because the
exact packaged Qt WebEngine/Chromium third-party license and redistribution
materials are not yet complete. The standalone research result above remains
unchanged; neither result expands the stable v0.9.0 support boundary.
