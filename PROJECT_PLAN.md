# BIMChange-Agent: Public Project Plan

> Status: Feasibility study. No experimental results or performance claims have been validated yet.  
> Last updated: 2026-08-07

## Overview

Building projects often contain multiple revisions of the same BIM model. Although deterministic IFC tools can identify low-level differences between model versions, their outputs may be difficult for project participants to interpret. Asking a language model to explain a model directly introduces a different risk: statements may be fluent but unsupported by the underlying IFC data.

BIMChange-Agent is a research prototype exploring whether an AI agent can use deterministic IFC comparison and query tools to produce revision explanations that are accurate, traceable, and useful to AEC practitioners.

The central research question is:

> Can an AI agent transform deterministic IFC revision data into natural-language change explanations while preserving traceable evidence for every material claim?

## Intended Users

- BIM coordinators;
- architects and engineers reviewing model updates;
- project managers;
- design reviewers;
- other AEC practitioners who need to understand model revisions without inspecting raw IFC structures.

## Research Questions

1. Does grounding the workflow in deterministic IFC tools improve change-identification accuracy compared with a direct language-model baseline?
2. Does a separate validation step improve evidence-citation accuracy and multi-step task success?
3. Does packaging the workflow as a repeatable agent skill improve tool selection and output consistency?
4. Do the reliability gains justify the additional latency and model-call cost?

These are research questions, not assumed conclusions. They will be answered through controlled experiments.

## Proposed Workflow

The initial design consists of five stages:

1. **Query planning** — identify the requested change types, IFC entities, storeys, and required tools.
2. **Deterministic IFC analysis** — use established IFC libraries or comparison utilities to inspect the two model versions.
3. **Structured change records** — normalize detected changes into records containing entity type, GlobalId, location, change category, and before/after values where available.
4. **Evidence-grounded explanation** — translate the structured records into language suitable for AEC users.
5. **Validation** — check generated statements against the underlying change records and report unsupported or indeterminate claims.

The architecture remains provisional until the feasibility study is complete.

## Evidence Requirements

Where available, each reported change should include:

- IFC entity type;
- GlobalId/GUID;
- associated building storey;
- change category, such as added, removed, property-modified, geometry-modified, or relationship-modified;
- previous and updated values;
- the deterministic tool output supporting the statement;
- an explanation for the user;
- an explicit indication when the evidence is insufficient.

The prototype will not present language-model output as a structural-safety conclusion or a formal code-compliance determination.

## Minimum Viable Prototype

The first validated prototype is expected to:

- read two openly licensed or reproducibly generated IFC model versions on Windows;
- detect additions, removals, and at least one modification category;
- normalize tool output into structured change records;
- support several categories of natural-language revision queries;
- cite IFC evidence in its answers;
- include at least one independent validation step;
- use a fixed question set with reproducible reference answers;
- compare two baselines with the proposed workflow;
- report accuracy, unsupported-claim rate, latency, and failure categories.

## Evaluation Plan

Three workflows are planned for comparison:

- **Direct LLM baseline:** a language model receives a limited model summary without access to specialist comparison tools.
- **Tool-using baseline:** an agent can call IFC comparison and query tools but has no independent validation stage.
- **Proposed workflow:** query planning, deterministic tools, structured evidence, explanation, and validation.

Planned evaluation measures include:

- task success rate;
- precision, recall, and F1 for change identification;
- evidence-citation accuracy;
- unsupported-claim rate;
- multi-step query success rate;
- output-schema compliance;
- response latency;
- estimated model-call cost;
- manual correction count;
- failure-type distribution.

## Data and Reproducibility

The project will use public, clearly licensed, or programmatically generated IFC data. When redistribution is not permitted, the repository will contain source links and reproducible preparation scripts instead of the original files.

Controlled revisions will be generated where practical so that the reference changes are known and auditable. Experimental results will record the relevant configuration, model identifier, date, and code revision.

No confidential employer, internship, client, or project data will be used.

## Scope Boundaries

This project does not aim to:

- train a foundation model;
- reproduce a complete BIM authoring or coordination platform;
- replace professional engineering review;
- perform formal structural-safety or regulatory-compliance certification;
- treat a complex user interface as the primary research contribution;
- claim effectiveness before baseline testing is complete.

## Decision Gates

### Gate 1 — Technical Feasibility

Confirm that the selected IFC tooling can be installed and run on Windows, open a public IFC model, and detect deterministic differences between two versions.

### Gate 2 — Data and Reference Answers

Confirm that controlled model revisions and auditable reference answers can be generated without relying on subjective engineering judgments.

### Gate 3 — Agent Prototype

Confirm that the workflow selects appropriate tools, cites real IFC evidence, and supports a minimum baseline comparison.

### Gate 4 — Evaluation and Release

Complete the fixed evaluation set, reproducible experiments, failure analysis, documentation, and demonstration materials.

## Current Status

Gate 1 technical feasibility is complete on Windows with Python 3.13.15, IfcOpenShell 0.8.5, and IfcDiff 0.8.5. A public IFC4 sample can be loaded, a controlled property revision can be generated, and the resulting change can be detected and verified against generated ground truth.

This result covers one property change in a small single-storey sample. It does not establish performance on additions, deletions, geometry changes, relationship changes, larger models, or natural-language queries. Gate 2 will determine whether a broader controlled revision set and auditable reference answers are viable.
