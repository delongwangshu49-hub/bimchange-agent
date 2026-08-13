# Research implementations

This directory contains isolated, offline research implementations that build on deterministic BIMChange-Agent artifacts without changing frozen release contracts.

- `r1_traceability/` generates and verifies fail-closed evidence manifests for supported Change Records and contains the controlled tamper acceptance harness.
- `r2_external_validity/` performs path-free inventory of authorised local sample roles and evaluates an IFC4 A/B/C replication against its change ledger and R1 acceptance evidence.

Local project models, absolute paths, credentials, and temporary external-sample results are not repository inputs. The deterministic Change Records remain the source of truth. The code makes zero model/API calls.

Research results are bounded technical evidence. They do not establish general IFC compatibility, professional engineering validation, or population-level user benefit.
