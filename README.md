# BIMChange-Agent / BIM 变更分析智能体

Evidence-grounded IFC/BIM revision analysis with deterministic tools and AI-agent evaluation.

基于确定性工具、结构化证据与 AI 智能体评测的 IFC/BIM 版本变更分析研究原型。

> **Current status — v0.1.0:** Gates 1–4 are complete for the controlled research scope. The Gate 4 held-out evaluation, private review, full reproducibility payload, public PR, and merge are complete. Read the [final bilingual Gate 4 report](docs/gate4-held-out-results.md).
>
> **当前状态 — v0.1.0：** 受控研究范围内的 Gate 1–4 已全部完成。Gate 4 留出评测、私人审查、完整复现载荷、公开 PR 与合并闭环均已完成。详见[最终 Gate 4 双语报告](docs/gate4-held-out-results.md)。

## What this is / 产品定位

BIMChange-Agent is currently a **source-run research prototype and developer toolkit**. It demonstrates an auditable path from IFC revision evidence to structured, evidence-linked answers and includes the complete controlled Gate 4 evaluation artifacts.

BIMChange-Agent 当前是一个**从源码运行的研究原型与开发工具包**。它展示了从 IFC 版本证据到结构化、可追溯答案的可审计路径，并公开了完整的受控 Gate 4 评测产物。

It is **not** currently a pip-installable package, desktop application, Revit plug-in, hosted service, or production-ready command-line product. In particular, the repository does not yet provide a supported one-command converter for arbitrary pairs of real-world IFC files into normalized Change Records.

它目前**不是**可通过 pip 安装的软件包、桌面应用、Revit 插件、托管服务或生产级命令行产品。尤其需要注意：仓库尚未提供将任意两份真实项目 IFC 一键转换为规范化 Change Records 的受支持通用入口。

## What works now / 当前可用能力

| Capability / 能力 | Status / 状态 | Input → output / 输入 → 输出 |
|---|---|---|
| IFC inspection / IFC 检查 | Directly usable offline / 可直接离线使用 | One IFC path → schema, hash, entity totals and selected entity counts / 单个 IFC 路径 → Schema、哈希、实体总数与分类计数 |
| Change Record query / 变更记录查询 | Directly usable offline / 可直接离线使用 | JSON filter request + schema-valid Change Record artifact → validated JSON matches with source hash and evidence / JSON 筛选请求 + 合规 Change Record 产物 → 带来源哈希和证据的校验后 JSON 结果 |
| Controlled fixture pipeline / 受控样例流程 | Reproducible offline / 可离线复现 | Included IFC fixture generators → revised IFC, IfcDiff output, normalized Change Records and verification / 仓库内样例生成器 → 修订 IFC、IfcDiff 输出、规范化 Change Records 与验证结果 |
| Gate 4 evaluation / Gate 4 评测 | Published and reproducible offline / 已发布且可离线复现 | Frozen runs, scores and audit artifacts → verified summary and bilingual report / 冻结运行、评分及审核产物 → 已验证汇总与双语报告 |
| AI workflows / AI 工作流 | Experimental / 实验性 | Frozen prompts and structured inputs → schema-validated candidate answers; live use requires an explicitly configured provider key and cost authorization / 冻结提示词与结构化输入 → 通过 Schema 校验的候选答案；实时使用需要显式配置供应商密钥并授权费用 |
| Arbitrary IFC-to-Change-Record conversion / 任意 IFC 到 Change Record 转换 | Not productized / 尚未产品化 | No supported general-purpose entry point yet / 尚无受支持的通用入口 |

## Quickstart / 快速开始

Validated environment: 64-bit Python 3.13 on Windows (the release was verified with Python 3.13.15). Commands below are offline and make no model/API calls.

已验证环境：Windows 64 位 Python 3.13（本发布使用 Python 3.13.15 验证）。以下命令完全离线，不会调用模型/API。

```powershell
git clone https://github.com/delongwangshu49-hub/bimchange-agent.git
cd bimchange-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Inspect the included IFC file.
.\.venv\Scripts\python.exe scripts\check_ifc.py

# Query the included Change Records with a real example request.
.\.venv\Scripts\python.exe scripts\query_change_records.py examples\query-added-beams.json

# Verify both quickstart commands end to end.
.\.venv\Scripts\python.exe scripts\test_quickstart.py
```

The query returns one matching `IfcBeam` addition, including its stable change ID, GlobalId, old/new values, and evidence selector. To query another schema-valid Change Record artifact, add `--change-records path\to\change-records.json`.

