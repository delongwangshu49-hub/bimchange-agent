# Windows packaging / Windows 打包

Version 1.0.0 is prepared locally. v0.9.0 remains the previously published stable release; v0.5.0 introduced the per-user installer, and v0.2.0-preview.1 remains a historical portable ZIP.

1.0.0 正在本地准备；此前已公开稳定版仍为 v0.9.0。v0.5.0 引入当前用户安装器，v0.2.0-preview.1 保留为历史便携 ZIP。

## Identity / 标识

Application and Python package: `1.0.0`. Windows file/product resource: `1.0.0 / 1.0.0.0`. The stable AppId remains `B90303A8-681C-4D53-A53D-18AA7B742C4E`, separate from the historical R4 private candidate. Runtime/installer/shortcuts retain the existing product icon and animated branding.

应用与 Python 包为 `1.0.0`，Windows 版本资源为 `1.0.0 / 1.0.0.0`。稳定 AppId 保持不变，与历史 R4 私有候选版分离；运行时、安装器与快捷方式保留既有图标及动态品牌资源。

The installer defaults to the current user under LocalAppData, with English/Chinese pages, Start Menu entry, optional desktop shortcut and an uninstaller. Compilation does not authorize installation or replacement of the user's existing copy.

默认在当前用户 LocalAppData 下安装，提供中英页面、开始菜单、可选桌面快捷方式和卸载器。编译不等于授权安装或替换用户在用软件。

## Local validation build / 本地验证构建

Use PowerShell 7 and 64-bit Python 3.13. Choose new output directories; existing packages are never overwritten.

使用 PowerShell 7 与 64 位 Python 3.13，选择新输出目录，不覆盖现有包。

```powershell
.\scripts\build_windows_portable.ps1 `
  -PythonExecutable .\.venv\Scripts\python.exe `
  -OutputRoot .\artifacts\validation-1.0.0

.\scripts\build_windows_installer.ps1 `
  -PythonExecutable .\.venv\Scripts\python.exe `
  -PortableDirectory .\artifacts\validation-1.0.0\BIMChange-Agent-1.0.0-win-x64-NOT-FOR-DISTRIBUTION `
  -OutputRoot .\artifacts\installer-validation-1.0.0
```

The portable builder uses an isolated environment and explicit source copy, pins dependencies, includes local WebEngine/viewer assets, audits known host-tool DLL contamination, omits generated IfcOpenShell parser fixtures and unused DevTools resource packs, and retains dynamic libraries. Budgets: unpacked ≤600 MiB, ZIP ≤350 MiB, installer ≤250 MiB. These checks do not imply a complete dependency-license audit.

便携构建使用隔离环境和显式源码复制，固定依赖，包含本地 WebEngine/查看器资源，审计已知宿主工具 DLL 混入，移除生成包中的 IfcOpenShell 解析测试样本及未用 DevTools 资源包，保留动态库。体积上限：解包 600 MiB、ZIP 350 MiB、安装器 250 MiB；这些检查不等于完整依赖许可审计。

Both builders default to `NOT-FOR-DISTRIBUTION` names. The installer rejects an EXE with the wrong product version. `-ReleaseCandidate` assembles fresh, officially named but unpublished artifacts for exact-artifact testing. The portable candidate additionally requires the audited no-CGAL wheel, its SHA256 and the complete notices directory. `-PublicRelease` is deliberately rejected: building and publishing are separate phases. Run `scripts/verify_release.py --public --evidence EVIDENCE_DIRECTORY` after acceptance; never rename private outputs or change gates without evidence.

两种构建默认使用禁止分发名称。安装器拒绝错误版本的 EXE。`-ReleaseCandidate` 新建使用正式名称、但尚未发布的待验收产物；便携候选包另须传入已审计的无 CGAL wheel、SHA256 与完整许可目录。`-PublicRelease` 明确拒绝执行：构建与发布分为两阶段。验收后运行 `scripts/verify_release.py --public --evidence EVIDENCE_DIRECTORY`；不得改名发布旧私有包或无证据修改条件。

## Required acceptance / 必需验收

1. Run offline unit, R3/R4 and native WebEngine suites. / 运行离线单测、R3/R4 与原生三维测试。
2. Run `BIMChange-Agent.exe --smoke-r4 SOURCE REVISED REPORT NEW_OUTPUT` against the final package, using a newly generated public synthetic pair. This verifies actual rendering, selection/cache, black grid, idle behavior and cleanup. / 用公开合成对验证最终包的实际渲染、选择/缓存、黑底网格、静止行为与清理。
3. After explicit approval and confirming installed-product state, use an isolated Windows environment to test install, launch, upgrade and uninstall. The stable AppId can affect an existing installation even if the destination folder differs. / 获明确授权并检查安装状态后，在隔离 Windows 环境验证安装、启动、升级、卸载；相同稳定 AppId 即使目录不同也可能影响在用安装。
4. Audit exact dependency licenses/corresponding sources, regenerate checksums for final assets, then obtain publication authorization. / 审计精确依赖许可/对应源码、生成最终校验值，再取得发布授权。

Prior smoke results are not proof for a rebuilt package. Local validation and native 3D success do not prove another machine's compatibility or engineering correctness.

旧包烟雾结果不能证明重建包通过；本机验证和原生三维成功不证明其他机器兼容性或工程正确性。

## Distribution boundary / 分发边界

See the [release checklist](releases/v1.0.0-release-checklist.md). No tag, commit, push or Release upload occurs in these build scripts. Unsigned EXEs may trigger SmartScreen. Exact licensing materials remain a blocking prerequisite, not something solved by changing a label.

详见[发布清单](releases/v1.0.0-release-checklist.md)。构建脚本不执行标签、提交、推送或 Release 上传。未签名 EXE 可能触发 SmartScreen。精确许可材料是阻断条件，不是更换标签即可解决的问题。

The installed Inno Setup 7.1.0 license expressly permits use for any purpose, including commercial use, subject to its notice and attribution conditions. The publisher separately requests commercial users to purchase a commercial license. The bundled license text and compiler identity must be retained; this task makes no purchase and does not relicense BIMChange-Agent.

已完整核对本机 Inno Setup 7.1.0 的许可文本：其明确允许包括商业用途在内的使用，并要求保留声明等条件；发布方另外请求商业用户购买商业许可。须保留适用许可文本与编译器标识；本任务不购买许可，也不改变 BIMChange-Agent 的许可。
