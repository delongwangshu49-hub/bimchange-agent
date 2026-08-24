param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [string]$PackageVersion = "0.9.0",
    [string]$TestRoot = ""
)

$ErrorActionPreference = "Stop"
$resolvedInstallerPath = [System.IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $resolvedInstallerPath -PathType Leaf)) {
    throw "Installer was not found: $resolvedInstallerPath"
}
if (-not $TestRoot) {
    $TestRoot = Join-Path $env:TEMP ("bimchange-installer-smoke-" + [guid]::NewGuid().ToString("N"))
}
$resolvedTestRoot = [System.IO.Path]::GetFullPath($TestRoot)
New-Item -ItemType Directory -Force -Path $resolvedTestRoot | Out-Null
$installDirectory = Join-Path $resolvedTestRoot "application"
$installLog = Join-Path $resolvedTestRoot "install.log"

$installProcess = Start-Process -FilePath $resolvedInstallerPath -ArgumentList @(
    "/CURRENTUSER",
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/MERGETASKS=!desktopicon",
    "/DIR=$installDirectory",
    "/LOG=$installLog"
) -Wait -PassThru -WindowStyle Hidden
if ($installProcess.ExitCode -ne 0) {
    throw "Silent installation failed with exit code $($installProcess.ExitCode)."
}

$applicationPath = Join-Path $installDirectory "BIMChange-Agent.exe"
$uninstallerPath = Join-Path $installDirectory "unins000.exe"
$brandIconPath = Join-Path $installDirectory "BIMChange-Agent-$PackageVersion.ico"
if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
    throw "Installed application was not found: $applicationPath"
}
if (-not (Test-Path -LiteralPath $uninstallerPath -PathType Leaf)) {
    throw "Uninstaller was not found: $uninstallerPath"
}
if (-not (Test-Path -LiteralPath $brandIconPath -PathType Leaf)) {
    throw "Installed shortcut icon was not found: $brandIconPath"
}

$applicationProcess = Start-Process -FilePath $applicationPath -PassThru
$started = $false
try {
    if (-not $applicationProcess.WaitForExit(8000)) {
        $started = $true
    } elseif ($applicationProcess.ExitCode -ne 0) {
        throw "Installed application exited with code $($applicationProcess.ExitCode)."
    }
} finally {
    if (-not $applicationProcess.HasExited) {
        Stop-Process -Id $applicationProcess.Id -Force
        $applicationProcess.WaitForExit()
    }
}
if (-not $started) {
    throw "Installed application did not remain running for the startup smoke window."
}

$uninstallLog = Join-Path $resolvedTestRoot "uninstall.log"
$uninstallProcess = Start-Process -FilePath $uninstallerPath -ArgumentList @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/LOG=$uninstallLog"
) -Wait -PassThru -WindowStyle Hidden
if ($uninstallProcess.ExitCode -ne 0) {
    throw "Silent uninstall failed with exit code $($uninstallProcess.ExitCode)."
}
if (Test-Path -LiteralPath $applicationPath) {
    throw "Application executable remained after uninstall."
}

Write-Output ([ordered]@{
    status = "PASS"
    installer = $resolvedInstallerPath
    test_root = $resolvedTestRoot
    installed_executable_started = $started
    installed_shortcut_icon_present = $true
    uninstall_removed_executable = $true
} | ConvertTo-Json)
