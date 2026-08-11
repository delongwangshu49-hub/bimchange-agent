# BIMChange-Agent Quickstart and Usage Guide

# BIMChange-Agent 快速开始与使用说明

## Product answer in one sentence

## 一句话产品定位

BIMChange-Agent v0.1.0 is a **source-run research prototype with usable offline developer tools and a fully published evaluation package**. It is not yet an installable end-user BIM product.

BIMChange-Agent v0.1.0 是一个**从源码运行、包含可用离线开发工具和完整公开评测包的研究原型**，尚不是面向终端用户的可安装 BIM 产品。

## 1. Install from a checkout

## 1. 从源码安装

The validated environment is 64-bit Python 3.13 on Windows. The v0.1.0 release was checked with Python 3.13.15 and the pinned dependencies in `requirements.txt`.

已验证环境为 Windows 64 位 Python 3.13。v0.1.0 发布使用 Python 3.13.15 和 `requirements.txt` 中的固定依赖版本完成检查。

```powershell
git clone https://github.com/delongwangshu49-hub/bimchange-agent.git
cd bimchange-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

There is no `pyproject.toml`, wheel, installer, GUI, or registered console command in this release. Run the scripts from the repository root as shown below.

本发布没有 `pyproject.toml`、wheel、安装器、GUI 或已注册的终端命令。请在仓库根目录按下列方式运行脚本。

## 2. Directly usable offline capabilities

## 2. 可直接离线使用的能力

### Inspect an IFC file

### 检查 IFC 文件

Input: one IFC file path. Output: a JSON object containing the absolute path, SHA-256, IfcOpenShell version, IFC schema, total entity count, and selected entity counts.

输入：一个 IFC 文件路径。输出：JSON 对象，包含绝对路径、SHA-256、IfcOpenShell 版本、IFC Schema、实体总数和选定类型计数。

Use the included sample:

使用仓库内样本：

```powershell
.\.venv\Scripts\python.exe scripts\check_ifc.py
```

Use your own file:

使用自己的文件：

```powershell
.\.venv\Scripts\python.exe scripts\check_ifc.py C:\path\to\model.ifc
```

Representative output fields:

代表性输出字段：

```json
{
  "sha256": "...",
  "ifcopenshell_version": "0.8.5",
  "schema": "IFC4",
  "entity_count": 407,
  "selected_entity_counts": {
    "IfcBuildingStorey": 1,
    "IfcBeam": 6,
    "IfcWall": 4
  }
}
```

Counts describe file contents; they do not determine engineering correctness or model quality.

这些计数只描述文件内容，不判断工程正确性或模型质量。

### Query structured Change Records

### 查询结构化 Change Records

Input A is a JSON request conforming to `schemas/change-query-request.schema.json`. This example asks for added beams:

输入 A 是符合 `schemas/change-query-request.schema.json` 的 JSON 请求。以下样例查询新增梁：

```json
{
  "schema_version": "0.1.0",
  "filters": {
    "change_types": ["added"],
    "entity_types": ["IfcBeam"]
  }
}
```

The same request is committed as `examples/query-added-beams.json`. Run it against the included Gate 2 Change Records:

同一请求已保存为 `examples/query-added-beams.json`。可针对仓库内 Gate 2 Change Records 运行：

```powershell
.\.venv\Scripts\python.exe scripts\query_change_records.py examples\query-added-beams.json
```

Output is a schema-validated JSON response. For the included data, `result_count` is `1`, and the result begins as follows:

输出是通过 Schema 校验的 JSON 响应。对仓库内数据，`result_count` 为 `1`，结果开头如下：

```json
{
  "schema_version": "0.1.0",
  "source": {
    "path": "data/ground_truth/gate2-change-records.json",
    "sha256": "..."
  },
  "filters": {
    "change_types": ["added"],
    "entity_types": ["IfcBeam"]
  },
  "result_count": 1,
  "results": [
    {
      "change_id": "gate2-added-001",
      "change_type": "added",
      "entity_type": "IfcBeam",
      "global_id": "1yBs77x9XA79IerK62qUGO",
      "evidence": {
        "detector": "IfcDiff 0.8.5",
        "result_file": "evals/results/gate2-ifcdiff.json",
        "selector": "added"
      }
    }
  ]
}
```

The actual output retains the complete location and old/new-value fields. Filters may use change type, IFC entity type, GlobalId, building storey name, property set, and property name. An empty `filters` object returns every record.

实际输出会保留完整位置及新旧值字段。筛选条件支持变更类型、IFC 实体类型、GlobalId、楼层名称、属性集和属性名称。空的 `filters` 对象返回全部记录。

To query another Change Record artifact that conforms to `schemas/change-record.schema.json`:

如需查询另一份符合 `schemas/change-record.schema.json` 的 Change Record 产物：

```powershell
.\.venv\Scripts\python.exe scripts\query_change_records.py request.json `
  --change-records C:\path\to\change-records.json `
  --output response.json
