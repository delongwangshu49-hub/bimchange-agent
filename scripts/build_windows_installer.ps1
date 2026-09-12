param(
    [Parameter(Mandatory = $true)]
    [string]$PortableDirectory,
    [string]$OutputRoot = "",
    [string]$PackageVersion = "1.0.0",
    [string]$FileVersion = "1.0.0.0",
    [string]$IsccPath = "",
    [string]$PythonExecutable = "python",
    [switch]$PublicRelease
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $repositoryRoot "packaging\windows\BIMChange-Agent.iss"
if ($PackageVersion -ne "1.0.0" -or $FileVersion -ne "1.0.0.0") {
    throw "This installer definition is frozen for 1.0.0 / 1.0.0.0."
}
if ($PublicRelease) {
    & $PythonExecutable (Join-Path $repositoryRoot 'scripts\verify_release.py') --public
    if ($LASTEXITCODE -ne 0) { throw 'Public release gates are not satisfied.' }
}

if ($env:OS -ne "Windows_NT") {
    throw "This packaging script supports Windows only."
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repositoryRoot "artifacts"
}

$resolvedPortableDirectory = [System.IO.Path]::GetFullPath($PortableDirectory)
$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$applicationPath = Join-Path $resolvedPortableDirectory "BIMChange-Agent.exe"
if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
    throw "PortableDirectory must contain BIMChange-Agent.exe: $resolvedPortableDirectory"
}
$resourceVersion = (Get-Item -LiteralPath $applicationPath).VersionInfo.ProductVersion
if ($resourceVersion -ne "1.0.0") { throw "Portable executable is not 1.0.0: $resourceVersion" }
$privateMarkers = Get-ChildItem -LiteralPath $resolvedPortableDirectory -File -Filter '*NOT-FOR-DISTRIBUTION*'
if ($PublicRelease -and $privateMarkers) { throw 'Validation/private packages cannot become public installers.' }
if (-not (Test-Path -LiteralPath $installerScript -PathType Leaf)) {
    throw "Installer definition was not found: $installerScript"
}

if (-not $IsccPath) {
    $isccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    )
    $IsccPath = $isccCandidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) {
    throw "ISCC.exe was not found. Install Inno Setup 7 or pass -IsccPath explicitly."
}

New-Item -ItemType Directory -Force -Path $resolvedOutputRoot | Out-Null
$suffix = if ($PublicRelease) { "" } else { "-NOT-FOR-DISTRIBUTION" }
$outputBaseName = "BIMChange-Agent-$PackageVersion-win-x64-setup$suffix"
$installerPath = Join-Path $resolvedOutputRoot ($outputBaseName + ".exe")
$checksumPath = $installerPath + ".sha256.txt"
if ((Test-Path -LiteralPath $installerPath) -or (Test-Path -LiteralPath $checksumPath)) {
    throw "Installer output already exists: $installerPath"
}

$compilerArguments = @(
    "/DSourceDir=$resolvedPortableDirectory",
    "/DOutputDir=$resolvedOutputRoot",
    "/DAppVersion=$PackageVersion",
    "/DAppFileVersion=$FileVersion",
    "/DOutputBaseName=$outputBaseName",
    $installerScript
)
$quotedCompilerArguments = @($compilerArguments | ForEach-Object { '"' + $_ + '"' })
$compilerProcess = Start-Process -FilePath $IsccPath -ArgumentList $quotedCompilerArguments `
    -WindowStyle Hidden -Wait -PassThru `
    -RedirectStandardOutput (Join-Path $resolvedOutputRoot 'iscc.stdout.log') `
    -RedirectStandardError (Join-Path $resolvedOutputRoot 'iscc.stderr.log')
if ($compilerProcess.ExitCode -ne 0) {
    throw "Inno Setup compilation failed."
}
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Inno Setup did not create the expected installer: $installerPath"
}

$hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-Item -LiteralPath $installerPath).Length -gt 250MB) { throw 'Installer exceeds 250 MiB budget.' }
Set-Content -LiteralPath $checksumPath -Value "$hash  $($outputBaseName).exe" -Encoding utf8NoBOM
$signature = Get-AuthenticodeSignature -LiteralPath $installerPath

Write-Output ([ordered]@{
    status = "PASS"
    distribution_status = $(if ($PublicRelease) { "PUBLIC_GATES_PASSED" } else { "NOT_FOR_DISTRIBUTION" })
    installer = $installerPath
    sha256 = $hash
    bytes = (Get-Item -LiteralPath $installerPath).Length
    authenticode = $signature.Status.ToString()
    compiler = (Get-Item -LiteralPath $IsccPath).VersionInfo.FileVersion
    install_scope = "current-user by default; elevation optional"
} | ConvertTo-Json)
