# Windows v0.2.0 Preview 1 product contract

This document records the frozen product boundary for the v0.2.0 Preview 1 engineering checkpoint. The pre-release does not claim support for arbitrary IFC files or represent the final product experience.

本文记录 v0.2.0 Preview 1 工程定档的冻结产品边界。该预发布版不声明支持任意 IFC 文件，也不代表最终产品效果。

## Confirmed delivery direction

- Distribution: Windows x64 portable ZIP; unpack and run without installing Python.
- Input: one source IFC and one revised IFC selected from the local computer.
- User flow: the home page immediately presents two file drop zones; analysis navigates to a separate report page.
- Output: in-application summary and change table, normalized JSON, and a self-contained HTML report.
- AI: optional explanation layer. DeepSeek is the only enabled provider in the first version. Other providers are represented as `coming_soon` metadata and cannot be selected through the backend.
- AI controls: a separate settings dialog; AI is off by default and an AI failure does not block the deterministic report.
- Privacy: deterministic inspection and diff stay local. An explicitly enabled DeepSeek call receives at most 200 normalized Change Records, not IFC files, absolute paths, or source/revised file names; records may still contain project-derived names and property values.

## Explicit preview boundary

The initial defaults are conservative safety guards, not measured performance limits:

| Boundary | Preview default |
|---|---:|
| Operating system target | Windows 10/11 x64 |
| IFC schema | exact `IFC4` |
| Maximum file size | 50 MiB per IFC |
| Maximum elements | 5,000 `IfcElement` objects per version |
| Minimum comparable GUID overlap | 50% of the smaller version |
| Normalized change types | added, deleted, property value modified |
| Detector relationship mode | IfcDiff `property` |

The service rejects missing, malformed, or duplicate `IfcRoot.GlobalId` values, files edited while they are being read, and model pairs below the overlap threshold. Only `IfcElement` results are normalized. If IfcDiff reports a structured category that the preview cannot normalize—or a property change lacks both old and new JSON-compatible values—the artifact retains an `unsupported_changes` entry instead of inventing a supported record.

## Installable service boundary

`pyproject.toml` exposes three commands that will also be called by the future GUI service layer:

```powershell
bimchange inspect C:\path\to\model.ifc

bimchange diff C:\path\to\old.ifc C:\path\to\new.ifc `
  --output-dir C:\path\to\new-report-folder

bimchange query C:\path\to\new-report-folder\change-records.json `
  --change-type property_modified `
  --property-set Pset_BeamCommon `
  --property-name IsExternal
```

The diff command writes:

- `ifcdiff.json`: retained raw detector evidence;
- `change-records.json`: schema-validated product artifact with hashes, input summaries, declared limits, pair diagnostics, supported records, unsupported detector flags, and warnings.

Existing v0.1.0 controlled evaluation files and schemas remain unchanged. Product artifacts use the separate schema version `0.2.0-preview.1`.

## AI provider boundary

The provider catalog is deliberately asymmetric:

- `deepseek`: enabled, default model `deepseek-v4-flash`;
- `openai`, `anthropic`, `google`: `coming_soon`, with no endpoint or default model configured.

The DeepSeek adapter uses the Chat Completions JSON-output shape documented by DeepSeek. It caps explanation input at 200 normalized changes, removes file names and absolute local paths, requires an absolute HTTPS base URL without embedded credentials/query/fragment, caps the response at 2 MiB, and never puts an API key in the request body or generated artifact. Constructing and testing the request payload makes no API call.

The deterministic artifact remains authoritative. AI output is an optional explanation and must not add change facts, engineering-safety conclusions, or unsupported claims.

DeepSeek JSON output reference: <https://api-docs.deepseek.com/guides/json_mode/>

## Current verification

Offline tests cover:

- inspection and rejection at the declared element limit;
- one representative IFC4 pair with one addition, one deletion, and one property value modification;
- schema validation, local-path omission, and exact deterministic query;
- valid zero-change output for an identical pair;
- only DeepSeek being enabled;
- bounded DeepSeek request construction without credentials or a network call;
- semantic artifact invariants, invalid provider URLs, non-element detector results, incomplete property differences, and HTML injection escaping;
- the desktop home-to-report flow in Qt offscreen mode, including report artifact generation;
- real background-thread failure delivery to an error dialog, same-file rejection, and export failure dialogs;
- a frozen Windows `onedir` executable startup smoke test;
- a portable ZIP candidate with a start guide, license, and SHA-256 sidecar;
- the existing v0.1.0 Quickstart, Change Record query, and Gate 4 foundation guard.

The release candidate is rebuilt after the full test, privacy, dependency-vulnerability, third-party-license, ZIP-structure, and frozen-EXE smoke gates. The build makes no model/API call and uses no credential.

Frozen release artifact:

- file: `BIMChange-Agent-0.2.0-preview.1-win-x64.zip`;
- size: `85,660,041` bytes (`221,771,155` bytes unpacked);
- SHA-256: `df92acc2519870ee2284d67ab4d2c728c5bd6dcb8fa39717a89331764bf7236e`;
- Windows Defender: custom scan completed on 2026-08-11 with real-time protection enabled and no reported detection;
- Authenticode: unsigned (`NotSigned`), as disclosed in the start guide and release notes.

## Windows build

From PowerShell on Windows x64:

```powershell
.\scripts\build_windows_portable.ps1
```

The script uses an explicit source allowlist, builds a PyInstaller `onedir` application in an isolated temporary environment, includes the start guide and third-party notices/license texts, then creates a ZIP and SHA-256 sidecar under `artifacts/`. Build output is intentionally ignored by Git and is attached only to the matching pre-release tag after the release gate passes.

## Deferred product work

The first package deliberately excludes 3D viewing, Revit integration, silent self-update, arbitrary IFC support, and a separate installer. The preferred initial update behavior is a manual GitHub Release check/open-download flow; silent binary replacement is deferred. See [3D preview options](three-dimensional-preview-options.md) for the later geometry-viewing assessment.
