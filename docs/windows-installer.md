# Windows installer development / Windows 安装包开发

The public `v0.2.0-preview.1` remains a historical portable ZIP. v0.5.0 was the first release produced through the per-user installer path described here; v0.7.0 is the current product release.

公开的 `v0.2.0-preview.1` 作为历史便携 ZIP 保留。v0.5.0 是首个使用本文当前用户安装路径生成的发布版本；v0.7.0 是当前产品版本。

## Packaging shape / 封装结构

1. `scripts/build_windows_portable.ps1` builds the allowlisted PyInstaller `onedir` application and its portable ZIP.
2. `scripts/build_windows_installer.ps1` compiles that exact directory with Inno Setup 7.
3. `scripts/smoke_test_windows_installer.ps1` silently installs to an isolated directory, starts the application without opening any IFC, then silently uninstalls it.

1. `scripts/build_windows_portable.ps1` 从显式白名单构建 PyInstaller `onedir` 程序与便携 ZIP。
2. `scripts/build_windows_installer.ps1` 使用 Inno Setup 7 编译完全相同的目录。
3. `scripts/smoke_test_windows_installer.ps1` 静默安装到隔离目录，不打开任何 IFC 即启动程序，随后静默卸载。

The installer is per-user by default under `%LOCALAPPDATA%\Programs\BIMChange-Agent`, creates a Start Menu shortcut, offers an unchecked desktop-shortcut task, supports Simplified Chinese and English, registers an uninstaller, and does not require administrator rights unless the user deliberately changes the install scope.

The PyInstaller executable and Inno Setup package both embed `packaging/windows/BIMChange-Agent.ico`. The runtime also assigns the matching PNG and a stable Windows AppUserModelID, so the window, taskbar, desktop shortcut, Start Menu entry, setup, and uninstall entry use the product identity consistently.

安装器默认按当前用户安装到 `%LOCALAPPDATA%\Programs\BIMChange-Agent`，创建开始菜单快捷方式，可选创建桌面快捷方式，支持简体中文与英文，注册卸载程序；除非用户主动改变安装范围，否则不需要管理员权限。

PyInstaller EXE 与 Inno Setup 安装包均嵌入 `packaging/windows/BIMChange-Agent.ico`；运行时还设置匹配的 PNG 和稳定 Windows AppUserModelID，使窗口、任务栏、桌面快捷方式、开始菜单、安装器与卸载项保持统一产品标识。

从 0.5.0 起，开始菜单与桌面快捷方式显式引用安装目录中的版本化独立 ICO，而不是只依赖 EXE 图标。安装升级时会先移除同名旧快捷方式再重建，以降低 Windows 图标缓存继续显示旧图案的概率。0.7.0 的 EXE 与安装器均写入对应 Windows 版本资源。

## Build / 构建

Use a clean output directory and the intended product version until a release is explicitly authorized:

在明确授权发布之前，请使用空输出目录和明确的产品版本号：

```powershell
.\scripts\build_windows_portable.ps1 `
  -OutputRoot .\artifacts\product-dev `
  -PackageVersion 0.7.0

.\scripts\build_windows_installer.ps1 `
  -PortableDirectory .\artifacts\product-dev\BIMChange-Agent-0.7.0-win-x64 `
  -OutputRoot .\artifacts\product-dev `
  -PackageVersion 0.7.0
```

The installer build emits an EXE and SHA-256 sidecar. The source directory must already contain `BIMChange-Agent.exe`; existing outputs are rejected instead of overwritten.

安装器构建会输出 EXE 与 SHA-256 校验文件。输入目录必须已包含 `BIMChange-Agent.exe`；若输出已存在，脚本会拒绝覆盖。

## Smoke test / 烟雾验证

```powershell
.\scripts\smoke_test_windows_installer.ps1 `
  -InstallerPath .\artifacts\product-dev\BIMChange-Agent-0.7.0-win-x64-setup.exe
```

This check exercises only installation, process startup, and uninstall. It does not open an IFC, call an AI provider, assess model output quality, scan for malware, or prove compatibility on another Windows machine.

该检查只覆盖安装、进程启动和卸载；不打开 IFC，不调用 AI 服务商，不评估模型输出质量，不替代恶意软件扫描，也不证明其他 Windows 机器上的兼容性。

## Release boundary / 发布边界

Development installers are unsigned. Windows may show an unknown-publisher warning. Code signing, public Release upload, auto-update, upgrade migration, and broader machine compatibility require separate release authorization and validation.

开发安装包未签名，Windows 可能显示未知发布者警告。代码签名、公开 Release 上传、自动更新、升级迁移与更广机器兼容性均需要独立的发布授权和验证。

The locally used Inno Setup 7.1.0 compiler identifies this installation as non-commercial. Any commercial distribution must first obtain the applicable Inno Setup commercial licence or deliberately migrate to another installer tool after a licence review.

本机使用的 Inno Setup 7.1.0 编译器将当前安装标识为非商业用途。任何商业分发都必须先取得适用的 Inno Setup 商业许可，或在许可证复核后明确迁移到其他安装器工具。
