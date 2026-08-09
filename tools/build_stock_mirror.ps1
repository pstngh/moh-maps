[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedRoot,
    [string]$RetailRoot = "",
    [string]$MOHToolsDir = "",
    [string]$NodePath = "",
    [int]$Threads = 4,
    [switch]$SkipGenerate,
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
if ($Threads -lt 1) { throw "Threads must be positive" }

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Split-Path -Parent $repositoryRoot
$GeneratedRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $GeneratedRoot))
if (-not $GeneratedRoot.StartsWith((Join-Path $repositoryRoot "generated"), [StringComparison]::OrdinalIgnoreCase)) {
    throw "GeneratedRoot must resolve below the repository generated directory"
}
$configPath = Join-Path $GeneratedRoot "mirror-config.json"
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "Missing mirror config: $configPath" }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
if ($config.schemaVersion -ne 1) { throw "Unexpected mirror config schema" }
if ($config.mapName -notmatch "^[A-Za-z0-9_]+$") { throw "Unsafe map name" }
if ($config.gameDirectory -notin @("dm", "obj")) { throw "Game directory must be dm or obj" }
if ($config.originalMap -notmatch "^[A-Za-z0-9_]+$") { throw "Unsafe original map name" }
$sourceMap = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $config.sourceMap))
if (-not $sourceMap.StartsWith($repositoryRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Source MAP resolves outside the repository" }

if (-not $RetailRoot) { $RetailRoot = Join-Path $workRoot "runtime_base_stock" }
if (-not $MOHToolsDir) { $MOHToolsDir = Join-Path $workRoot "MOHTools" }
$RetailRoot = [IO.Path]::GetFullPath($RetailRoot)
$MOHToolsDir = [IO.Path]::GetFullPath($MOHToolsDir)
if (-not $NodePath) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { $nodeCommand = Get-Command node -ErrorAction SilentlyContinue }
    if (-not $nodeCommand) { throw "-NodePath is required because Node.js is not on PATH" }
    $NodePath = $nodeCommand.Source
}
$NodePath = [IO.Path]::GetFullPath($NodePath)

$generator = Join-Path $PSScriptRoot "mirror_stock_map.js"
$validator = Join-Path $PSScriptRoot "validate_stock_mirror.js"
$inspector = Join-Path $PSScriptRoot "inspect_aa_bsp.js"
$q3map = Join-Path $MOHToolsDir "Q3map.exe"
$mohlight = Join-Path $MOHToolsDir "MOHlight.exe"
foreach ($required in @($sourceMap, $generator, $validator, $inspector, $q3map, $mohlight, $NodePath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build input: $required" }
}

$retailPackDirectory = ""
foreach ($candidate in @($RetailRoot, (Join-Path $RetailRoot "main"))) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) { continue }
    $lookup = @{}
    foreach ($pack in Get-ChildItem -LiteralPath $candidate -Filter "*.pk3" -File) {
        $lookup[$pack.Name.ToLowerInvariant()] = $pack
    }
    $complete = $true
    foreach ($number in 0..6) {
        if (-not $lookup.ContainsKey("pak$number.pk3")) { $complete = $false; break }
    }
    if ($complete) { $retailPackDirectory = $candidate; $retailPackLookup = $lookup; break }
}
if (-not $retailPackDirectory) { throw "Retail Pak0.pk3 through Pak6.pk3 were not found under $RetailRoot" }
$retailPaks = @(0..6 | ForEach-Object { $retailPackLookup["pak$_.pk3"] })

