# Gate 3 Deterministic Tool Interface

## Outcome

The first Gate 3 tool boundary is fixed and implemented without a language model. An agent can request exact Change Records through a versioned JSON interface instead of reading the ground-truth file directly.

This is infrastructure for a future agent experiment. It does not perform natural-language interpretation, generate explanations, validate free-text claims, or report model performance.

## Tool Contract

The tool accepts a request conforming to `schemas/change-query-request.schema.json`:

```json
{
  "schema_version": "0.1.0",
  "filters": {
    "change_types": ["deleted"],
    "entity_types": ["IfcWall"],
    "building_storey_names": ["00 groundfloor"]
  }
}
```

Supported filters are:

- change type;
- IFC entity type;
- GlobalId;
- building-storey name;
- property-set name;
- property name.

All supplied filters are combined with logical AND. An empty filter object returns all records. A valid query with no matches returns an empty `results` array; it is not treated as a tool failure.

The response conforms to `schemas/change-query-response.schema.json` and contains:

- interface version;
- source Change Record path and SHA-256;
- the applied filters;
- result count;
- complete matching Change Records with deterministic evidence selectors.

The data source is host-configured and is not selectable by the agent request. This prevents a model-generated request from reading an arbitrary local path.

## Implementation

`src/bimchange_agent/change_query.py` implements validation and filtering. `scripts/run_change_query.py` is the current command-line adapter.

```powershell
.\.venv\Scripts\python.exe scripts\run_change_query.py evals\fixtures\gate3-added-query.json
```

The core query function is independent of the fixed question IDs and question wording. The reference-answer generator now reuses the same filter semantics, while the independent query tests include an entity-type request that is not tied to a question identifier.

## Tests

```powershell
.\.venv\Scripts\python.exe scripts\test_change_query.py
```

The test checks:

- all-record retrieval;
- one change-type filter;
- combined change-type, entity-type, and storey filtering;
- an arbitrary entity-type query;
- a valid zero-result geometry query;
- rejection of an unsupported request field.

## Experiment Boundaries Fixed So Far

- The eight current questions are explicitly marked as the `development` split.
- The future held-out evaluation set must use a separate artifact and must not be used to tune prompts or tool logic.
- The deterministic query tool accepts structured filters only; natural-language planning remains a model responsibility.
- Direct LLM must not receive this tool or the Change Records.
- Tool-Using Agent may call this tool but will not receive an independent answer-validation or repair step.
- Proposed workflow may call this tool and will add an independent validation step with at most one controlled repair attempt.

## Subsequent Contract Work

The following items are now fixed in [gate3-agent-protocol.md](gate3-agent-protocol.md):

- a fixed non-diff input summary for Direct LLM;
- a common prediction schema achievable by all three workflows;
- separate change-identification and evidence-support scoring;
- deterministic structured-evidence validation and its explicit free-text limitation.

Before model calls begin, the project still needs:

- the final free-text validation strategy;
- model, temperature, repetition count, budget, retry, and stopping decisions.

No API key or paid model call is required for the implemented tool layer.
