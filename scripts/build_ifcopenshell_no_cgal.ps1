param([Parameter(Mandatory=$true)][string]$BuildRoot)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 is required.' }
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'Use the dedicated disposable Windows CI runner, not an existing desktop installation.'
}
$repoRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = [IO.Path]::GetFullPath($BuildRoot)
if (-not $nativeRoot.StartsWith([IO.Path]::GetFullPath($env:RUNNER_TEMP)+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'BuildRoot must be inside RUNNER_TEMP.'
}
New-Item -ItemType Directory -Force -Path $nativeRoot | Out-Null
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}
$manifest = Get-Content -Raw (Join-Path $repoRoot 'packaging/native-sources.json') | ConvertFrom-Json
$sourceRoot = Join-Path $nativeRoot 'sources'
$archiveRoot = Join-Path $nativeRoot 'archives'
$installRoot = Join-Path $nativeRoot 'install'
$evidenceRoot = Join-Path $nativeRoot 'evidence'
New-Item -ItemType Directory -Force -Path $sourceRoot,$archiveRoot,$installRoot,$evidenceRoot | Out-Null
$trees = @{}
foreach ($entry in $manifest) {
    $archive = Join-Path $archiveRoot $entry.name
    if ($entry.commit) {
        $checkout = Join-Path $repoRoot ".native-sources/$($entry.id)"
        $revision = (& git -C $checkout rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $revision -ne $entry.commit) { throw 'Native source revision mismatch.' }
        Invoke-Checked 'git' @('-C',$checkout,'archive','--format=tar',"--prefix=$($entry.id)/","--output=$archive",'HEAD')
        $trees[$entry.id]=$checkout
        continue
    }
    if (-not (Test-Path -LiteralPath $archive)) { Invoke-WebRequest -Uri $entry.url -OutFile $archive }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Source digest mismatch: $($entry.name)"
    }
    $destination=Join-Path $sourceRoot $entry.id
    if (-not (Test-Path -LiteralPath $destination)) {
        New-Item -ItemType Directory -Path $destination | Out-Null
        Invoke-Checked 'tar.exe' @('-xf',$archive,'-C',$destination,'--strip-components=1')
    }
    $trees[$entry.id]=$destination
}
$generator=@('-G','Visual Studio 17 2022','-A','x64')
$occtBuild=Join-Path $nativeRoot 'occt-build'
$occtInstall=Join-Path $installRoot 'occt'
Invoke-Checked 'cmake' (@('-S',$trees.occt,'-B',$occtBuild)+$generator+@(
    "-DCMAKE_INSTALL_PREFIX=$occtInstall",'-DINSTALL_DIR_LAYOUT=Unix','-DBUILD_LIBRARY_TYPE=Shared',
    '-DBUILD_MODULE_Draw=OFF','-DBUILD_MODULE_Visualization=ON','-DUSE_FREETYPE=OFF',
    '-DUSE_TK=OFF','-DUSE_TBB=OFF','-DUSE_FREEIMAGE=OFF','-DUSE_FFMPEG=OFF',
    '-DUSE_VTK=OFF','-DUSE_RAPIDJSON=OFF','-DBUILD_DOC_Overview=OFF'))
Invoke-Checked 'cmake' @('--build',$occtBuild,'--config','Release','--parallel','4')
Invoke-Checked 'cmake' @('--install',$occtBuild,'--config','Release')
$boostBuild=Join-Path $nativeRoot 'boost-build'
$boostInstall=Join-Path $installRoot 'boost'
Invoke-Checked 'cmake' (@('-S',$trees.boost,'-B',$boostBuild)+$generator+@(
    "-DCMAKE_INSTALL_PREFIX=$boostInstall",'-DBUILD_SHARED_LIBS=OFF','-DBUILD_TESTING=OFF',
    '-DBOOST_INCLUDE_LIBRARIES=system;program_options;regex;thread;date_time;iostreams',
    '-DBOOST_IOSTREAMS_ENABLE_ZLIB=OFF','-DBOOST_IOSTREAMS_ENABLE_BZIP2=OFF',
    '-DBOOST_IOSTREAMS_ENABLE_LZMA=OFF','-DBOOST_IOSTREAMS_ENABLE_ZSTD=OFF'))
Invoke-Checked 'cmake' @('--build',$boostBuild,'--config','Release','--parallel','4')
Invoke-Checked 'cmake' @('--install',$boostBuild,'--config','Release')
$ifcBuild=Join-Path $nativeRoot 'ifc-build'
$ifcInstall=Join-Path $installRoot 'ifc'
$pythonBase=(& python -c 'import sys; print(sys.base_prefix)').Trim()
$pythonExecutable=(& python -c 'import sys; print(sys.executable)').Trim()
$occConfig=(Get-ChildItem -LiteralPath $occtInstall -Filter OpenCASCADEConfig.cmake -Recurse | Select-Object -First 1).DirectoryName
if (-not $occConfig) { throw 'Built OCCT config not found.' }
Invoke-Checked 'cmake' (@('-S',(Join-Path $trees.ifcopenshell 'cmake'),'-B',$ifcBuild)+$generator+@(
    '-DWITH_CGAL=OFF','-DWITH_OPENCASCADE=ON','-DBUILD_IFCPYTHON=ON',
    '-DBUILD_CONVERT=OFF','-DBUILD_GEOMSERVER=OFF','-DBUILD_EXAMPLES=OFF',
    '-DBUILD_ONLY_COMMON_SCHEMAS=OFF','-DCOLLADA_SUPPORT=OFF','-DGLTF_SUPPORT=OFF',
    '-DHDF5_SUPPORT=OFF','-DIFCXML_SUPPORT=OFF','-DWITH_PROJ=OFF','-DUSD_SUPPORT=OFF',
    '-DWITH_ROCKSDB=OFF','-DWITH_ZSTD=OFF','-DBUILD_QTVIEWER=OFF',
    '-DENABLE_BUILD_OPTIMIZATIONS=OFF','-DVERSION_OVERRIDE=ON','-DADD_COMMIT_SHA=OFF',
    "-DOpenCASCADE_DIR=$occConfig","-DCMAKE_PREFIX_PATH=$boostInstall",'-DBoost_NO_BOOST_CMAKE=OFF',
    "-DEIGEN_DIR=$($trees.eigen)","-DPYTHON_EXECUTABLE=$pythonExecutable",
    "-DPYTHON_INCLUDE_DIR=$pythonBase/include","-DPYTHON_LIBRARY=$pythonBase/libs/python313.lib",
    "-DPYTHON_MODULE_INSTALL_DIR=$ifcInstall","-DCMAKE_INSTALL_PREFIX=$ifcInstall"))
Copy-Item -LiteralPath (Join-Path $ifcBuild 'CMakeCache.txt') -Destination (Join-Path $evidenceRoot 'IfcOpenShell-CMakeCache.txt')
Copy-Item -LiteralPath (Join-Path $occtBuild 'CMakeCache.txt') -Destination (Join-Path $evidenceRoot 'OCCT-CMakeCache.txt')
Copy-Item -LiteralPath (Join-Path $boostBuild 'CMakeCache.txt') -Destination (Join-Path $evidenceRoot 'Boost-CMakeCache.txt')
Invoke-Checked 'cmake' @('--build',$ifcBuild,'--config','Release','--target','ifcopenshell_wrapper','--parallel','2')
Invoke-Checked 'cmake' @('--install',$ifcBuild,'--config','Release')
Invoke-Checked 'python' @((Join-Path $repoRoot 'scripts/assemble_no_cgal_wheel.py'),$nativeRoot)
