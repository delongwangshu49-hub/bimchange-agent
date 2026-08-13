# BIMChange-Agent

<p align="center">
  <img src="docs/assets/brand/bimchange-logo-evolution.gif" width="960" alt="BIMChange-Agent logo evolution: one building separates into two revisions while the BIMChange-Agent wordmark draws from left to right">
</p>

**Auditable IFC revision intelligence, built from structured evidence.**

**以结构化证据为基础、可审计的 IFC 版本变更智能。**

BIMChange-Agent is an offline-first Windows application and research project for evidence-grounded IFC revision review. It combines bounded deterministic IFC4 comparison, normalized Change Records, optional provider-based AI explanation, and a reproducible research track that guides product evolution.

BIMChange-Agent 是一个离线优先、由科研证据驱动的 Windows IFC 版本变更审阅工具：提供受限的确定性 IFC4 比较、规范化 Change Records、可选的多服务商 AI 解读，以及持续反哺产品的可复现科研路线。

[![Windows Release](https://img.shields.io/badge/windows_release-v0.5.0-9B5438)](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.5.0)
[![Research Release](https://img.shields.io/badge/research_release-v0.1.0-6F7872)](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.1.0)
![Python](https://img.shields.io/badge/validated-Python_3.13-2D302F)
![Platform](https://img.shields.io/badge/desktop-Windows_x64-918674)
![Status](https://img.shields.io/badge/status-bounded_product_iteration-88746A)

> [!IMPORTANT]
> v0.5.0 is a **bounded product iteration**, not a claim of general IFC compatibility or professional engineering validation. It accepts only the explicit IFC4 boundary below. v0.1.0 remains the frozen research release and Gate 4 evidence baseline; v0.2.0 Preview 1 remains available as historical context.
>
> v0.5.0 是一个**边界明确的产品迭代版**，不宣称通用 IFC 兼容性，也不构成专业工程验证。它只接受下文明确说明的 IFC4 输入范围。v0.1.0 继续作为冻结的研究发布版与 Gate 4 证据基线；v0.2.0 Preview 1 作为历史版本保留。

## Download and install / 下载与安装

Download `BIMChange-Agent-0.5.0-win-x64-setup.exe` from the [v0.5.0 release](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.5.0), verify the accompanying SHA-256 file, and run the installer. It installs for the current Windows user by default and does not require Python or administrator access.

从 [v0.5.0 Release 页面](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.5.0)下载 `BIMChange-Agent-0.5.0-win-x64-setup.exe`，依据随附文件核对 SHA-256 后运行安装程序。默认安装到当前 Windows 用户，无需 Python 或管理员权限。

1. Download the installer and compare its SHA-256 with the release sidecar. / 下载安装包，并与 Release 随附校验文件核对 SHA-256。
2. Run the installer; Windows SmartScreen may show an unknown-publisher warning because this build is not code-signed. / 运行安装程序；由于当前版本未进行代码签名，Windows SmartScreen 可能显示未知发布者。
3. Launch BIMChange-Agent from the desktop or Start Menu. / 从桌面或开始菜单启动 BIMChange-Agent。
4. Select or drag the previous IFC on the left and the revised IFC on the right. / 在左侧选择旧版 IFC，在右侧选择新版 IFC。
5. Keep AI off for a fully local deterministic comparison, then click **Start analysis**. / 保持 AI 关闭即可执行完全本地的确定性比较，然后点击“开始分析”。
6. Filter and inspect the report, then export JSON or self-contained HTML when needed. / 筛选并查看报告，按需导出 JSON 或独立 HTML。

The application supports exact IFC4, at most 50 MiB and 5,000 `IfcElement` objects per file, and requires at least 50% shared element GlobalIds on the smaller side. Supported normalized changes are addition, deletion, and property-value modification. IFC2X3 work remains research-only and is not enabled in the product.

当前产品仅支持精确 IFC4、单文件不超过 50 MiB、每版最多 5,000 个 `IfcElement`，且较小一侧至少 50% 的构件 GlobalId 重合；当前规范化新增、删除与属性值修改。IFC2X3 仍只处于科研验证阶段，未在产品中启用。

Welcome to try it and [open an issue](https://github.com/delongwangshu49-hub/bimchange-agent/issues/new/choose). Include the version, Windows version, IFC schema, approximate file sizes, and reproducible steps—but never upload confidential IFC files, API keys, or unredacted reports to a public issue.

欢迎试用并[提交反馈](https://github.com/delongwangshu49-hub/bimchange-agent/issues/new/choose)。请说明软件版本、Windows 版本、IFC Schema、文件大致规模和复现步骤，但不要向公开 Issue 上传保密 IFC、API Key 或未经脱敏的报告。

## Product view / 产品界面

The screenshots below are generated from synthetic records and contain no real project files, local paths, API keys, or personal identifiers.

以下截图全部使用合成记录生成，不包含真实项目文件、本地路径、API Key 或个人身份信息。

![BIMChange-Agent 0.5.0 dark home](docs/assets/product-v0.5.0/desktop-dark-home.png)

![BIMChange-Agent 0.5.0 synthetic report](docs/assets/product-v0.5.0/desktop-light-report.png)

AI is off by default. Four explicit provider adapters are available in Settings, but their current conformance evidence is based on offline request/response fixtures rather than paid live-account validation. API keys remain in process memory only; IFC files, absolute paths, and file names are excluded from provider payloads.

AI 默认关闭。设置中心提供四个显式服务商适配器，但当前兼容性证据来自离线请求/响应测试，并不等同于付费真实账户在线验证。API Key 仅保留在当前进程内存中；IFC 文件、绝对路径和文件名不会进入服务商载荷。

See [Chinese release notes](CHANGELOG.zh-CN.md) and the [v0.5.0 release record](docs/releases/v0.5.0.md).

版本变化详见[中文更新日志](CHANGELOG.zh-CN.md)与 [v0.5.0 发布记录](docs/releases/v0.5.0.md)。

## See it in 30 seconds / 30 秒了解项目

```mermaid
flowchart LR
    A["Old IFC4<br/>旧版 IFC4"] --> C["Bounded local diff<br/>受限本地差分"]
    B["Revised IFC4<br/>新版 IFC4"] --> C
    C --> D["Normalized Change Records<br/>规范化变更记录"]
    D --> E["Desktop report<br/>桌面报告"]
    E --> F["JSON · HTML · optional AI explanation<br/>JSON · HTML · 可选 AI 解读"]
```

The deterministic path stays local and is authoritative. AI is off by default and is only an optional explanation layer. Arbitrary real-project IFC pairs remain outside the support claim until the compatibility envelope is measured.

确定性路径在本地运行并作为权威结果；AI 默认关闭，只是可选解释层。在真实样本兼容范围完成测量前，本项目仍不宣称支持任意真实工程 IFC 文件对。

| Run today / 现在可运行 | Input / 输入 | Output / 输出 |
|---|---|---|
| **Inspect IFC / 检查 IFC** | one `.ifc` path / 单个 `.ifc` 路径 | deterministic JSON with schema, hash, entity total, and selected type counts / 包含 Schema、哈希、实体总数与分类计数的确定性 JSON |
| **Windows desktop application / Windows 桌面应用** | bounded old/new IFC4 pair / 受限新旧 IFC4 文件对 | filtered in-app review plus JSON/HTML export / 可筛选应用内审阅及 JSON/HTML 导出 |
| **Query changes / 查询变更** | JSON filters + schema-valid Change Records / JSON 筛选条件与符合 Schema 的变更记录 | validated matches with stable IDs, old/new values, source hash, and evidence selector / 带稳定 ID、新旧值、来源哈希和证据选择器的校验后结果 |
| **Verify end to end / 端到端验证** | included sample and query / 仓库自带样例与查询 | a PASS record proving the quickstart used zero model calls / 证明快速开始未调用模型的 PASS 记录 |
| **Reproduce Gate 4 / 复现 Gate 4** | frozen runs, scores, audit artifacts / 冻结运行、评分与审计产物 | independently verified summary, report, and research charts / 经独立验证的汇总、报告与科研图表 |

## Quickstart / 快速开始

Validated release environment: 64-bit Python 3.13 on Windows. These commands are offline and make no model/API calls.

已验证的发布环境为 Windows 64 位 Python 3.13；以下命令完全离线，不会调用模型或 API。

```powershell
git clone https://github.com/delongwangshu49-hub/bimchange-agent.git
cd bimchange-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 1. Inspect the included IFC model. / 检查仓库自带 IFC 模型。
.\.venv\Scripts\python.exe scripts\check_ifc.py

# 2. Query added beams. / 从自带 Change Records 查询新增梁。
.\.venv\Scripts\python.exe scripts\query_change_records.py examples\query-added-beams.json

# 3. Test both paths end to end. / 端到端测试两条路径。
.\.venv\Scripts\python.exe scripts\test_quickstart.py
```

The final command should report:

最后一条命令应返回以下结果：

```json
{
  "status": "PASS",
  "ifc_schema": "IFC4",
  "ifc_entity_count": 407,
  "query_result_count": 1,
  "query_change_id": "gate2-added-001",
  "model_calls_made": 0
}
```

For custom paths, expected outputs, controlled fixture generation, Gate 4 verification, and safe dry-run behavior, use the [bilingual Quickstart and usage guide](docs/quickstart.md).

自定义路径、预期输出、受控样例生成、Gate 4 验证和安全 dry-run 行为详见[双语快速开始与使用指南](docs/quickstart.md)。

## Inputs and outputs / 输入与输出

Inspect any IFC that IfcOpenShell can open:

检查任意可由 IfcOpenShell 打开的 IFC 文件：

```powershell
.\.venv\Scripts\python.exe scripts\check_ifc.py C:\path\to\model.ifc
```

Query an already normalized Change Record artifact with a schema-valid request:

使用符合 Schema 的请求查询已经规范化的 Change Record 产物：

```json
{
  "schema_version": "0.1.0",
  "filters": {
    "change_types": ["added"],
    "entity_types": ["IfcBeam"]
  }
}
```

```powershell
.\.venv\Scripts\python.exe scripts\query_change_records.py request.json `
  --change-records C:\path\to\change-records.json `
  --output response.json
```

The response is validated against [`change-query-response.schema.json`](schemas/change-query-response.schema.json) and keeps the complete matching Change Records:

响应会依据 [`change-query-response.schema.json`](schemas/change-query-response.schema.json) 校验，并保留完整的匹配 Change Records：

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

This query path consumes **already normalized** Change Records. It does not turn arbitrary raw IfcDiff output into the project schema.

该查询路径只接收**已经规范化**的 Change Records，不会把任意原始 IfcDiff 输出自动转换为本项目 Schema。

## Capability boundary / 能力边界

| Layer / 层级 | Status / 状态 | What that means / 含义 |
|---|---|---|
| IFC inspection / IFC 检查 | **usable now / 当前可用** | deterministic and offline; accepts a user-supplied IFC path / 确定性离线运行，接受用户 IFC 路径 |
| Change Record validation and query / 变更记录校验与查询 | **usable now / 当前可用** | accepts user-supplied schema-valid artifacts / 接受用户提供且符合 Schema 的产物 |
| Controlled fixture diff pipeline / 受控样例差分流程 | **reproducible / 可复现** | regenerates known revisions and normalized records for repository fixtures / 可为仓库样例重建已知修订与规范化记录 |
| Gate 4 evaluation package / Gate 4 评测包 | **published and reproducible / 已发布且可复现** | 360 frozen executions, scores, blind audit, independent validation, report, and chart matrix / 包含 360 次冻结执行、评分、盲审、独立验证、报告与图表矩阵 |
| Live AI workflows / 实时 AI 工作流 | **experimental / 实验性** | dry-run by default; live use requires a provider key, `--live`, and cost authorization / 默认 dry-run；实时运行需要供应商密钥、`--live` 与费用授权 |
| Bounded IFC4 pair conversion / 受限 IFC4 文件对转换 | **bounded product / 有界产品能力** | supported only inside the explicit v0.5.0 guardrails / 仅在 v0.5.0 明确护栏内支持 |
| Windows packaging and GUI / Windows 打包与界面 | **early preview / 早期预览** | portable ZIP and desktop report flow; not code-signed / 便携 ZIP 与桌面报告流程，尚未代码签名 |
| Arbitrary IFC, 3D and Revit / 任意 IFC、三维与 Revit | **not supported / 尚不支持** | compatibility evidence and integrations remain future work / 兼容证据与集成仍属后续工作 |

当前可用的是受限 IFC4 桌面比较、IFC 检查、Change Records 查询和研究复现；任意 IFC、三维预览与 Revit 集成仍不在支持范围内。

## Gate 4 research snapshot / Gate 4 科研结果

![Gate 4 workflow performance](docs/assets/gate4/workflow-performance.svg)

Across 120 scheduled executions per workflow, Proposed recorded 96.67% semantic exact match and 97.90% Change F1; Tool-Using Agent recorded 84.17% and 91.85%; Direct LLM recorded 54.17% and 63.16%. Deterministic evidence support reached 100% for Tool-Using Agent and Proposed.

每种工作流各执行 120 次：Proposed 的语义精确匹配率为 96.67%、Change F1 为 97.90%；Tool-Using Agent 分别为 84.17% 和 91.85%；Direct LLM 分别为 54.17% 和 63.16%。Tool-Using Agent 与 Proposed 的确定性证据支持率均为 100%。

![Semantic exact match by question category](docs/assets/gate4/category-exact-match.svg)

The 40-question fixture covers six frozen categories. Category cuts are descriptive views of the same evaluation, not separate experiments. Human review remains distinct from deterministic evidence validation: one reviewer audited 135 sampled executions and 505 atomic claims, with 501 supported, one unsupported, and three indeterminate claims.

该 40 题样例覆盖六个冻结类别；分类结果只是同一评测的描述性切分，并非独立实验。人工审核与确定性证据校验保持分离：一名审核者检查了 135 次抽样执行和 505 条原子声明，其中 501 条获支持、1 条不获支持、3 条无法确定。

These results are bounded by one controlled synthetic IFC4 fixture, three repetitions, one model provider, frozen change types, and a single-reviewer audit. Read the [full bilingual results report](docs/gate4-held-out-results.md) for definitions, exact tables, Bootstrap intervals, operational accounting, and all limitations.

这些结果仅适用于一个受控合成 IFC4 样例、三次重复、单一模型供应商、冻结变化类型和单审核者审计。指标定义、精确表格、Bootstrap 区间、运行账目及全部限制详见[完整双语结果报告](docs/gate4-held-out-results.md)。

## Reproduce the evidence / 复现证据

Verify the published evaluation without generating model output:

在不生成任何模型输出的情况下验证已发布评测：

```powershell
.\.venv\Scripts\python.exe scripts\verify_gate4_foundation.py
.\.venv\Scripts\python.exe scripts\verify_gate4_scores.py
.\.venv\Scripts\python.exe scripts\verify_gate4_offline_summary.py
.\.venv\Scripts\python.exe scripts\generate_gate4_results_document.py --check
```

Rebuild and verify the research chart matrix from the frozen machine-readable summary:

从冻结的机器可读汇总重建并验证科研图表矩阵：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-visualization.txt
.\.venv\Scripts\python.exe scripts\generate_gate4_visualizations.py --write
.\.venv\Scripts\python.exe scripts\generate_gate4_visualizations.py --check
```

- [Visualization gallery and source map](docs/gate4-visualizations.md)
- [Machine-readable chart manifest](docs/assets/gate4/chart-manifest.json)
- [Machine-readable Gate 4 summary](evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json)
- [Independent validation](evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json)
- [Post-run audit](evals/audits/held_out/gate4-post-run-audit.json)
- [Release v0.1.0](https://github.com/delongwangshu49-hub/bimchange-agent/releases/tag/v0.1.0)

Gate 3 and Gate 4 workflow runners default to dry-run/offline behavior. Do not add `--live` unless a model call, credential, and cost are explicitly intended.

Gate 3 与 Gate 4 工作流默认执行 dry-run/离线路径；只有在明确计划调用模型、使用凭据并接受费用时才应添加 `--live`。

## Repository map / 仓库导航

```text
examples/                 runnable query inputs
src/bimchange_agent/      desktop, diff, query, evidence, and workflow logic
schemas/                  versioned JSON contracts
scripts/                  inspection, generation, scoring, verification, and tests
tests/                    offline product-core, report, and desktop regression tests
packaging/                Windows start guide and third-party notices
data/                     attributed IFC source, fixtures, and Change Records
evals/                    frozen development and Gate 4 artifacts
docs/                     methods, boundaries, results, release notes, and visualizations
pyproject.toml            installable CLI/desktop package and pinned preview dependencies
constraints-preview.txt   exact dependency set used for the Windows preview build
```

## Productization path / 产品化路线

The v0.2.0 Preview 1 checkpoint adds a bounded IFC4 diff/normalization service, installable `inspect/diff/query` commands, a PySide6 desktop flow, JSON/HTML reports, and an optional DeepSeek explanation boundary. It is an engineering checkpoint—not a replacement for the frozen v0.1.0 research release or evidence package. See the [preview contract](docs/product-preview-v0.2.md), [privacy and security boundary](docs/privacy-and-security.md), [release notes](docs/releases/v0.2.0-preview.1.md), and [roadmap](docs/roadmap.md).

v0.2.0 Preview 1 定档包含受限 IFC4 差分/规范化、可安装 `inspect/diff/query`、PySide6 桌面流程、JSON/HTML 报告和可选 DeepSeek 解读边界。它是工程检查点，不替代冻结的 v0.1.0 科研发布与证据包。详见[预览契约](docs/product-preview-v0.2.md)、[隐私与安全边界](docs/privacy-and-security.md)、[版本说明](docs/releases/v0.2.0-preview.1.md)和[路线图](docs/roadmap.md)。

1. **Keep the bounded core trustworthy** — use a small number of authorized representative IFC4 files as smoke checks, classify clear failures, and keep the support claim narrow.
2. **Improve the review experience** — turn the existing upload-to-report path into a more legible, guided, and visually coherent desktop experience before broadening technical scope.
3. **Expand AI deliberately** — retain the deterministic Change Record as the source of fact, while adding provider adapters and user-selected configuration only after each provider has a documented privacy boundary and offline request/error tests.
4. **Build research-backed capability** — study evidence traceability, AI-explanation reliability, and review efficiency so feature decisions have measurable support.
5. **Explore spatial change context as a side track** — a later local viewer should show changed elements and a small spatial context, colour-code change types, and connect report rows to `GlobalId`; it is not a commitment to build a general-purpose BIM viewer.

后续主线是：用少量获授权 IFC4 小样本完成烟雾验证，保持支持边界收窄；随后优先提升上传、分析、报告、错误提示和导出的整体审阅体验；在确定性 Change Records 仍为事实源的前提下，逐家补齐可选 AI 服务商的适配、隐私边界和离线请求/错误测试。科研副线将围绕证据可追溯性、AI 解读可靠性和审阅效率展开。三维作为穿插探索，目标是把变化构件及其局部空间上下文以颜色和 `GlobalId` 高亮呈现，而不是承诺完整 BIM 浏览器。详见[路线图](docs/roadmap.md)、[科研与能力探索方向](docs/research-directions.md)和[后续三维预览选项](docs/three-dimensional-preview-options.md)。

## License, attribution, and safety

Original code and documentation are MIT licensed. The Windows package also contains third-party components under their own licenses, including LGPL components; see [`packaging/THIRD-PARTY-NOTICES.txt`](packaging/THIRD-PARTY-NOTICES.txt). The initial IFC sample comes from buildingSMART's `Sample-Test-Files` repository under CC BY 4.0; provenance, retrieval date, and checksum are recorded in [`data/README.md`](data/README.md).

BIMChange-Agent does not replace professional BIM coordination, engineering review, structural-safety assessment, or formal regulatory-compliance checking.

本项目不能替代专业 BIM 协调、工程审查、结构安全评估或正式法规合规检查。
