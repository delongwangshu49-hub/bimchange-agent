param(
    [string]$OutputRoot = "",
    [string]$PackageVersion = "1.0.0",
    [string]$PythonExecutable = "python",
    [string]$PreparedEnvironment = "",
    [string]$NativeIfcWheel = "",
    [string]$NativeIfcWheelSha256 = "",
    [string]$NoticesDirectory = "",
    [switch]$ReleaseCandidate,
    [switch]$PublicRelease
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ($PackageVersion -ne "1.0.0") { throw "This build definition is frozen for 1.0.0." }
if ($PublicRelease) {
    throw 'Assemble with -ReleaseCandidate, verify the exact artifacts, then run verify_release.py --public before publishing. Builds do not publish.'
}
if ($ReleaseCandidate -and (-not $NativeIfcWheel -or -not $NativeIfcWheelSha256 -or -not $NoticesDirectory)) {
    throw 'A release candidate requires the audited native wheel digest and notices directory.'
}
if ($ReleaseCandidate) {
    $gates = Get-Content -Raw (Join-Path $repositoryRoot 'packaging/release-1.0.0-gates.json') | ConvertFrom-Json
    if (-not $gates.public_upload_authorized) { throw 'Release candidate preparation is not authorized.' }
    foreach ($required in @('UPSTREAM-NOTICES.zip','source-inventory.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $NoticesDirectory $required))) { throw "Missing notices: $required" }
    }
}
$suffix = if ($ReleaseCandidate) { "" } else { "-NOT-FOR-DISTRIBUTION" }
$packageName = "BIMChange-Agent-$packageVersion-win-x64$suffix"

if ($env:OS -ne "Windows_NT") {
    throw "This packaging script supports Windows only."
}
$pythonArchitecture = (& $PythonExecutable -c "import platform; print(platform.architecture()[0])").Trim()
if ($LASTEXITCODE -ne 0 -or $pythonArchitecture -ne "64bit") {
    throw "A working 64-bit Python is required to build the Windows x64 package."
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repositoryRoot "artifacts"
}
$resolvedOutputParent = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $resolvedOutputParent | Out-Null
$portableDirectory = Join-Path $resolvedOutputParent $packageName
$zipPath = Join-Path $resolvedOutputParent ($packageName + ".zip")
$checksumPath = $zipPath + ".sha256.txt"
$maximumUnpackedBytes = 600MB
$maximumZipBytes = 350MB
if ((Test-Path -LiteralPath $portableDirectory) -or (Test-Path -LiteralPath $zipPath)) {
    throw "Output already exists. Choose an empty output directory: $resolvedOutputParent"
}

$buildRoot = Join-Path $env:TEMP ("bimchange-1.0.0-validation-build-" + [guid]::NewGuid().ToString("N"))
$buildEnvironment = Join-Path $buildRoot "venv"
if ($PreparedEnvironment) {
    $buildEnvironment = [IO.Path]::GetFullPath($PreparedEnvironment)
    if (-not (Test-Path -LiteralPath (Join-Path $buildEnvironment 'Scripts\python.exe'))) {
        throw 'PreparedEnvironment must be an existing isolated build virtual environment.'
    }
}
$sourceRoot = Join-Path $buildRoot "source"
$distRoot = Join-Path $buildRoot "dist"
$workRoot = Join-Path $buildRoot "work"
$specRoot = Join-Path $buildRoot "spec"
New-Item -ItemType Directory -Force -Path $buildRoot,$sourceRoot,$distRoot,$workRoot,$specRoot | Out-Null

# Build from an explicit source allowlist. This avoids writing generated metadata
# into the working tree and prevents unrelated/untracked files from entering the
# package build context.
Copy-Item -LiteralPath (Join-Path $repositoryRoot "pyproject.toml") -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $repositoryRoot "README.md") -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $repositoryRoot "LICENSE") -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $repositoryRoot "constraints-preview.txt") -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $repositoryRoot "src") -Destination $sourceRoot -Recurse