$mapName = $config.mapName
$gameDirectory = $config.gameDirectory
$lightThreads = if ($config.lightThreads) { [int]$config.lightThreads } else { $Threads }
if ($lightThreads -lt 1) { throw "lightThreads must be positive" }
$terrainControlMode = if ($config.terrainControlMode) { [string]$config.terrainControlMode } else { "cell-sentinel" }
if ($terrainControlMode -notin @("cell-sentinel", "legacy-full-row")) { throw "Unsupported terrainControlMode: $terrainControlMode" }
$q3mapArguments = @($config.q3mapArgs | ForEach-Object { [string]$_ } | Where-Object { $_ })
$allowedQ3mapArguments = @("-nomanvis")
foreach ($argument in $q3mapArguments) {
    if ($argument -notin $allowedQ3mapArguments) { throw "Unsupported q3mapArgs value: $argument" }
}
$canonicalMapRoot = Join-Path $GeneratedRoot "main\maps\$gameDirectory"
$canonicalMap = Join-Path $canonicalMapRoot "$mapName.map"
$canonicalBsp = Join-Path $canonicalMapRoot "$mapName.bsp"
$canonicalScript = Join-Path $canonicalMapRoot "$mapName.scr"
$canonicalPrecache = Join-Path $canonicalMapRoot "${mapName}_precache.scr"
$mirrorReport = Join-Path $GeneratedRoot "$mapName-mirror-report.json"
$validationReport = Join-Path $GeneratedRoot "$mapName-validation.json"
$bspReport = Join-Path $GeneratedRoot "$mapName-bsp.json"
$buildReportPath = Join-Path $GeneratedRoot "$mapName-build-report.json"
$packagePath = Join-Path $GeneratedRoot "$mapName.pk3"
$buildRoot = Join-Path $GeneratedRoot ".build"
$buildMain = Join-Path $buildRoot "main"
$buildMapRoot = Join-Path $buildMain "maps\$gameDirectory"
$buildMap = Join-Path $buildMapRoot "$mapName.map"
$buildBsp = Join-Path $buildMapRoot "$mapName.bsp"

if (-not $SkipGenerate -and -not $PackageOnly) {
    $generatorArguments = @($generator, "--source", $sourceMap, "--output-root", $GeneratedRoot, "--map-name", $mapName, "--game-directory", $gameDirectory, "--original-map", $config.originalMap, "--display-name", $config.displayName, "--terrain-control-mode", $terrainControlMode)
    $extraPrecache = @($config.extraPrecache) -join ";"
    if ($extraPrecache) { $generatorArguments += @("--extra-precache", $extraPrecache) }
    & $NodePath @generatorArguments
    if ($LASTEXITCODE -ne 0) { throw "Mirror generation failed with exit code $LASTEXITCODE" }
}
foreach ($required in @($canonicalMap, $canonicalScript, $canonicalPrecache, $mirrorReport)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing generated source: $required" }
}
& $NodePath $validator --output-root $GeneratedRoot | Out-File -LiteralPath $validationReport -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Mirror validation failed" }

