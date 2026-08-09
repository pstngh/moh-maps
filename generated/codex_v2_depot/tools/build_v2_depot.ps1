[CmdletBinding()]
param(
    [string]$MapName = "codex_v2_depot",
    [string]$GeneratedRoot = "",
    [string]$RetailRoot = "",
    [string]$MOHToolsDir = "",
    [string]$NodePath = "",
    [int]$Threads = 4,
    [switch]$SkipGenerate,
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
if ($MapName -notmatch "^[A-Za-z0-9_]+$") { throw "MapName may contain only letters, numbers, and underscores" }
if ($Threads -lt 1) { throw "Threads must be positive" }
if (-not $GeneratedRoot) { $GeneratedRoot = Join-Path $PSScriptRoot ".." }
$GeneratedRoot = [IO.Path]::GetFullPath($GeneratedRoot)
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$workRoot = Split-Path -Parent $repositoryRoot
if (-not $RetailRoot) { $RetailRoot = Join-Path $workRoot "runtime_base_stock" }
if (-not $MOHToolsDir) { $MOHToolsDir = Join-Path $workRoot "MOHTools" }
if (-not $NodePath) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { $nodeCommand = Get-Command node -ErrorAction SilentlyContinue }
    if (-not $nodeCommand) { throw "-NodePath is required because Node.js is not on PATH" }
    $NodePath = $nodeCommand.Source
}
$RetailRoot = [IO.Path]::GetFullPath($RetailRoot)
$MOHToolsDir = [IO.Path]::GetFullPath($MOHToolsDir)
$NodePath = [IO.Path]::GetFullPath($NodePath)

$generator = Join-Path $PSScriptRoot "generate_v2_depot.js"
$validator = Join-Path $PSScriptRoot "validate_v2_depot.js"
$inspector = Join-Path $repositoryRoot "tools\inspect_aa_bsp.js"
$q3map = Join-Path $MOHToolsDir "Q3map.exe"
$mohlight = Join-Path $MOHToolsDir "MOHlight.exe"
foreach ($required in @($generator, $validator, $inspector, $q3map, $mohlight, $NodePath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build input: $required" }
}

$retailPackDirectory = ""
foreach ($candidate in @($RetailRoot, (Join-Path $RetailRoot "main"))) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) { continue }
    $lookup = @{}
    foreach ($pack in Get-ChildItem -LiteralPath $candidate -Filter "*.pk3" -File) { $lookup[$pack.Name.ToLowerInvariant()] = $pack }
    if (@(0..6 | Where-Object { -not $lookup.ContainsKey("pak$_.pk3") }).Count -eq 0) {
        $retailPackDirectory = $candidate
        $retailPackLookup = $lookup
        break
    }
}
if (-not $retailPackDirectory) { throw "Retail Pak0.pk3 through Pak6.pk3 were not found under $RetailRoot" }
$retailPaks = @(0..6 | ForEach-Object { $retailPackLookup["pak$_.pk3"] })

$canonicalMapRoot = Join-Path $GeneratedRoot "main\maps\dm"
$canonicalMap = Join-Path $canonicalMapRoot "$MapName.map"
$canonicalBsp = Join-Path $canonicalMapRoot "$MapName.bsp"
$canonicalScript = Join-Path $canonicalMapRoot "$MapName.scr"
$canonicalPrecache = Join-Path $canonicalMapRoot "${MapName}_precache.scr"
$designReportPath = Join-Path $GeneratedRoot "$MapName-design-report.json"
$validationReportPath = Join-Path $GeneratedRoot "$MapName-validation.json"
$bspReportPath = Join-Path $GeneratedRoot "$MapName-bsp.json"
$buildReportPath = Join-Path $GeneratedRoot "$MapName-build-report.json"
$packagePath = Join-Path $GeneratedRoot "$MapName.pk3"
$buildRoot = Join-Path $GeneratedRoot ".build"
$compileRoot = Join-Path $buildRoot "compile"
$compileMain = Join-Path $compileRoot "main"
$compileMapRoot = Join-Path $compileMain "maps\dm"
$compileMap = Join-Path $compileMapRoot "$MapName.map"
$compileBsp = Join-Path $compileMapRoot "$MapName.bsp"

