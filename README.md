# BIMChange-Agent

Research prototype for evidence-grounded IFC/BIM revision analysis using deterministic tools and AI agents.

> **Status:** Gate 1 technical feasibility study. The repository does not yet contain an IFC revision-analysis agent or validated performance results.

## Research Goal

BIMChange-Agent explores whether an AI agent can use deterministic IFC comparison and query tools to produce revision explanations that are accurate, traceable, and useful to AEC practitioners.

The proposed workflow will be evaluated against simpler baselines. Every material change claim should be traceable to IFC entities and deterministic tool output. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the research questions, proposed workflow, scope, and decision gates.

## Currently Verified

The following limited feasibility result has been reproduced on Windows:

- Python 3.13.15 (64-bit);
- IfcOpenShell 0.8.5 installed from PyPI;
- successful loading of a public IFC4 structural sample;
- deterministic reporting of the file hash, schema, total entity count, and selected entity-type counts.

The current sample contains 407 IFC entities, including six beams, four walls, and one footing. It has only one building storey and contains no columns or slabs, so it is an initial loading sample rather than the final benchmark model.

## Not Yet Implemented

- IFC version-difference detection;
- controlled revision generation;
- a normalized change-record schema;
- natural-language revision queries;
- an LLM or agent workflow;
- an independent validator;
- baseline experiments or performance evaluation.

## Quick Start on Windows

Prerequisite: Python 3.13 (64-bit). The current environment was validated with Python 3.13.15.

```powershell
git clone https://github.com/delongwangshu49-hub/bimchange-agent.git
cd bimchange-agent
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\check_ifc.py
```

The smoke test prints a JSON summary. The absolute file path will depend on the local checkout, while the checked-in sample's SHA-256 should be:

```text
68be722391e7aaa53bb9278645a02aa4b6382f13cc07548a1612e9b1dc3def67
```

You can inspect another IFC file by passing its path:

```powershell
.\.venv\Scripts\python.exe scripts\check_ifc.py C:\path\to\model.ifc
```

## Data and Licensing

The initial sample is sourced from the buildingSMART `Sample-Test-Files` repository and remains licensed under Creative Commons Attribution 4.0 International (CC BY 4.0). Its source, attribution, retrieval date, and checksum are recorded in [data/README.md](data/README.md).

The repository's MIT license applies to the original project code and documentation. It does not replace the sample dataset's original license.

## Scope and Safety

This research prototype is not a substitute for professional BIM coordination, engineering review, structural-safety assessment, or formal regulatory-compliance checking. No such conclusions should be inferred from language-model output.