$stageResults = [ordered]@{}
if ($PackageOnly -and (Test-Path -LiteralPath $buildReportPath -PathType Leaf)) {
    $previousBuild = Get-Content -Raw -LiteralPath $buildReportPath | ConvertFrom-Json
    foreach ($property in $previousBuild.stages.PSObject.Properties) {
        $stageResults[$property.Name] = $property.Value
    }
}
if (-not $PackageOnly) {
    if (Test-Path -LiteralPath $buildRoot) {
        $resolvedBuild = [IO.Path]::GetFullPath($buildRoot)
        $expectedBuild = [IO.Path]::GetFullPath((Join-Path $GeneratedRoot ".build"))
        if (-not $resolvedBuild.Equals($expectedBuild, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected build root: $resolvedBuild"
        }
        Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildMapRoot -Force | Out-Null
    foreach ($pack in $retailPaks) {
        $destination = Join-Path $buildMain $pack.Name
        try { New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null }
        catch { Copy-Item -LiteralPath $pack.FullName -Destination $destination }
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    foreach ($assetPath in @($config.looseBuildInputs)) {
        if (-not $assetPath) { continue }
        if ($assetPath.StartsWith("/") -or $assetPath.Contains("\") -or $assetPath.Split("/") -contains "..") {
            throw "Unsafe loose build input: $assetPath"
        }
        $found = $false
        foreach ($pack in @($retailPaks | Sort-Object Name -Descending)) {
            $archive = [IO.Compression.ZipFile]::OpenRead($pack.FullName)
            try {
                $entry = @($archive.Entries | Where-Object { $_.FullName.Equals($assetPath, [StringComparison]::OrdinalIgnoreCase) }) | Select-Object -First 1
                if ($entry) {
                    $destination = Join-Path $buildMain ($assetPath.Replace("/", "\"))
                    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
                    $found = $true
                    break
                }
            }
            finally { $archive.Dispose() }
        }
        if (-not $found) { throw "Loose build input was not found in retail Pak0-Pak6: $assetPath" }
    }
    foreach ($source in @($canonicalMap, $canonicalScript, $canonicalPrecache)) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $buildMapRoot (Split-Path -Leaf $source))
    }

    $q3mapLog = Join-Path $buildRoot "q3map.log"
    $visLog = Join-Path $buildRoot "vis.log"
    $lightLog = Join-Path $buildRoot "mohlight.log"

    $stageResults.q3mapArgs = @($q3mapArguments)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    & $q3map -threads $Threads @q3mapArguments -gamedir $buildRoot -moddir main $buildMap 2>&1 | Tee-Object -FilePath $q3mapLog
    $q3mapExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.q3mapSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($q3mapExit -ne 0 -or -not (Test-Path -LiteralPath $buildBsp -PathType Leaf)) { throw "Q3map failed with exit code $q3mapExit" }
    $q3mapLines = @(Get-Content -LiteralPath $q3mapLog)
    $q3mapFatal = @($q3mapLines | Where-Object { $_ -match "ERROR:|MAX_[A-Z_]+|is incomplete|invalid brush" })
    if ($q3mapFatal.Count) { throw "Fatal Q3map diagnostics: $($q3mapFatal -join ' | ')" }
    $stageResults.q3mapWarnings = @($q3mapLines | Where-Object { $_ -match "^WARNING" }).Count
    $stageResults.q3mapMissingImageWarnings = @($q3mapLines | Where-Object { $_ -match "(?i)Couldn.t find image" }).Count
    $stageResults.q3mapLeakDiagnostics = @($q3mapLines | Where-Object { $_ -match "(?i)leaked" }).Count
    $stageResults.q3mapDegenerateDiagnostics = @($q3mapLines | Where-Object { $_ -match "(?i)degenerate" }).Count

    $timer.Restart()
    & $q3map -vis -fast -threads $Threads -gamedir $buildRoot -moddir main $buildBsp 2>&1 | Tee-Object -FilePath $visLog
    $visExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.visSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($visExit -ne 0) { throw "VIS failed with exit code $visExit" }

    $timer.Restart()
    & $mohlight -threads $lightThreads -gamedir $buildRoot -moddir main $buildMap 2>&1 | Tee-Object -FilePath $lightLog
    $lightExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.mohlightSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    $stageResults.mohlightThreads = $lightThreads
    if ($lightExit -ne 0) { throw "MOHlight failed with exit code $lightExit" }
    $lightLines = @(Get-Content -LiteralPath $lightLog)
    $lightFatal = @($lightLines | Where-Object { $_ -match "ERROR:|MAX_[A-Z_]+|access violation" })
    if ($lightFatal.Count) { throw "Fatal MOHlight diagnostics: $($lightFatal -join ' | ')" }
    $stageResults.lightClampWarnings = @($lightLines | Where-Object { $_ -match "Num lights per leaf clamped" }).Count
    $stageResults.lightHashWarnings = @($lightLines | Where-Object { $_ -match "potential hash mismatch" }).Count
    Copy-Item -LiteralPath $buildBsp -Destination $canonicalBsp -Force
}

if (-not (Test-Path -LiteralPath $canonicalBsp -PathType Leaf)) { throw "No compiled BSP is available to package" }
& $NodePath $inspector $canonicalBsp $repositoryRoot | Out-File -LiteralPath $bspReport -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Final BSP inspection failed" }
$bspInspection = Get-Content -Raw -LiteralPath $bspReport | ConvertFrom-Json

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$entries = @(
    [pscustomobject]@{ Source = $canonicalBsp; Entry = "maps/$gameDirectory/$mapName.bsp" },
    [pscustomobject]@{ Source = $canonicalScript; Entry = "maps/$gameDirectory/$mapName.scr" },
    [pscustomobject]@{ Source = $canonicalPrecache; Entry = "maps/$gameDirectory/${mapName}_precache.scr" }
) | Sort-Object Entry
$fixedTimestamp = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
function New-DeterministicPackage {
    param([string]$Destination, [object[]]$PackageEntries)
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force }
    $stream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $archive = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
        try {
            foreach ($item in $PackageEntries) {
                $zipEntry = $archive.CreateEntry($item.Entry, [IO.Compression.CompressionLevel]::Optimal)
                $zipEntry.LastWriteTime = $fixedTimestamp
                $input = [IO.File]::OpenRead($item.Source)
                try { $output = $zipEntry.Open(); try { $input.CopyTo($output) } finally { $output.Dispose() } }
                finally { $input.Dispose() }
            }
        }
        finally { $archive.Dispose() }
    }
    finally { $stream.Dispose() }
}

$firstPackage = "$packagePath.first"
$secondPackage = "$packagePath.second"
New-DeterministicPackage $firstPackage $entries
New-DeterministicPackage $secondPackage $entries
$firstHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $firstPackage).Hash
$secondHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $secondPackage).Hash
if ($firstHash -ne $secondHash -or (Get-Item $firstPackage).Length -ne (Get-Item $secondPackage).Length) { throw "Package reproducibility mismatch" }
if (Test-Path -LiteralPath $packagePath) { Remove-Item -LiteralPath $packagePath -Force }
Move-Item -LiteralPath $firstPackage -Destination $packagePath
Remove-Item -LiteralPath $secondPackage -Force