查询命令会返回一条匹配的 `IfcBeam` 新增记录，其中包含稳定的变更 ID、GlobalId、新旧值和证据选择器。若要查询另一份符合 Schema 的 Change Record 产物，可添加 `--change-records path\to\change-records.json`。

See [Quickstart and usage guide](docs/quickstart.md) for complete inputs, output examples, Gate 4 verification commands, safe dry-run behavior, and current product boundaries.

完整输入、输出示例、Gate 4 验证命令、安全 dry-run 行为与当前产品边界，详见[快速开始与使用说明](docs/quickstart.md)。

## Gate 4 release result / Gate 4 发布结果

The controlled held-out fixture contains 40 English questions, three frozen workflows, and three repetitions: 360 primary executions in total. Across 120 scheduled executions per workflow, Proposed achieved 96.67% semantic exact match and 97.90% change F1; Tool-Using Agent achieved 84.17% and 91.85%; Direct LLM achieved 54.17% and 63.16%. These are results from one independently constructed synthetic fixture, not a universal BIM benchmark.

受控留出样例包含 40 道英文问题、三个冻结工作流和三次重复，共 360 次主执行。每个工作流的 120 次计划执行中，Proposed 的语义精确匹配率为 96.67%、Change F1 为 97.90%；Tool-Using Agent 分别为 84.17% 和 91.85%；Direct LLM 分别为 54.17% 和 63.16%。这些结果来自一个独立构造的合成样例，并非通用 BIM 基准。

- [Final bilingual report / 最终双语报告](docs/gate4-held-out-results.md)
- [Machine-readable offline summary / 机器可读离线汇总](evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json)
- [Independent validation / 独立验证记录](evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json)
- [Post-run audit / 运行后审计](evals/audits/held_out/gate4-post-run-audit.json)
- [Release v0.1.0](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.1.0)

## Offline reproduction / 离线复现

The following checks validate the published Gate 4 artifacts without generating new model outputs:

以下检查不会生成新的模型输出，用于验证已发布的 Gate 4 产物：

```powershell
.\.venv\Scripts\python.exe scripts\verify_gate4_foundation.py
.\.venv\Scripts\python.exe scripts\verify_gate4_scores.py
.\.venv\Scripts\python.exe scripts\verify_gate4_offline_summary.py
.\.venv\Scripts\python.exe scripts\generate_gate4_results_document.py --check
```

The Gate 3 and Gate 4 workflow runners default to dry-run/offline behavior. Do not add `--live` unless a model call, provider credential, and cost are explicitly intended. No additional live calls are needed to inspect or verify this release.

Gate 3 与 Gate 4 工作流运行器默认执行 dry-run/离线路径。除非明确需要模型调用、已配置供应商凭据并接受费用，否则不要添加 `--live`。查看或验证本发布不需要任何新增实时调用。

## Repository guide / 仓库导航

- `examples/` — runnable input examples / 可运行的输入样例
- `src/bimchange_agent/` — deterministic query, evidence validation, fixture and workflow logic / 确定性查询、证据验证、样例与工作流逻辑
- `schemas/` — versioned JSON Schemas / 版本化 JSON Schema
- `scripts/` — generation, comparison, query, scoring, verification and tests / 生成、比较、查询、评分、验证与测试脚本
- `data/` — attributed source IFC plus controlled generated fixtures and Change Records / 已署名源 IFC、受控生成样例与 Change Records
- `evals/` — frozen development and Gate 4 evaluation artifacts / 冻结开发集与 Gate 4 评测产物
- `docs/` — contracts, findings, limitations and usage guidance / 契约、结果、限制与使用说明

## License and safety / 许可与安全

Original code and documentation are licensed under MIT. The initial IFC sample comes from buildingSMART's `Sample-Test-Files` repository under CC BY 4.0; source, attribution, retrieval date, and checksum are recorded in [data/README.md](data/README.md).

原创代码与文档采用 MIT 许可。初始 IFC 样本来自 buildingSMART 的 `Sample-Test-Files` 仓库，采用 CC BY 4.0 许可；来源、署名、获取日期与校验和见 [data/README.md](data/README.md)。

This research prototype is not a substitute for professional BIM coordination, engineering review, structural-safety assessment, or formal regulatory-compliance checking.

本研究原型不能替代专业 BIM 协调、工程审查、结构安全评估或正式法规合规检查。
