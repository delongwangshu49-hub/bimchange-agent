# Gate 4 Frozen Foundation

# Gate 4 冻结基础

## Outcome / 结果

Gate 4 now has a machine-readable foundation that pins the protected Gate 3 repository bytes to commit `abcb095` and reserves independent `held_out` paths before any held-out artifact is generated or read.

Gate 4 现已具备机器可读的基础配置：受保护的 Gate 3 仓库字节固定到提交 `abcb095`，并在生成或读取任何留出产物前预留独立的 `held_out` 路径。

The foundation layer itself does not implement evaluation artifacts. The deterministic IFC fixture and Change Records have since been added as a separate guarded layer; questions, reference answers, schedules, audits, the freeze manifest, and model runs remain unimplemented.

基础层本身不实现评测产物；确定性 IFC 样例与 Change Record 现已作为独立受守卫层加入，问题、参考答案、执行计划、审核产物、冻结清单与模型运行仍未实现。

See [Gate 4 deterministic held-out fixture](gate4-held-out-fixture.md) for the implemented layer and its offline evidence.

已实现层及其离线证据详见 [Gate 4 确定性留出样例](gate4-held-out-fixture.md)。

## Protected boundary / 受保护边界

`configs/gate4-foundation.json` records 37 reviewed Gate 3 files and their Git blob IDs and SHA-256 hashes at `abcb095`. The list covers the Gate 2 data used by Gate 3, Gate 3 contracts, fixed development inputs and references, retained results, all Schemas, query and evidence modules, workflow prompts and logic, and per-answer scoring code.

`configs/gate4-foundation.json` 记录了 `abcb095` 中 37 个已审核 Gate 3 文件的 Git blob ID 与 SHA-256。范围覆盖 Gate 3 使用的 Gate 2 数据、Gate 3 契约、固定开发输入与参考答案、保留结果、全部 Schema、查询与证据模块、工作流提示词与逻辑，以及逐答案评分代码。

The guard compares four representations for every protected file: the pinned baseline blob, current `HEAD`, Git index, and working-tree content after Git's canonical clean filters. This preserves byte-level repository identity without treating Windows CRLF checkout conversion as a contract change.

守卫对每个受保护文件比较四种表示：固定基线 blob、当前 `HEAD`、Git 索引，以及经过 Git 规范化 clean filter 后的工作树内容。这样既保持仓库字节级身份，也不会把 Windows CRLF 签出转换误判为契约变化。

## Independent held-out paths / 独立留出路径

The path registry reserves separate locations for source and revised IFC files, the operation ledger, Change Records, questions, reference answers, Direct LLM input, run schedule, pre-run and post-run audits, the freeze manifest, and retained results. Every target includes the `held_out` path segment and is rejected if it overlaps a protected Gate 3 path or uses `development` or `gate3` naming.

路径注册表为源 IFC、修订 IFC、操作账本、Change Record、问题、参考答案、Direct LLM 输入、运行计划、运行前后审核、冻结清单与保留结果分别预留独立位置。每个目标都包含 `held_out` 路径段；若与受保护的 Gate 3 路径重叠，或使用 `development`、`gate3` 命名，检查将拒绝通过。

## Offline verification / 离线验证

Run the foundation check before any Gate 4 generator, verifier, question builder, or workflow wrapper:

在运行任何 Gate 4 生成器、验证器、问题构建器或工作流外壳前，先执行基础检查：

```powershell
.\.venv\Scripts\python.exe scripts\verify_gate4_foundation.py
.\.venv\Scripts\python.exe scripts\test_gate4_foundation.py
```

A passing report explicitly records that no held-out artifact was read or generated and that no model call was made. Later implementation steps must call this guard before accessing registered held-out paths.

通过报告会明确记录：未读取或生成留出产物，也未发起模型调用。后续实现必须在访问已登记的留出路径前调用该守卫。