$packageStream = [IO.File]::OpenRead($packagePath)
try {
    $archive = [IO.Compression.ZipArchive]::new($packageStream, [IO.Compression.ZipArchiveMode]::Read, $false)
    try {
        if ($archive.Entries.Count -ne $entries.Count) { throw "Package entry count mismatch" }
        foreach ($item in $entries) {
            $zipEntry = $archive.GetEntry($item.Entry)
            if (-not $zipEntry) { throw "Missing package entry: $($item.Entry)" }
            if ($zipEntry.LastWriteTime.DateTime -ne $fixedTimestamp.DateTime) { throw "Nondeterministic timestamp: $($item.Entry)" }
            $entryStream = $zipEntry.Open()
            try { $sha = [Security.Cryptography.SHA256]::Create(); try { $archiveHash = ([BitConverter]::ToString($sha.ComputeHash($entryStream))).Replace("-", "") } finally { $sha.Dispose() } }
            finally { $entryStream.Dispose() }
            if ($archiveHash -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $item.Source).Hash) { throw "Package hash mismatch: $($item.Entry)" }
        }
    }
    finally { $archive.Dispose() }
}
finally { $packageStream.Dispose() }

$mirror = Get-Content -Raw -LiteralPath $mirrorReport | ConvertFrom-Json
$buildReport = [ordered]@{
    schemaVersion = 1
    mapName = $mapName
    gameDirectory = $gameDirectory
    source = [ordered]@{ path = $config.sourceMap; bytes = (Get-Item $sourceMap).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceMap).Hash.ToLowerInvariant() }
    transform = $mirror.transform
    terrainControlMode = $terrainControlMode
    transformed = $mirror.transformed
    retailPaks = @($retailPaks | ForEach-Object { [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() } })
    stages = $stageResults
    map = [ordered]@{ bytes = (Get-Item $canonicalMap).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalMap).Hash.ToLowerInvariant() }
    bsp = $bspInspection
    package = [ordered]@{ entries = $entries.Count; bytes = (Get-Item $packagePath).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant(); reproducedTwice = $true }
}
[IO.File]::WriteAllText($buildReportPath, (($buildReport | ConvertTo-Json -Depth 10) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "Built $packagePath"
Write-Output "SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash)"