```

This option consumes already normalized Change Records. It does not normalize arbitrary raw IfcDiff output automatically.

该选项读取已经规范化的 Change Records，不会自动规范化任意原始 IfcDiff 输出。

### Verify the quickstart end to end

### 端到端验证快速开始

```powershell
.\.venv\Scripts\python.exe scripts\test_quickstart.py
```

Expected final fields include `"status": "PASS"`, `"query_result_count": 1`, and `"model_calls_made": 0`.

预期最终字段包括 `"status": "PASS"`、`"query_result_count": 1` 和 `"model_calls_made": 0`。

## 3. Controlled generation and evaluation reproduction

## 3. 受控生成与评测复现

### Rebuild a controlled IFC revision

### 重建受控 IFC 修订

The included Gate 2 pipeline creates a known revision, runs IfcDiff, normalizes three expected changes, and verifies the result:

仓库内 Gate 2 流程会创建一个已知修订、运行 IfcDiff、规范化三条预期变更并验证结果：

```powershell
.\.venv\Scripts\python.exe scripts\run_gate2_diff.py
```

The larger Gate 4 fixture pipeline is also offline:

规模更大的 Gate 4 样例流程同样完全离线：

```powershell
.\.venv\Scripts\python.exe scripts\run_gate4_fixture.py
.\.venv\Scripts\python.exe scripts\test_gate4_fixture.py
```

These are controlled generators tied to repository fixtures, not general converters for arbitrary IFC pairs.

这些是绑定仓库样例的受控生成器，并非面向任意 IFC 文件对的通用转换器。

### Verify the published Gate 4 package

### 验证已发布的 Gate 4 评测包

The v0.1.0 release contains the 360 frozen primary executions, 348 retained candidates, 12 recorded experimental failures, scoring artifacts, blind-audit artifacts, manifests, and the final bilingual report. The following commands verify the protected foundation, scores, summary, and report rendering without a model/API call:

v0.1.0 发布包含 360 次冻结主执行、348 个保留候选、12 个已记录实验失败、评分产物、盲审产物、manifest 和最终双语报告。以下命令无需调用模型/API，即可验证受保护基础、评分、汇总和报告生成一致性：

```powershell
.\.venv\Scripts\python.exe scripts\verify_gate4_foundation.py
.\.venv\Scripts\python.exe scripts\verify_gate4_scores.py
.\.venv\Scripts\python.exe scripts\verify_gate4_offline_summary.py
.\.venv\Scripts\python.exe scripts\generate_gate4_results_document.py --check
```

The authoritative narrative is [Gate 4 Controlled Held-Out Evaluation Results](gate4-held-out-results.md). The machine-readable summary is `evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json`.

权威叙述见 [Gate 4 受控留出评测结果](gate4-held-out-results.md)。机器可读汇总位于 `evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json`。

Published outputs reproduce the recorded evaluation. The provider's original stochastic responses cannot be regenerated byte-for-byte, and no new live run is needed to verify this release.

公开产物用于复现已记录评测。供应商原始随机响应无法逐字节重新生成，验证本发布也不需要新增实时运行。

## 4. Experimental AI workflows

## 4. 实验性 AI 工作流

The Gate 3 runner is a research harness for Direct LLM, Tool-Using Agent, and Proposed workflows. Its default is a dry run and sends no API request:

Gate 3 运行器是 Direct LLM、Tool-Using Agent 和 Proposed 三种工作流的研究评测框架。默认执行 dry run，不发送 API 请求：

```powershell
.\.venv\Scripts\python.exe scripts\run_gate3_workflows.py
```

Live mode is deliberately separate and requires a locally ignored provider key plus an explicit `--live` flag. It is not required for the quickstart or release verification. Never commit `.env.local`, keys, diagnostic runs, or smoke-test outputs.

实时模式被有意隔离，需要本地忽略的供应商密钥和显式 `--live` 参数。快速开始和发布验证均不需要实时模式。切勿提交 `.env.local`、密钥、诊断运行或冒烟测试输出。

Gate 4 live execution is a frozen evaluation protocol, not a general user-facing inference service. The published evaluation is complete; users should inspect and verify the retained artifacts rather than send more paid calls.

Gate 4 实时执行是冻结评测协议，不是面向用户的通用推理服务。公开评测已经完成；用户应检查和验证保留产物，而不是继续发送付费调用。

## 5. What is not productized

## 5. 尚未产品化的部分

This release does not provide:

本发布不提供：

- a supported general converter from any old/new IFC pair to normalized Change Records;
- a natural-language end-user CLI that accepts a project and returns a finished coordination report;
- pip/conda packaging, an installer, a GUI, Revit/authoring-tool integration, or a hosted API;
- broad validation across real projects, IFC exporters, schemas, disciplines, and operating systems;
- guarantees of engineering correctness, structural safety, or regulatory compliance.

- 从任意新旧 IFC 文件对生成规范化 Change Records 的受支持通用转换器；
- 接收项目并直接生成完整协调报告的自然语言终端工具；
- pip/conda 打包、安装器、GUI、Revit/建模软件集成或托管 API；
- 跨真实项目、IFC 导出器、Schema、专业和操作系统的广泛验证；
- 工程正确性、结构安全或法规合规保证。

If a user only has two arbitrary IFC files today, the repository can inspect each file and the installed IfcDiff dependency can produce a raw diff, but translating that raw diff into the project's normalized, evidence-linked Change Record contract still requires development work and domain review.

如果用户目前只有任意两份 IFC 文件，本仓库可以分别检查文件，已安装的 IfcDiff 依赖也能产生原始差异；但将该原始差异转换为本项目规范化、证据关联的 Change Record 契约，仍需要开发工作和领域审查。

## 6. Practical next productization phase

## 6. 可执行的下一阶段产品化计划

The smallest credible route from research prototype to an installable developer product is:

从研究原型走向可安装开发者产品的最小可信路径是：

1. Build and test a general `old.ifc + new.ifc → Change Records` normalization command, with explicit support and warning policies for added, deleted, property-modified, and geometry-modified entities.
2. Package stable commands such as `bimchange inspect`, `bimchange diff`, and `bimchange query` in a `pyproject.toml`, while keeping model-backed explanation optional.
3. Add clean-room installation tests, cross-platform CI, representative real-project fixtures, performance limits, and exporter/schema compatibility reporting.
4. Only then add a user-facing report command or UI, provider abstraction, credential handling, and professional review workflow.

1. 建立并测试通用的 `old.ifc + new.ifc → Change Records` 规范化命令，为新增、删除、属性修改和几何修改实体定义明确的支持与告警策略。
2. 通过 `pyproject.toml` 打包 `bimchange inspect`、`bimchange diff`、`bimchange query` 等稳定命令，并保持模型解释能力可选。
3. 增加干净环境安装测试、跨平台 CI、代表性真实项目样例、性能边界以及导出器/Schema 兼容性报告。
4. 完成上述基础后，再加入面向用户的报告命令或 UI、供应商抽象、凭据管理和专业审核流程。

Until those steps are complete, describe BIMChange-Agent as a research prototype/developer toolkit with runnable offline components—not as a finished terminal product.

在这些步骤完成前，应将 BIMChange-Agent 定义为“包含可运行离线组件的研究原型/开发工具包”，而不是最终终端产品。
