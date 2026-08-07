# Gate 3 Evaluation Contract

## Purpose

This document fixes the first development question set and machine-scoring contract before any language model is selected or evaluated. It prevents the model implementation from silently redefining which answers count as correct.

The contract is a Gate 3 preparation artifact, not an agent result. No LLM, paid API, or model comparison was used to create the reference answers or the reported scoring smoke tests.

## Fixed Pilot Questions

`evals/questions/gate3-questions.json` contains eight English questions derived from the three verified Gate 2 Change Records:

| Question | Category | Expected evidence |
|---|---|---|
| `gate3-q01-summary` | Summary | All three records |
| `gate3-q02-added` | Added-element lookup | Added beam |
| `gate3-q03-deleted-wall-storey` | Multi-filter lookup | Deleted wall on `00 groundfloor` |
| `gate3-q04-property` | Property before/after | Beam `IsExternal` change |
| `gate3-q05-beams` | Entity-type filter | Added and modified beams |
| `gate3-q06-storey` | Storey filter | Deleted wall only |
| `gate3-q07-no-geometry` | Negative control | No records; `not_found` |
| `gate3-q08-safety-boundary` | Evidence boundary | Deleted-wall record; `insufficient_evidence` |

The questions cover simple retrieval, combined filters, summaries, explicit absence, and a question that cannot be answered from revision records alone. The set is intentionally small and is only the development pilot; it is not yet the final benchmark described in the project plan.

## Deterministic Reference Answers

`scripts/generate_gate3_reference_answers.py` validates the question file, applies each structured selection to `data/ground_truth/gate2-change-records.json`, and writes `evals/reference_answers/gate3-reference-answers.json`.

Each answer contains:

- one of `answered`, `not_found`, or `insufficient_evidence`;
- a human-readable reference answer;
- the complete selected Change Records, including GUIDs, locations, old/new values, and deterministic evidence selectors;
- explicit limitations where the records do not support a stronger conclusion.

The artifact stores hashes for both the question set and the source Change Records. Both question and answer files are validated with Draft 2020-12 JSON Schemas.

## Machine Scoring

`scripts/score_gate3_answers.py` compares a candidate answer artifact with the fixed reference. It reports:

- schema compliance;
- answer-status accuracy;
- exact match accuracy for status plus structured evidence;
- micro precision, recall, and F1 over exact evidence records;
- per-question results.

The scorer deliberately does not score free-text wording. A later independent validator must check whether natural-language claims are supported by the cited records. Until that validator exists, a candidate cannot be described as fully evidence-grounded merely because its structured fields score well.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts\generate_gate3_reference_answers.py
.\.venv\Scripts\python.exe scripts\score_gate3_answers.py
.\.venv\Scripts\python.exe scripts\test_gate3_scoring.py
```

The self-score must produce `1.0` for status, exact match, and evidence precision/recall/F1 because the reference is compared with itself. This is only a scorer wiring check and is not an agent performance result.

The test script also removes one expected record from a copied answer and confirms that exact-match accuracy falls below `1.0`. It then supplies an invalid status and confirms that the JSON Schema rejects the artifact.

## Decisions Deferred for Review

Before running an agent experiment, the following must be reviewed and fixed:

- the minimal deterministic tool interface exposed to the agent;
- the exact separation between Direct LLM, Tool-Using Agent, and Proposed workflow;
- the independent free-text claim validator;
- model provider and model version;
- API-key handling, run count, estimated cost, and stopping rules;
- whether the eight-question pilot is sufficient for development before expanding the final benchmark.

No API key should be added to the repository or requested until that review is complete.
