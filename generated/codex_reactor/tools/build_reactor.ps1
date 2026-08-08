[CmdletBinding()]
param(
    [string]$MapName = "codex_reactor",
    [string]$GeneratedRoot = "",
    [string]$RetailRoot = "",
    [string]$MOHToolsDir = "",
    [string]$NodePath = "",
    [int]$Threads = 4,
    [switch]$SkipGenerate,
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
if ($MapName -notmatch "^[A-Za-z0-9_]+$") {
    throw "MapName may contain only letters, numbers, and underscores"
}
if ($Threads -lt 1) { throw "Threads must be positive" }

if (-not $GeneratedRoot) { $GeneratedRoot = Join-Path $PSScriptRoot ".." }
$GeneratedRoot = [System.IO.Path]::GetFullPath($GeneratedRoot)
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$workRoot = Split-Path -Parent $repositoryRoot
if (-not $RetailRoot) { $RetailRoot = Join-Path $workRoot "runtime_base_stock" }
if (-not $MOHToolsDir) { $MOHToolsDir = Join-Path $workRoot "MOHTools" }
$RetailRoot = [System.IO.Path]::GetFullPath($RetailRoot)
$MOHToolsDir = [System.IO.Path]::GetFullPath($MOHToolsDir)
if (-not $NodePath) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { $nodeCommand = Get-Command node -ErrorAction SilentlyContinue }
    if (-not $nodeCommand) { throw "-NodePath is required because Node.js is not on PATH" }
    $NodePath = $nodeCommand.Source
}
$NodePath = [System.IO.Path]::GetFullPath($NodePath)