if (-not $SkipGenerate -and -not $PackageOnly) {
    & $NodePath $generator $MapName $GeneratedRoot
    if ($LASTEXITCODE -ne 0) { throw "Map generation failed" }
}
foreach ($required in @($canonicalMap, $canonicalScript, $canonicalPrecache, $designReportPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing generated source: $required" }
}
& $NodePath $validator $GeneratedRoot $MapName | Out-File -LiteralPath $validationReportPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Source validation failed" }
$validation = Get-Content -Raw -LiteralPath $validationReportPath | ConvertFrom-Json

$stageResults = [ordered]@{}
if (-not $PackageOnly) {
    if (Test-Path -LiteralPath $buildRoot) {
        $resolvedBuild = [IO.Path]::GetFullPath($buildRoot)
        $expectedBuild = [IO.Path]::GetFullPath((Join-Path $GeneratedRoot ".build"))
        if (-not $resolvedBuild.Equals($expectedBuild, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to clean unexpected build root: $resolvedBuild" }
        Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
    }
    New-Item -ItemType Directory -Path $compileMapRoot -Force | Out-Null

    $reproRoot = Join-Path $buildRoot "generation-repro"
    & $NodePath $generator $MapName $reproRoot | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Clean-root reproducibility generation failed" }
    foreach ($relative in @("main\maps\dm\$MapName.map", "main\maps\dm\$MapName.scr", "main\maps\dm\${MapName}_precache.scr", "$MapName-design-report.json")) {
        $canonical = Join-Path $GeneratedRoot $relative
        $reproduced = Join-Path $reproRoot $relative
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $canonical).Hash -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $reproduced).Hash) {
            throw "Generation reproducibility mismatch: $relative"
        }
    }
    $stageResults.generationReproduced = $true

    foreach ($pack in $retailPaks) {
        $destination = Join-Path $compileMain $pack.Name
        try { New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null }
        catch { Copy-Item -LiteralPath $pack.FullName -Destination $destination }
    }
    if (@(Get-ChildItem -LiteralPath $compileMain -Filter "Pak*.pk3" -File).Count -ne 7) { throw "Compile root must expose exactly Pak0.pk3 through Pak6.pk3" }
    foreach ($source in @($canonicalMap, $canonicalScript, $canonicalPrecache)) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $compileMapRoot (Split-Path -Leaf $source))
    }

    $q3mapLog = Join-Path $buildRoot "q3map.log"
    $visLog = Join-Path $buildRoot "vis.log"
    $lightLog = Join-Path $buildRoot "mohlight.log"

    $timer = [Diagnostics.Stopwatch]::StartNew()
    & $q3map -threads $Threads -gamedir $compileRoot -moddir main $compileMap 2>&1 | Tee-Object -FilePath $q3mapLog
    $q3mapExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.q3mapSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($q3mapExit -ne 0) { throw "Q3map failed with exit code $q3mapExit" }
    $q3mapLines = @(Get-Content -LiteralPath $q3mapLog)
    $q3mapFatal = @($q3mapLines | Where-Object { $_ -match "Couldn.t find image|ERROR:|MAX_[A-Z_]+|is incomplete|LEAKED|invalid brush|degenerate" })
    $q3mapWarnings = @($q3mapLines | Where-Object { $_ -match "^WARNING" })
    if ($q3mapFatal.Count) { throw "Fatal Q3map diagnostics: $($q3mapFatal -join ' | ')" }
    if ($q3mapWarnings.Count) { throw "Unexpected Q3map warnings: $($q3mapWarnings -join ' | ')" }

    $timer.Restart()
    & $q3map -vis -fast -threads $Threads -gamedir $compileRoot -moddir main $compileBsp 2>&1 | Tee-Object -FilePath $visLog
    $visExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.visSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($visExit -ne 0) { throw "VIS failed with exit code $visExit" }

    $timer.Restart()
    & $mohlight -threads $Threads -gamedir $compileRoot -moddir main $compileMap 2>&1 | Tee-Object -FilePath $lightLog
    $lightExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.mohlightSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($lightExit -ne 0) { throw "MOHlight failed with exit code $lightExit" }
    $lightLines = @(Get-Content -LiteralPath $lightLog)
    $lightFatal = @($lightLines | Where-Object { $_ -match "ERROR:|MAX_[A-Z_]+|access violation" })
    if ($lightFatal.Count) { throw "Fatal MOHlight diagnostics: $($lightFatal -join ' | ')" }
    $stageResults.q3mapWarnings = $q3mapWarnings.Count
    $stageResults.lightClampWarnings = @($lightLines | Where-Object { $_ -match "Num lights per leaf clamped" }).Count
    $stageResults.lightHashWarnings = @($lightLines | Where-Object { $_ -match "potential hash mismatch" }).Count
    if ($stageResults.lightClampWarnings -ne 0 -or $stageResults.lightHashWarnings -ne 0) { throw "Unexpected MOHlight clamp/hash warning" }
    Copy-Item -LiteralPath $compileBsp -Destination $canonicalBsp -Force
}

