# R2 external-validity slice

This isolated path inventories an authorised local A/B/C IFC4 sample set and one IFC2X3 boundary sample without storing their paths or copying the models into the repository.

The preflight establishes data readiness only. IFC4 evidence replication is performed with the R1 traceability verifier. A single IFC2X3 file is an exploratory schema-boundary input, not a comparable revision pair and not evidence that the current product supports IFC2X3.

All commands are offline and make zero model/API calls.

`preflight.py` produces path-free sample metadata. `evaluate_replication.py` then checks the A/B zero-change control, B/C and A/C semantic equivalence, ledger agreement, and the R1 reproducibility/tamper evidence.

`ifc2x3_pair.py` is a separate research-only path. It first freezes an exact six-operation ledger and cross-schema field map without writing an IFC or running IfcDiff. Only then can it build two non-overwriting IFC2X3 revisions and verify byte reproducibility. Reaching `READY_FOR_PREREGISTERED_DIFF` does not itself establish an IFC2X3 diff, traceability, or product-support result.

`evaluate_ifc2x3_pair.py` may run only after that pair gate passes. It compares the fixed IfcDiff output against the preregistered GUIDs, property paths, and values, then writes research-only Change Records. A passing result remains bounded to one controlled IFC2X3 pair; R1 traceability and product support remain separate, unpassed gates.
