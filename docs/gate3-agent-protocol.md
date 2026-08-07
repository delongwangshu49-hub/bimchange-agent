# Gate 3 Cross-Workflow Protocol

## Purpose

This protocol fixes comparable inputs, outputs, tool access, and deterministic checks for the three planned workflows before a model or API is selected.

No model was called to produce or test these artifacts. The current results verify data plumbing and scoring behavior only.

## Experimental Conditions

| Condition | Input available to the model | Tool access | Independent validation | Repair |
|---|---|---|---|---|
| Direct LLM | One question plus the fixed non-diff model-pair summary | None | None | None |
| Tool-Using Agent | One question plus the Change Record query-tool contract | One deterministic query per question | None | None |
| Proposed | Same question and query-tool contract as Tool-Using Agent | One deterministic query per question | Structured prediction and evidence validation | At most one controlled repair |

The Tool-Using and Proposed conditions receive the same query capability. The proposed condition differs only through its independent validation and one bounded repair opportunity.

## Direct LLM Input

`evals/inputs/development/gate3-model-pair-summary.json` is generated separately from each IFC version. It contains:

- `IfcElement` type, GlobalId, Name, and Tag;
- direct spatial container and an explicit building storey when present;
- scalar property-set values.

It excludes:

- precomputed differences and Change Records;
- geometry and placement coordinates;
- materials, classifications, quantities, and nested property values;
- engineering, safety, and compliance judgments.

The artifact contains source and revised inventories rather than a `changes` field. The Direct LLM must infer differences from those two inventories.

## Common Prediction Format

All three conditions must return `schemas/candidate-answer.schema.json`. The common prediction facts are:

- change type;
- IFC entity type and GlobalId;
- spatial location;
- changed field when applicable;
- old and new values;
- workflow-accessible evidence references.

The schema does not require a candidate to know the project-internal `change_id`. A Direct LLM can cite version-specific model-summary entries, while a tool-using workflow can cite a returned Change Record. This prevents the output contract from granting one condition an impossible requirement.

## Separate Scoring Dimensions

`scripts/score_gate3_predictions.py` compares workflow-neutral prediction facts with `evals/reference_answers/gate3-canonical-predictions.json`. Evidence references are excluded from the semantic fact identity.

The scorer reports separately:

- schema compliance;
- answer-status accuracy;
- semantic exact-match accuracy;
- change precision, recall, and F1;
- deterministic evidence-support rate;
- status consistency.

This separation allows a run to identify the right change but cite the wrong source, or cite a real source while stating the wrong change. Those are distinct failure modes.

## Independent Evidence Validation

`scripts/validate_candidate_answers.py` does not use the natural-language reference answer. It checks structured predictions directly against the cited source:

- model-summary evidence must cite the correct version, GlobalId, presence or absence, location, property field, and value;
- query evidence must cite a real Change Record whose semantic fact exactly matches the prediction;
- `answered`, `not_found`, and `insufficient_evidence` must obey basic result and limitation rules.

The validator reports `free_text_semantics_validated: false`. It does not claim that arbitrary prose is entailed by structured evidence. That remaining check requires a separately approved strategy, such as claim-level model judging with manual audit or deterministic rendering from verified facts.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts\generate_gate3_direct_input.py
.\.venv\Scripts\python.exe scripts\generate_gate3_reference_answers.py
.\.venv\Scripts\python.exe scripts\test_gate3_candidate_contract.py
```

The contract test confirms that:

- correct model-summary citations support every canonical prediction;
- correct query citations support every canonical prediction;
- corrupting one citation reduces evidence support without changing change F1;
- removing one prediction reduces change recall;
- an invalid workflow value is rejected by the JSON Schema.

These are harness tests, not model performance figures.

## Remaining Approval Point

Before the first model call, the project must select:

- the free-text validation strategy;
- model provider and exact model version;
- temperature and other randomness controls;
- repetitions per question and workflow;
- API-key setup through local environment variables only;
- estimated call volume, cost ceiling, retry policy, and stopping rules.

The held-out evaluation set must be created only after prompts, schemas, and workflow logic are frozen.
