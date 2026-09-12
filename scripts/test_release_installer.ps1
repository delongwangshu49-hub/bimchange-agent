param(
    [Parameter(Mandatory=$true)][string]$InstallerPath,
    [Parameter(Mandatory=$true)][string]$PreviousInstallerPath,
    [Parameter(Mandatory=$true)][string]$PayloadManifest,
    [Parameter(Mandatory=$true)][string]$SourceIfc,
    [Parameter(Mandatory=$true)][string]$RevisedIfc,
    [Parameter(Mandatory=$true)][string]$TestRoot
)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSVersion.Major -lt 7 -or $env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'This test is restricted to a disposable Windows GitHub Actions runner.'
}
$testDirectory=[IO.Path]::GetFullPath($TestRoot)
if (-not $testDirectory.StartsWith([IO.Path]::GetFullPath($env:RUNNER_TEMP)+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'TestRoot must be inside RUNNER_TEMP.'
}
if (Test-Path -LiteralPath $testDirectory) { throw 'TestRoot must be new.' }
$uninstallKey='Software\Microsoft\Windows\CurrentVersion\Uninstall\{B90303A8-681C-4D53-A53D-18AA7B742C4E}_is1'
foreach ($hive in @('HKCU:','HKLM:')) {
    if (Test-Path -LiteralPath (Join-Path $hive $uninstallKey)) { throw 'Existing stable installation detected; aborting.' }
}
if (Test-Path -LiteralPath 'HKCU:/Software/BIMChange-Agent') { throw 'Existing user preferences detected; aborting.' }
New-Item -ItemType Directory -Path $testDirectory | Out-Null
$payload=Get-Content -Raw -LiteralPath $PayloadManifest | ConvertFrom-Json
$inputHashes=@((Get-FileHash -LiteralPath $SourceIfc).Hash,(Get-FileHash -LiteralPath $RevisedIfc).Hash)
function Run-Process([string]$File,[string[]]$Arguments) {
    $quoted=@($Arguments | ForEach-Object { '"'+$_+'"' })
    $process=Start-Process -FilePath $File -ArgumentList $quoted -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(120000)) { throw "Process timed out: $File" }
    if ($process.ExitCode -ne 0) { throw "Process failed ($($process.ExitCode)): $File" }
}
function Install([string]$File,[string]$Directory,[string]$Log) {
    Run-Process $File @('/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
        '/MERGETASKS=!desktopicon',"/DIR=$Directory","/LOG=$Log")
}
function Verify-Payload([string]$Directory) {
    foreach ($entry in $payload.files) {
        $path=[IO.Path]::GetFullPath((Join-Path $Directory $entry.path))
        if (-not $path.StartsWith($Directory+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe manifest path.' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing installed file: $($entry.path)" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Installed hash mismatch: $($entry.path)" }
    }
    if ((Get-Item -LiteralPath (Join-Path $Directory 'BIMChange-Agent.exe')).VersionInfo.ProductVersion -ne '1.0.0') { throw 'Installed version mismatch.' }
    if ((Get-ItemProperty -LiteralPath "HKCU:\$uninstallKey").DisplayVersion -ne '1.0.0') { throw 'Uninstall registration version mismatch.' }
    $shortcut=Join-Path ([Environment]::GetFolderPath('Programs')) 'BIMChange-Agent/BIMChange-Agent.lnk'
    $link=(New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
    if ($link.TargetPath -ne (Join-Path $Directory 'BIMChange-Agent.exe')) { throw 'Shortcut target mismatch.' }
    if ($link.IconLocation -notlike '*BIMChange-Agent-1.0.0.ico*') { throw 'Shortcut icon mismatch.' }
}
function Uninstall([string]$Directory,[string]$Log) {
    Run-Process (Join-Path $Directory 'unins000.exe') @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=$Log")
    if (Test-Path -LiteralPath (Join-Path $Directory 'BIMChange-Agent.exe')) { throw 'Uninstall left application executable.' }
    if (Test-Path -LiteralPath "HKCU:\$uninstallKey") { throw 'Uninstall left registration.' }
}
function Verify-Report([string]$Directory) {
    $artifact=Get-Content -Raw -LiteralPath (Join-Path $Directory 'r3-change-records.json') | ConvertFrom-Json
    if ($artifact.schema_version -ne '0.4.0' -or $artifact.summary.total_supported -ne 3 -or
        $artifact.summary.added -ne 1 -or $artifact.summary.deleted -ne 1 -or
        $artifact.summary.property_modified -ne 1 -or $artifact.summary.unsupported -ne 0 -or
        $artifact.model_calls_made -ne 0) { throw 'Installed R3 comparison result mismatch.' }
}
$fresh=Join-Path $testDirectory 'fresh'
Install $InstallerPath $fresh (Join-Path $testDirectory 'fresh-install.log')
Verify-Payload $fresh
Run-Process (Join-Path $fresh 'BIMChange-Agent.exe') @('--smoke-test')
Run-Process (Join-Path $fresh 'BIMChange-Agent.exe') @('--smoke-diff',$SourceIfc,$RevisedIfc,(Join-Path $testDirectory 'fresh-report'))
Verify-Report (Join-Path $testDirectory 'fresh-report')
Uninstall $fresh (Join-Path $testDirectory 'fresh-uninstall.log')
$upgrade=Join-Path $testDirectory 'upgrade'
Install $PreviousInstallerPath $upgrade (Join-Path $testDirectory 'previous-install.log')
if ((Get-ItemProperty -LiteralPath "HKCU:\$uninstallKey").DisplayVersion -ne '0.9.0') { throw 'Upgrade baseline is not 0.9.0.' }
Run-Process (Join-Path $upgrade 'BIMChange-Agent.exe') @('--smoke-test')
$preferenceKey='HKCU:/Software/BIMChange-Agent/BIMChange-Agent/appearance'
New-Item -Path $preferenceKey -Force | Out-Null
New-ItemProperty -LiteralPath $preferenceKey -Name 'theme' -Value 'dark' -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $preferenceKey -Name 'language' -Value 'en' -PropertyType String -Force | Out-Null
Install $InstallerPath $upgrade (Join-Path $testDirectory 'upgrade-install.log')
Verify-Payload $upgrade
Run-Process (Join-Path $upgrade 'BIMChange-Agent.exe') @('--smoke-test')
Run-Process (Join-Path $upgrade 'BIMChange-Agent.exe') @('--smoke-diff',$SourceIfc,$RevisedIfc,(Join-Path $testDirectory 'upgrade-report'))
Verify-Report (Join-Path $testDirectory 'upgrade-report')
$preferences=Get-ItemProperty -LiteralPath $preferenceKey
if ($preferences.theme -ne 'dark' -or $preferences.language -ne 'en') { throw 'Upgrade did not preserve appearance preferences.' }
Uninstall $upgrade (Join-Path $testDirectory 'upgrade-uninstall.log')
if ((Get-FileHash -LiteralPath $SourceIfc).Hash -ne $inputHashes[0] -or (Get-FileHash -LiteralPath $RevisedIfc).Hash -ne $inputHashes[1]) { throw 'Input data changed.' }
$report=[ordered]@{status='PASS'; installer_sha256=(Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant();
    payload_manifest_sha256=(Get-FileHash -LiteralPath $PayloadManifest -Algorithm SHA256).Hash.ToLowerInvariant();
    previous_installer_sha256=(Get-FileHash -LiteralPath $PreviousInstallerPath -Algorithm SHA256).Hash.ToLowerInvariant();
    fresh_install=$true; upgrade_from='0.9.0'; payload_files_verified=$payload.files.Count;
    installed_version='1.0.0'; desktop_startup=$true; offline_comparison=$true; preferences_preserved=$true;
    shortcut_target_and_icon=$true; uninstall_executable_and_registry_removed=$true; input_files_unchanged=$true;
    run_url="https://github.com/$env:GITHUB_REPOSITORY/actions/runs/$env:GITHUB_RUN_ID"}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $testDirectory 'installer-acceptance.json') -Encoding utf8NoBOM
$report | ConvertTo-Json