$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
if (-not $PreparedEnvironment) {
    & $PythonExecutable -m venv $buildEnvironment
    & $buildPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to prepare pip in the isolated build environment." }
    & $buildPython -m pip install -c (Join-Path $sourceRoot "constraints-preview.txt") "${sourceRoot}[desktop-build]"
} else {
    & $buildPython -m pip install --no-deps --force-reinstall $sourceRoot
}
if ($LASTEXITCODE -ne 0) { throw "Failed to install desktop build dependencies." }
if ($NativeIfcWheel) {
    if (-not $NativeIfcWheelSha256 -or (Get-FileHash -LiteralPath $NativeIfcWheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $NativeIfcWheelSha256.ToLowerInvariant()) {
        throw 'Native IfcOpenShell wheel digest mismatch.'
    }
    & $buildPython -m pip install --no-deps --force-reinstall $NativeIfcWheel
    if ($LASTEXITCODE -ne 0) { throw 'Native dependency installation failed.' }
    & $buildPython -c "import importlib.metadata as m,json; d=m.distribution('ifcopenshell'); p=json.loads(d.read_text('NO-CGAL-BUILD.json')); assert d.version=='0.8.5+nocgal.1'; assert p['status']=='PASS'; assert set(p['disabled_kernels'])=={'cgal','cgal-simple'}; print('Audited no-CGAL dependency installed')"
    if ($LASTEXITCODE -ne 0) { throw 'Native dependency provenance check failed.' }
}
& $buildPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Build dependency consistency check failed." }
# DLL discovery must not pick up optional ICU/OpenSSL binaries from unrelated
# host tools such as Poppler. This changes only the current build environment.
$previousBuildPath = $env:PATH
$basePython = (& $buildPython -c "import sys; print(sys.base_prefix)").Trim()
$env:PATH = @((Join-Path $buildEnvironment 'Scripts'), $basePython,
    (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
try {
& $buildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "BIMChange-Agent" `
    --icon (Join-Path $repositoryRoot "packaging\windows\BIMChange-Agent.ico") `
    --version-file (Join-Path $repositoryRoot "packaging\windows\BIMChange-Agent.version-info.txt") `
    --distpath $distRoot `
    --workpath $workRoot `
    --specpath $specRoot `
    --collect-all ifcopenshell `
    --collect-data bimchange_agent `
    --additional-hooks-dir (Join-Path $repositoryRoot "packaging\hooks") `
    --hidden-import ifcdiff `
    --hidden-import bimchange_agent.r4_webengine_runtime `
    --hidden-import PySide6.QtWebEngineCore `
    --hidden-import PySide6.QtWebEngineWidgets `
    (Join-Path $repositoryRoot "scripts\desktop_entry.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
} finally {
    $env:PATH = $previousBuildPath
}

$builtApplication = Join-Path $distRoot "BIMChange-Agent"
if (-not (Test-Path -LiteralPath (Join-Path $builtApplication "BIMChange-Agent.exe"))) {
    throw "PyInstaller did not create the expected executable."
}
& $buildPython (Join-Path $repositoryRoot 'scripts\audit_r4_build_dependencies.py') `
    (Join-Path $workRoot 'BIMChange-Agent\Analysis-00.toc') $builtApplication
if ($LASTEXITCODE -ne 0) { throw 'Generated DLL provenance audit failed.' }
& $buildPython (Join-Path $repositoryRoot 'scripts\audit_qt_bundle.py') $builtApplication
if ($LASTEXITCODE -ne 0) { throw 'Qt module minimization audit failed.' }

# `--collect-all ifcopenshell` includes parser test fixtures that are not used by
# the desktop product. Remove only that exact generated directory so packaged
# `.ifc` resources are limited to IfcOpenShell's runtime Pset schemas.
$bundledFixtureDirectory = Join-Path $builtApplication "_internal\ifcopenshell\simple_spf\fixtures"
if (Test-Path -LiteralPath $bundledFixtureDirectory -PathType Container) {
    $resolvedBuiltApplication = [System.IO.Path]::GetFullPath($builtApplication)
    $resolvedFixtureDirectory = [System.IO.Path]::GetFullPath($bundledFixtureDirectory)
    if (-not $resolvedFixtureDirectory.StartsWith(
        $resolvedBuiltApplication + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Bundled fixture directory escaped the generated application root."
    }
    Remove-Item -LiteralPath $resolvedFixtureDirectory -Recurse -Force
}

Copy-Item -LiteralPath $builtApplication -Destination $portableDirectory -Recurse

# Chromium's DevTools front-end payload is not used by the locked-down R4
# viewer (remote debugging is never enabled). PyInstaller collects both the
# release and debug variants by default, adding more than 80 MiB to the
# unpacked candidate. Keep the runtime resource packs, but omit DevTools-only
# packs and verify the resulting package with the native WebEngine smoke gate.
$webEngineResources = Join-Path $portableDirectory "_internal\PySide6\resources"
foreach ($devToolsPack in @(
    "qtwebengine_devtools_resources.pak",
    "qtwebengine_devtools_resources.debug.pak"
)) {
    $devToolsPath = Join-Path $webEngineResources $devToolsPack
    if (Test-Path -LiteralPath $devToolsPath) {
        Remove-Item -LiteralPath $devToolsPath -Force
    }
}

Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\README-START-HERE.txt") -Destination (Join-Path $portableDirectory "README-START-HERE.txt")
Copy-Item -LiteralPath (Join-Path $repositoryRoot "LICENSE") -Destination $portableDirectory
if (-not $ReleaseCandidate) {
    Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\1.0.0-NOT-FOR-DISTRIBUTION.txt") -Destination $portableDirectory
}
$licenseOutput = Join-Path $portableDirectory "licenses"
New-Item -ItemType Directory -Force -Path $licenseOutput | Out-Null
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\THIRD-PARTY-NOTICES.txt") -Destination $portableDirectory
if ($NoticesDirectory) {
    Copy-Item -LiteralPath (Join-Path $NoticesDirectory 'UPSTREAM-NOTICES.zip') -Destination $licenseOutput
    Copy-Item -LiteralPath (Join-Path $NoticesDirectory 'source-inventory.json') -Destination $licenseOutput
    Copy-Item -LiteralPath (Join-Path $repositoryRoot 'packaging/CORRESPONDING-SOURCE.txt') -Destination $portableDirectory
}
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\licenses\GPL-3.0.txt") -Destination $licenseOutput
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\licenses\LGPL-3.0.txt") -Destination $licenseOutput
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\licenses\INNO-SETUP.txt") -Destination $licenseOutput
$pythonBase = (& $buildPython -c "import sys; print(sys.base_prefix)").Trim()
$pythonLicense = Join-Path $pythonBase "LICENSE.txt"
if (-not (Test-Path -LiteralPath $pythonLicense)) {
    throw "Python runtime license was not found: $pythonLicense"
}
Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $licenseOutput "PYTHON-LICENSE.txt")
Copy-Item -LiteralPath (Join-Path $repositoryRoot "src\bimchange_agent\resources\r4_viewer\vendor\THREE-LICENSE.txt") -Destination (Join-Path $licenseOutput "THREE-MIT.txt")
$metadataOutput = Join-Path $licenseOutput "python-package-metadata"
New-Item -ItemType Directory -Force -Path $metadataOutput | Out-Null
$sitePackages = Join-Path $buildEnvironment "Lib\site-packages"
$runtimeDistributionPatterns = @(
    "ifcopenshell-*.dist-info", "ifcdiff-*.dist-info", "jsonschema-*.dist-info",
    "jsonschema_specifications-*.dist-info", "attrs-*.dist-info",
    "referencing-*.dist-info", "rpds_py-*.dist-info", "numpy-*.dist-info",
    "shapely-*.dist-info", "isodate-*.dist-info", "python_dateutil-*.dist-info",
    "six-*.dist-info", "lark-*.dist-info", "typing_extensions-*.dist-info",
    "deepdiff-*.dist-info", "cachebox-*.dist-info", "orderly_set-*.dist-info",
    "pyside6_essentials-*.dist-info", "pyside6_addons-*.dist-info", "shiboken6-*.dist-info"
)
foreach ($pattern in $runtimeDistributionPatterns) {
    foreach ($distribution in Get-ChildItem -LiteralPath $sitePackages -Directory -Filter $pattern) {
        $distributionOutput = Join-Path $metadataOutput $distribution.Name
        New-Item -ItemType Directory -Force -Path $distributionOutput | Out-Null
        $metadata = Join-Path $distribution.FullName "METADATA"
        if (Test-Path -LiteralPath $metadata) {
            Copy-Item -LiteralPath $metadata -Destination $distributionOutput
        }
        $licenses = Join-Path $distribution.FullName "licenses"
        if (Test-Path -LiteralPath $licenses) {
            Copy-Item -LiteralPath $licenses -Destination $distributionOutput -Recurse
        }
        $nativeProof = Join-Path $distribution.FullName 'NO-CGAL-BUILD.json'
        if (Test-Path -LiteralPath $nativeProof) { Copy-Item -LiteralPath $nativeProof -Destination $distributionOutput }
        $nativePatch = Join-Path $distribution.FullName 'ifc-swig.patch'
        if (Test-Path -LiteralPath $nativePatch) { Copy-Item -LiteralPath $nativePatch -Destination $distributionOutput }
    }
}
$unpackedBytes = (Get-ChildItem -LiteralPath $portableDirectory -File -Recurse | Measure-Object -Property Length -Sum).Sum
if ($unpackedBytes -gt $maximumUnpackedBytes) {
    throw "1.0.0 build exceeds the 600 MiB unpacked budget: $unpackedBytes bytes."
}
Compress-Archive -LiteralPath $portableDirectory -DestinationPath $zipPath -CompressionLevel Optimal
$zipBytes = (Get-Item -LiteralPath $zipPath).Length
if ($zipBytes -gt $maximumZipBytes) {
    throw "1.0.0 build exceeds the 350 MiB portable ZIP budget: $zipBytes bytes."
}
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $checksumPath -Value "$hash  $($packageName).zip" -Encoding utf8NoBOM

Write-Output ([ordered]@{
    status = "PASS"
    distribution_status = $(if ($ReleaseCandidate) { "STAGED_FINAL_ARTIFACT_VERIFICATION_REQUIRED" } else { "NOT_FOR_DISTRIBUTION" })
    portable_directory = $portableDirectory
    zip = $zipPath
    sha256 = $hash
    zip_bytes = $zipBytes
    unpacked_bytes = $unpackedBytes
    build_root = $buildRoot
} | ConvertTo-Json)
