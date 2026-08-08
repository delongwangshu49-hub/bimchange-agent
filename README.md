# BIMChange-Agent / BIM 变更分析智能体

Evidence-grounded IFC/BIM revision analysis with deterministic tools and AI agents.

基于确定性工具与 AI 智能体、可追溯到 IFC 证据的 BIM 版本变更分析。

> **Status:** Gates 1–3 are complete for the controlled development scope. Gate 4—independent evaluation and release preparation—is next.
>
> 受控开发范围内的 Gate 1–3 已完成；下一阶段为 Gate 4，即独立评测与发布准备。

## Overview / 项目概述

BIMChange-Agent explores whether an AI agent can turn deterministic IFC comparison results into accurate, traceable revision explanations for AEC practitioners. Material claims are linked to structured Change Records rather than inferred from fluent text alone.

BIMChange-Agent 探索 AI 智能体能否将确定性的 IFC 比较结果转化为面向 AEC 从业者的准确、可追溯版本说明。关键结论需关联结构化 Change Record，而不是仅依赖语言模型生成的流畅文本。

The repository currently contains a reproducible Windows pipeline for loading IFC files, generating controlled revisions, detecting and normalizing changes, querying Change Records, running three model workflows, and scoring structured evidence.

本仓库目前包含一套可在 Windows 上复现的流程：读取 IFC、生成受控版本、检测并规范化变更、查询 Change Record、运行三种模型工作流，以及评估结构化证据。

## Current Progress / 当前进度

- **Gate 1 — Technical feasibility:** IfcOpenShell and IfcDiff load a public IFC4 model and verify a controlled property change.
  IfcOpenShell 与 IfcDiff 已能读取公开 IFC4 模型，并验证受控属性变更。
- **Gate 2 — Data and reference answers:** one added beam, one deleted wall, and one property modification are normalized into three auditable Change Records.
  一个新增梁、一个删除墙和一个属性修改已规范化为三条可审计的 Change Record。
- **Gate 3 — Agent prototype:** Direct LLM, Tool-Using Agent, and Proposed workflows run against the same eight-question development set with common schemas and scoring.
  Direct LLM、Tool-Using Agent 与 Proposed 三种流程已在同一组八题开发集上运行，并采用统一 Schema 与评分方式。
- **Gate 4 — Next:** freeze the current contracts, create an independent held-out revision set, repeat the comparison, analyze failures, and prepare release materials.
  冻结当前契约，建立独立留出版本与问题集，重复对比实验，分析失败案例并准备发布材料。

## Gate 3 Development Snapshot / Gate 3 开发集概览

All retained runs used DeepSeek V4 Flash with the same eight development questions and one retained answer per question and condition.

所有保留运行均使用 DeepSeek V4 Flash，并采用相同的八道开发问题；每个问题与实验条件保留一次最终答案。

| Workflow / 工作流 | Completion / 完成率 | Status accuracy / 状态准确率 | Exact match / 精确匹配 | Change F1 / 变更 F1 | Evidence support / 证据支持率 |
|---|---:|---:|---:|---:|---:|
| Direct LLM | 100% | 87.5% | 37.5% | 0.600 | 0.700 |
| Tool-Using Agent | 100% | 100% | 87.5% | 0.947 | 1.000 |
| Proposed | 100% | 100% | 100% | 1.000 | 1.000 |

These figures are preliminary development-set results produced after iterative prompt and contract debugging. They are not held-out benchmark results, do not estimate variance, and must not be interpreted as general model performance.

上述数据是在提示词与契约反复调试后得到的初步开发集结果，并非独立留出基准；目前没有方差估计，也不能据此推断模型的通用性能。

See [Gate 3 development results](docs/gate3-development-results.md) for the recorded configuration, cost, failure modes, and limitations. The machine-readable summary is stored in [evals/results/development/summary.json](evals/results/development/summary.json).

运行配置、成本、失败模式与局限详见 [Gate 3 开发集结果](docs/gate3-development-results.md)；机器可读汇总位于 [evals/results/development/summary.json](evals/results/development/summary.json)。

## Reproduce Locally / 本地复现

Prerequisite: 64-bit Python 3.13 on Windows. The current environment was validated with Python 3.13.15.

前置条件：Windows 上的 64 位 Python 3.13；当前环境使用 Python 3.13.15 完成验证。

```powershell
git clone https://github.com/delongwangshu49-hub/bimchange-agent.git
cd bimchange-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_gate1_diff.py
.\.venv\Scripts\python.exe scripts\run_gate2_diff.py
.\.venv\Scripts\python.exe scripts\generate_gate3_reference_answers.py
.\.venv\Scripts\python.exe scripts\test_gate3_scoring.py
.\.venv\Scripts\python.exe scripts\test_change_query.py
.\.venv\Scripts\python.exe scripts\test_gate3_candidate_contract.py
.\.venv\Scripts\python.exe scripts\test_gate3_workflows.py
```

The Gate 3 runner defaults to a dry run and sends no API request. Live runs require a locally stored `DEEPSEEK_API_KEY`; copy `.env.example` to the ignored `.env.local`, or use the hidden-input helper.

Gate 3 运行器默认仅执行 dry run，不会发送 API 请求。实时运行需要在本地配置 `DEEPSEEK_API_KEY`；可将 `.env.example` 复制为已被忽略的 `.env.local`，或使用隐藏输入辅助脚本。

```powershell
.\scripts\set_deepseek_key.ps1
.\.venv\Scripts\python.exe scripts\run_gate3_workflows.py
# Add --live only when an API call and its cost are intended.
```

Never commit API keys, `.env.local`, diagnostic runs, or smoke-test outputs.

请勿提交 API 密钥、`.env.local`、诊断运行或冒烟测试输出。

## Repository Guide / 仓库导览

- `src/bimchange_agent/` — deterministic query, evidence validation, and Gate 3 runner logic.
  确定性查询、证据验证与 Gate 3 运行逻辑。
- `schemas/` — versioned JSON Schemas for Change Records, requests, answers, and claim validation.
  Change Record、请求、答案及声明验证所用的版本化 JSON Schema。
- `scripts/` — reproducible generation, comparison, scoring, testing, and workflow commands.
  可复现的生成、比较、评分、测试与工作流命令。
- `evals/` — fixed development questions, references, inputs, and retained result artifacts.
  固定的开发问题、参考答案、输入与保留结果。
- `docs/` — experiment contracts, evidence, findings, and limitations.
  实验契约、证据、发现与局限说明。

The public roadmap and decision gates are described in [PROJECT_PLAN.md](PROJECT_PLAN.md).

公开路线图与决策门详见 [PROJECT_PLAN.md](PROJECT_PLAN.md)。

## Data, License, and Safety / 数据、许可与安全边界

The initial IFC sample comes from buildingSMART's `Sample-Test-Files` repository under CC BY 4.0. Source, attribution, retrieval date, and checksum are recorded in [data/README.md](data/README.md). Original project code and documentation are licensed under MIT.

初始 IFC 样本来自 buildingSMART 的 `Sample-Test-Files` 仓库，采用 CC BY 4.0 许可；来源、署名、获取日期与校验和记录于 [data/README.md](data/README.md)。项目原创代码与文档采用 MIT 许可。

This research prototype is not a substitute for professional BIM coordination, engineering review, structural-safety assessment, or formal regulatory-compliance checking.

本研究原型不能替代专业 BIM 协调、工程审查、结构安全评估或正式法规合规检查。
