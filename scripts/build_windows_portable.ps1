param(
    [string]$OutputRoot = "",
    [string]$PackageVersion = "0.5.0"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$packageName = "BIMChange-Agent-$packageVersion-win-x64"

if ($env:OS -ne "Windows_NT") {
    throw "This packaging script supports Windows only."
}
$pythonArchitecture = (python -c "import platform; print(platform.architecture()[0])").Trim()
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
if ((Test-Path -LiteralPath $portableDirectory) -or (Test-Path -LiteralPath $zipPath)) {
    throw "Output already exists. Choose an empty output directory: $resolvedOutputParent"
}

$buildRoot = Join-Path $env:TEMP ("bimchange-desktop-build-" + [guid]::NewGuid().ToString("N"))
$buildEnvironment = Join-Path $buildRoot "venv"
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

python -m venv $buildEnvironment
$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
& $buildPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to prepare pip in the isolated build environment." }
& $buildPython -m pip install -c (Join-Path $sourceRoot "constraints-preview.txt") "${sourceRoot}[desktop-build]"
if ($LASTEXITCODE -ne 0) { throw "Failed to install desktop build dependencies." }
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
    --hidden-import ifcdiff `
    (Join-Path $repositoryRoot "scripts\desktop_entry.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$builtApplication = Join-Path $distRoot "BIMChange-Agent"
if (-not (Test-Path -LiteralPath (Join-Path $builtApplication "BIMChange-Agent.exe"))) {
    throw "PyInstaller did not create the expected executable."
}

Copy-Item -LiteralPath $builtApplication -Destination $portableDirectory -Recurse
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\README-START-HERE.txt") -Destination $portableDirectory
Copy-Item -LiteralPath (Join-Path $repositoryRoot "LICENSE") -Destination $portableDirectory
$licenseOutput = Join-Path $portableDirectory "licenses"
New-Item -ItemType Directory -Force -Path $licenseOutput | Out-Null
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\THIRD-PARTY-NOTICES.txt") -Destination $portableDirectory
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\licenses\GPL-3.0.txt") -Destination $licenseOutput
Copy-Item -LiteralPath (Join-Path $repositoryRoot "packaging\licenses\LGPL-3.0.txt") -Destination $licenseOutput
$pythonBase = (& $buildPython -c "import sys; print(sys.base_prefix)").Trim()
$pythonLicense = Join-Path $pythonBase "LICENSE.txt"
if (-not (Test-Path -LiteralPath $pythonLicense)) {
    throw "Python runtime license was not found: $pythonLicense"
}
Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $licenseOutput "PYTHON-LICENSE.txt")
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
    "pyside6_essentials-*.dist-info", "shiboken6-*.dist-info"
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
    }
}
Compress-Archive -LiteralPath $portableDirectory -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $checksumPath -Value "$hash  $($packageName).zip" -Encoding utf8NoBOM

Write-Output ([ordered]@{
    status = "PASS"
    portable_directory = $portableDirectory
    zip = $zipPath
    sha256 = $hash
    zip_bytes = (Get-Item -LiteralPath $zipPath).Length
    unpacked_bytes = (Get-ChildItem -LiteralPath $portableDirectory -File -Recurse | Measure-Object -Property Length -Sum).Sum
    build_root = $buildRoot
} | ConvertTo-Json)