$generator = Join-Path $PSScriptRoot "generate_reactor.js"
$validator = Join-Path $PSScriptRoot "validate_reactor.js"
$inspector = Join-Path $PSScriptRoot "inspect_reactor_bsp.js"
$q3map = Join-Path $MOHToolsDir "Q3map.exe"
$mohlight = Join-Path $MOHToolsDir "MOHlight.exe"
foreach ($required in @($generator, $validator, $inspector, $q3map, $mohlight, $NodePath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing build input: $required"
    }
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
if (-not $retailPackDirectory) {
    throw "Retail Pak0.pk3 through Pak6.pk3 were not found under $RetailRoot"
}
$retailPaks = @(0..6 | ForEach-Object { $retailPackLookup["pak$_.pk3"] })

$canonicalMain = Join-Path $GeneratedRoot "main"
$canonicalMapRoot = Join-Path $canonicalMain "maps\dm"
$canonicalMap = Join-Path $canonicalMapRoot "$MapName.map"
$canonicalBsp = Join-Path $canonicalMapRoot "$MapName.bsp"
$canonicalScript = Join-Path $canonicalMapRoot "$MapName.scr"
$canonicalPrecache = Join-Path $canonicalMapRoot "${MapName}_precache.scr"
$designReport = Join-Path $GeneratedRoot "$MapName-design-report.json"
$validationReport = Join-Path $GeneratedRoot "$MapName-validation.json"
$buildReportPath = Join-Path $GeneratedRoot "$MapName-build-report.json"
$packagePath = Join-Path $GeneratedRoot "$MapName.pk3"
$buildRoot = Join-Path $GeneratedRoot ".build"
$buildMain = Join-Path $buildRoot "main"
$buildMapRoot = Join-Path $buildMain "maps\dm"
$buildMap = Join-Path $buildMapRoot "$MapName.map"
$buildBsp = Join-Path $buildMapRoot "$MapName.bsp"
$textureSourceRoot = Join-Path $repositoryRoot "generated\codex_nuke\main\textures\codex_nuke"

if (-not $SkipGenerate -and -not $PackageOnly) {
    & $NodePath $generator $MapName $GeneratedRoot
    if ($LASTEXITCODE -ne 0) { throw "Map generation failed with exit code $LASTEXITCODE" }
}
foreach ($required in @($canonicalMap, $canonicalScript, $canonicalPrecache, $designReport)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing generated source: $required" }
}
& $NodePath $validator $GeneratedRoot $MapName | Out-File -LiteralPath $validationReport -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Source validation failed" }
$design = Get-Content -LiteralPath $designReport -Raw | ConvertFrom-Json

$stageResults = [ordered]@{}
if (-not $PackageOnly) {
    if (Test-Path -LiteralPath $buildRoot) {
        $resolvedBuild = [System.IO.Path]::GetFullPath($buildRoot)
        $expectedBuild = [System.IO.Path]::GetFullPath((Join-Path $GeneratedRoot ".build"))
        if (-not $resolvedBuild.Equals($expectedBuild, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected build root: $resolvedBuild"
        }
        Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildMapRoot -Force | Out-Null

    foreach ($pack in $retailPaks) {
        $destination = Join-Path $buildMain $pack.Name
        try {
            New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null
        }
        catch {
            Copy-Item -LiteralPath $pack.FullName -Destination $destination
        }
    }
    foreach ($source in @($canonicalMap, $canonicalScript, $canonicalPrecache)) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $buildMapRoot (Split-Path -Leaf $source))
    }
    $buildTextureRoot = Join-Path $buildMain "textures\codex_nuke"
    New-Item -ItemType Directory -Path $buildTextureRoot -Force | Out-Null
    foreach ($textureName in @($design.materials.bundledOriginalTextures)) {
        $source = Join-Path $textureSourceRoot $textureName
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing texture source: $source" }
        Copy-Item -LiteralPath $source -Destination (Join-Path $buildTextureRoot $textureName)
    }

    $q3mapLog = Join-Path $buildRoot "q3map.log"
    $visLog = Join-Path $buildRoot "vis.log"
    $lightLog = Join-Path $buildRoot "mohlight.log"

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    & $q3map -threads $Threads -gamedir $buildRoot -moddir main $buildMap 2>&1 | Tee-Object -FilePath $q3mapLog
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
    & $q3map -vis -fast -threads $Threads -gamedir $buildRoot -moddir main $buildBsp 2>&1 | Tee-Object -FilePath $visLog
    $visExit = $LASTEXITCODE
    $timer.Stop()
    $stageResults.visSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    if ($visExit -ne 0) { throw "VIS failed with exit code $visExit" }

    $timer.Restart()
    & $mohlight -threads $Threads -gamedir $buildRoot -moddir main $buildMap 2>&1 | Tee-Object -FilePath $lightLog
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

    Copy-Item -LiteralPath $buildBsp -Destination $canonicalBsp -Force
}

if (-not (Test-Path -LiteralPath $canonicalBsp -PathType Leaf)) {
    throw "No compiled BSP is available to package: $canonicalBsp"
}
$bspInspectionPath = Join-Path $GeneratedRoot "$MapName-bsp.json"
& $NodePath $inspector $canonicalBsp | Out-File -LiteralPath $bspInspectionPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Final BSP inspection failed" }
$bspInspection = Get-Content -LiteralPath $bspInspectionPath -Raw | ConvertFrom-Json

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$entries = @(
    [pscustomobject]@{ Source = $canonicalBsp; Entry = "maps/dm/$MapName.bsp" },
    [pscustomobject]@{ Source = $canonicalScript; Entry = "maps/dm/$MapName.scr" },
    [pscustomobject]@{ Source = $canonicalPrecache; Entry = "maps/dm/${MapName}_precache.scr" }
)
foreach ($textureName in @($design.materials.bundledOriginalTextures)) {
    $entries += [pscustomobject]@{
        Source = (Join-Path $textureSourceRoot $textureName)
        Entry = "textures/codex_nuke/$textureName"
    }
}
$entries = @($entries | Sort-Object Entry)
$duplicates = @($entries | Group-Object Entry | Where-Object { $_.Count -ne 1 })
if ($duplicates.Count) { throw "Duplicate package entries: $($duplicates.Name -join ', ')" }
foreach ($entry in $entries) {
    if ($entry.Entry.StartsWith("/") -or $entry.Entry.Contains("\") -or $entry.Entry.Split("/") -contains "..") {
        throw "Unsafe package entry: $($entry.Entry)"
    }
    if (-not (Test-Path -LiteralPath $entry.Source -PathType Leaf)) { throw "Missing package source: $($entry.Source)" }
}

$fixedTimestamp = [System.DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [System.TimeSpan]::Zero)
function New-DeterministicPackage {
    param([string]$Destination, [object[]]$PackageEntries)
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force }
    $stream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        $archive = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
        try {
            foreach ($item in $PackageEntries) {
                $zipEntry = $archive.CreateEntry($item.Entry, [System.IO.Compression.CompressionLevel]::Optimal)
                $zipEntry.LastWriteTime = $fixedTimestamp
                $input = [System.IO.File]::OpenRead($item.Source)
                try {
                    $output = $zipEntry.Open()
                    try { $input.CopyTo($output) } finally { $output.Dispose() }
                }
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
$firstBytes = (Get-Item -LiteralPath $firstPackage).Length
$secondBytes = (Get-Item -LiteralPath $secondPackage).Length
if ($firstHash -ne $secondHash -or $firstBytes -ne $secondBytes) { throw "Package reproducibility mismatch" }
if (Test-Path -LiteralPath $packagePath) { Remove-Item -LiteralPath $packagePath -Force }
Move-Item -LiteralPath $firstPackage -Destination $packagePath
Remove-Item -LiteralPath $secondPackage -Force

$packageStream = [System.IO.File]::OpenRead($packagePath)
try {
    $archive = [System.IO.Compression.ZipArchive]::new($packageStream, [System.IO.Compression.ZipArchiveMode]::Read, $false)
    try {
        if ($archive.Entries.Count -ne $entries.Count) { throw "Package entry count mismatch" }
        $byName = @{}
        foreach ($entry in $entries) { $byName[$entry.Entry] = $entry.Source }
        foreach ($zipEntry in $archive.Entries) {
            if (-not $byName.ContainsKey($zipEntry.FullName)) { throw "Unexpected package entry: $($zipEntry.FullName)" }
            if ($zipEntry.LastWriteTime.DateTime -ne $fixedTimestamp.DateTime) { throw "Nondeterministic package timestamp: $($zipEntry.FullName)" }
            $source = $byName[$zipEntry.FullName]
            if ($zipEntry.Length -ne (Get-Item -LiteralPath $source).Length) { throw "Package length mismatch: $($zipEntry.FullName)" }
            $entryStream = $zipEntry.Open()
            try {
                $sha = [System.Security.Cryptography.SHA256]::Create()
                try { $archiveHash = ([System.BitConverter]::ToString($sha.ComputeHash($entryStream))).Replace("-", "") }
                finally { $sha.Dispose() }
            }
            finally { $entryStream.Dispose() }
            $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
            if ($archiveHash -ne $sourceHash) { throw "Package hash mismatch: $($zipEntry.FullName)" }
        }
    }
    finally { $archive.Dispose() }
}
finally { $packageStream.Dispose() }

$buildReport = [ordered]@{
    schemaVersion = 1
    mapName = $MapName
    retailPaks = @($retailPaks | ForEach-Object { [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() } })
    stages = $stageResults
    map = [ordered]@{ bytes = (Get-Item -LiteralPath $canonicalMap).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonicalMap).Hash.ToLowerInvariant() }
    bsp = $bspInspection
    package = [ordered]@{ entries = $entries.Count; bytes = (Get-Item -LiteralPath $packagePath).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant(); reproducedTwice = $true }
}
[System.IO.File]::WriteAllText($buildReportPath, (($buildReport | ConvertTo-Json -Depth 8) + "`n"), [System.Text.UTF8Encoding]::new($false))
Write-Output "Built $packagePath"
Write-Output "SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash)"