if (-not (Test-Path -LiteralPath $canonicalBsp -PathType Leaf)) { throw "No compiled BSP is available: $canonicalBsp" }
& $NodePath $inspector $canonicalBsp $repositoryRoot | Out-File -LiteralPath $bspReportPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "BSP inspection failed" }
$bspInspection = Get-Content -Raw -LiteralPath $bspReportPath | ConvertFrom-Json
foreach ($pair in @(@("info_player_deathmatch", 18), @("info_player_allied", 8), @("info_player_axis", 8), @("info_player_start", 1))) {
    if ($bspInspection.classCounts.($pair[0]) -ne $pair[1]) { throw "Compiled entity count mismatch for $($pair[0])" }
}
if ($bspInspection.visibilityBytes -le 0 -or $bspInspection.lightmapPages -le 0) { throw "Compiled BSP lacks VIS or lightmaps" }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$entries = @(
    [pscustomobject]@{ Source = $canonicalBsp; Entry = "maps/dm/$MapName.bsp" },
    [pscustomobject]@{ Source = $canonicalScript; Entry = "maps/dm/$MapName.scr" },
    [pscustomobject]@{ Source = $canonicalPrecache; Entry = "maps/dm/${MapName}_precache.scr" }
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
                try { $output = $zipEntry.Open(); try { $input.CopyTo($output) } finally { $output.Dispose() } } finally { $input.Dispose() }
            }
        } finally { $archive.Dispose() }
    } finally { $stream.Dispose() }
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
        foreach ($zipEntry in $archive.Entries) {
            if ($zipEntry.FullName.Contains("\") -or $zipEntry.FullName.Split("/") -contains "..") { throw "Unsafe package entry: $($zipEntry.FullName)" }
            if ($zipEntry.LastWriteTime.DateTime -ne $fixedTimestamp.DateTime) { throw "Nondeterministic timestamp: $($zipEntry.FullName)" }
        }
    } finally { $archive.Dispose() }
} finally { $packageStream.Dispose() }

$buildReport = [ordered]@{
    schemaVersion = 1
    mapName = $MapName
    retailPaks = @($retailPaks | ForEach-Object { [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() } })
    validation = $validation
    stages = $stageResults
    map = [ordered]@{ bytes = (Get-Item -LiteralPath $canonicalMap).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalMap).Hash.ToLowerInvariant() }
    bsp = $bspInspection
    package = [ordered]@{ entries = $entries.Count; bytes = (Get-Item -LiteralPath $packagePath).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant(); reproducedTwice = $true }
}
[IO.File]::WriteAllText($buildReportPath, (($buildReport | ConvertTo-Json -Depth 10) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "Built $packagePath"
Write-Output "SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash)"
