# Gate 3 Cross-Workflow Protocol

## Purpose

This protocol fixes comparable inputs, outputs, tool access, and deterministic checks for the three planned workflows.

The contracts and offline tests described below do not constitute model-performance results.

## Locked Development Configuration

- Provider: DeepSeek;
- Model: `deepseek-v4-flash` for all three development conditions;
- API: DeepSeek's Responses-compatible API with strict JSON Schema output;
- Reasoning effort: `high` for all three conditions;
- Maximum answer-generation output per request: 16,000 tokens, including provider reasoning tokens;
- Proposed's auxiliary claim-validator call may use up to 16,000 tokens because its reasoning and complete claim ledger are not part of the cross-condition answer-generation comparison;
- Structured generations are instructed to return exactly one JSON object with no surrounding text or second object; local Schema validation remains authoritative;
- Response storage: unavailable and always reported as `store: false` by the provider;
- Repetitions: once per development question and condition;
- Transient retries: at most two; schema and factual failures are not infrastructure retries;
- A provider-success response with completely empty structured output is treated as a documented DeepSeek JSON-output transient and may be retried; malformed non-empty JSON is not retried;
- Development cost ceiling: configurable, with a default hard ceiling of USD 0.50;
- `deepseek-v4-pro` is reserved for a later cross-model replication after the Flash development workflow is frozen.

The current Responses-compatible API does not expose a fixed seed in this runner. The omission is recorded rather than described as deterministic sampling. DeepSeek currently maps `low` and `medium` reasoning effort to `high`, so the runner records `high` explicitly.

## Experimental Conditions

| Condition | Input available to the model | Tool access | Independent validation | Repair |
|---|---|---|---|---|
| Direct LLM | One question plus the fixed non-diff model-pair summary | None | None | None |
| Tool-Using Agent | One question plus the Change Record query-tool contract | One deterministic query per question | None | None |
| Proposed | Same question and query-tool contract as Tool-Using Agent | One deterministic query per question | Structured prediction and evidence validation | At most one controlled repair |

The Tool-Using and Proposed conditions receive the same query capability. The proposed condition differs only through its independent validation and one bounded repair opportunity.

The query contract constrains `change_types` to the lowercase development vocabulary: `added`, `deleted`, `property_modified`, and the negative-control category `geometry_modified`. Case variants and unknown change types are rejected before query execution rather than interpreted as an empty result.

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

The deterministic evidence validator continues to report `free_text_semantics_validated: false`. The Proposed runner therefore adds a separate same-model validation call that decomposes the answer into atomic claims and labels each `supported`, `unsupported`, or `indeterminate` using only the returned Change Records and structured predictions. It also performs a reference-free deterministic completeness check: the prediction facts must exactly cover the Change Records returned by the model-selected query. An initial candidate-Schema failure, missing or unexpected facts, an `unsupported` claim, an evidence failure, or a status violation permits one controlled repair. Tool-Using Agent does not receive this repair path. All eight development questions remain subject to manual audit; the model judge is not treated as ground truth.

## Minimal Runners

`scripts/run_gate3_workflows.py` implements the three conditions. Without `--live` it only validates and prints the locked run plan; no API request is sent. With `--live`, results and safe usage metadata are written under `evals/results/development/`. `DEEPSEEK_API_KEY` is read from the process environment or the ignored local `.env.local` file and is never written to result artifacts.

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

## Post-Development Freeze

The paid smoke test and complete eight-question development run are complete. Their retained artifacts and limitations are documented in `docs/gate3-development-results.md` and `evals/results/development/summary.json`.

Before held-out evaluation, the prompts, schemas, and workflow logic must be frozen. The held-out revision and question set must be created separately, and held-out outcomes must not be used to tune the frozen workflow. Repeated runs, uncertainty reporting, and failure analysis belong to Gate 4.

On Windows, `scripts/set_deepseek_key.ps1` prompts for a fresh key with hidden input and replaces `.env.local` without printing the key. A key pasted into chat, an issue, a commit, or a screenshot must be revoked rather than reused.
