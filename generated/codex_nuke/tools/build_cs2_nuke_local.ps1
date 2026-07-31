param(
    [string]$Vmf = "",
    [string]$GeneratedRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$LocalRoot = "",
    [string]$NodePath = "",
    [string]$Q3mapPath = "",
    [string]$MohlightPath = "",
    [string]$RetailRoot = "",
    [int]$Threads = 4,
    [switch]$SkipGenerate,
    [switch]$PrepareOnly,
    [switch]$PreflightOnly,
    [switch]$SkipQ3map,
    [switch]$SkipVis,
    [switch]$SkipLight
)

$ErrorActionPreference = "Stop"
if (-not $Vmf) {
    throw "-Vmf is required"
}
$Vmf = [System.IO.Path]::GetFullPath($Vmf)
$mapName = "codex_nuke_source2"
$GeneratedRoot = [System.IO.Path]::GetFullPath($GeneratedRoot)
$defaultLocalRoot = [System.IO.Path]::GetFullPath((Join-Path $GeneratedRoot ".local-source2"))
if (-not $LocalRoot) {
    $LocalRoot = $defaultLocalRoot
}
$LocalRoot = [System.IO.Path]::GetFullPath($LocalRoot)
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$repositoryPrefix = $repositoryRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$localRootInsideRepository =
    $LocalRoot.Equals($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $LocalRoot.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)
if (
    $localRootInsideRepository -and
    -not $LocalRoot.Equals($defaultLocalRoot, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "A LocalRoot inside the repository must be the ignored .local-source2 directory: $defaultLocalRoot"
}
$buildRoot = Join-Path $LocalRoot "enhanced"
$mainRoot = Join-Path $buildRoot "main"
$mapRoot = Join-Path $mainRoot "maps\dm"
$manifestPath = Join-Path $LocalRoot "local-build-manifest.json"
$localAssetMain = Join-Path $LocalRoot "mohaa\main"
$packagePath = Join-Path $GeneratedRoot "codex_nuke-source2-local.pk3"

function Resolve-Executable {
    param([string]$Explicit, [string[]]$Names)
    if ($Explicit) {
        $resolved = [System.IO.Path]::GetFullPath($Explicit)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Executable not found: $resolved"
        }
        return $resolved
    }
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    return ""
}

$NodePath = Resolve-Executable $NodePath @("node.exe", "node")
if (-not $RetailRoot) {
    $defaultRetailRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\runtime_base_stock"))
    if (Test-Path -LiteralPath $defaultRetailRoot -PathType Container) {
        $RetailRoot = $defaultRetailRoot
    }
    else {
        throw "-RetailRoot is required and must contain retail Allied Assault Pak0.pk3 through Pak6.pk3"
    }
}
$RetailRoot = [System.IO.Path]::GetFullPath($RetailRoot)
if (-not (Test-Path -LiteralPath $RetailRoot -PathType Container)) {
    throw "Retail Allied Assault root not found: $RetailRoot"
}
$retailPackDirectory = ""
$retailPackLookup = @{}
foreach ($candidateDirectory in @($RetailRoot, (Join-Path $RetailRoot "main"))) {
    if (-not (Test-Path -LiteralPath $candidateDirectory -PathType Container)) {
        continue
    }
    $candidateLookup = @{}
    foreach ($pack in Get-ChildItem -LiteralPath $candidateDirectory -Filter "*.pk3" -File) {
        $candidateLookup[$pack.Name.ToLowerInvariant()] = $pack
    }
    $hasAllRetailPaks = $true
    foreach ($packNumber in 0..6) {
        if (-not $candidateLookup.ContainsKey("pak$packNumber.pk3")) {
            $hasAllRetailPaks = $false
            break
        }
    }
    if ($hasAllRetailPaks) {
        $retailPackDirectory = $candidateDirectory
        $retailPackLookup = $candidateLookup
        break
    }
}
if (-not $retailPackDirectory) {
    throw "Retail Allied Assault Pak0.pk3 through Pak6.pk3 were not found in $RetailRoot or its main directory"
}
$retailPaks = @(0..6 | ForEach-Object { $retailPackLookup["pak$_.pk3"] })
if (-not $Q3mapPath) {
    $Q3mapPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\MOHTools\Q3map.exe"))
}
if (-not $MohlightPath) {
    $MohlightPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\MOHTools\MOHlight.exe"))
}
foreach ($required in @($Vmf, $manifestPath, $NodePath, $Q3mapPath, $MohlightPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing local build input: $required"
    }
}
$localManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifestAssets = @($localManifest.assets)
if ($manifestAssets.Count -lt 1) {
    throw "Local Source2 manifest contains no model assets"
}
$staticManifestAssets = @($manifestAssets | Where-Object { $_.compileMode -ne "runtime" })
$runtimeManifestAssets = @($manifestAssets | Where-Object { $_.compileMode -eq "runtime" })
$expectedStaticModels = $staticManifestAssets.Count
$maxMohlightStaticVertices = 75000
$runtimeInspectionArguments = @()
foreach ($asset in $runtimeManifestAssets) {
    $origin = @($asset.origin)
    if ($origin.Count -ne 3) {
        throw "Runtime model $($asset.id) must have a three-component origin"
    }
    $originArguments = @()
    foreach ($component in $origin) {
        $number = [double]$component
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            throw "Runtime model $($asset.id) has a non-finite origin"
        }
        $originArguments += $number.ToString("R", [System.Globalization.CultureInfo]::InvariantCulture)
    }
    $model = ([string]$asset.tiki).Replace("\", "/") -replace "^models/", ""
    $runtimeInspectionArguments += @(
        "--require-runtime-model-origin",
        $model,
        $originArguments[0],
        $originArguments[1],
        $originArguments[2]
    )
}

$staticVertexCount = 0
foreach ($asset in $staticManifestAssets) {
    $conversionPath = Join-Path $localAssetMain "models\codex_nuke\source2\$($asset.id)\$($asset.id).conversion.json"
    if (-not (Test-Path -LiteralPath $conversionPath -PathType Leaf)) {
        throw "Missing static-model conversion manifest: $conversionPath"
    }
    $conversion = Get-Content -LiteralPath $conversionPath -Raw | ConvertFrom-Json
    $staticVertexCount += [int]$conversion.geometry.verticesAfterSplitting
}
if ($staticVertexCount -gt $maxMohlightStaticVertices) {
    throw "Retail MOHlight 1.48 static-model vertex budget exceeded: $staticVertexCount > $maxMohlightStaticVertices; weld, partition, or runtime-light an aggregate"
}
if ($Threads -lt 1) {
    throw "-Threads must be positive"
}

if (-not $SkipGenerate) {
    if (Test-Path -LiteralPath $buildRoot) {
        $resolvedBuild = [System.IO.Path]::GetFullPath($buildRoot)
        $requiredPrefix = $LocalRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $resolvedBuild.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean build outside LocalRoot: $resolvedBuild"
        }
        Remove-Item -LiteralPath $resolvedBuild -Recurse
    }
    & $NodePath `
        (Join-Path $PSScriptRoot "generate_nuke.js") `
        $Vmf `
        $buildRoot `
        $mapName `
        --source2-static-manifest $manifestPath
    if ($LASTEXITCODE -ne 0) {
        throw "Local Source2 generator failed"
    }
}

New-Item -ItemType Directory -Path $mainRoot -Force | Out-Null
foreach ($pack in $retailPaks) {
    $stagedPack = Join-Path $mainRoot $pack.Name
    $resolvedPack = [System.IO.Path]::GetFullPath($stagedPack)
    $requiredPrefix = $mainRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPack.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to stage retail pack outside build root: $resolvedPack"
    }
    if (Test-Path -LiteralPath $stagedPack) {
        Remove-Item -LiteralPath $stagedPack -Force
    }
    try {
        New-Item -ItemType HardLink -Path $stagedPack -Target $pack.FullName -ErrorAction Stop | Out-Null
    }
    catch {
        Copy-Item -LiteralPath $pack.FullName -Destination $stagedPack -Force
    }
}
$stagedLocalPayloads = @(
    (Join-Path $mainRoot "models\codex_nuke\source2"),
    (Join-Path $mainRoot "textures\codex_nuke_source2")
)
foreach ($stagedPayload in $stagedLocalPayloads) {
    if (Test-Path -LiteralPath $stagedPayload) {
        $resolvedPayload = [System.IO.Path]::GetFullPath($stagedPayload)
        $requiredPrefix = $mainRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $resolvedPayload.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean staged payload outside main root: $resolvedPayload"
        }
        Remove-Item -LiteralPath $resolvedPayload -Recurse -Force
    }
}
$copyPairs = @(
    @{ Source = (Join-Path $GeneratedRoot "main\scripts"); Destination = (Join-Path $mainRoot "scripts") },
    @{ Source = (Join-Path $GeneratedRoot "main\textures"); Destination = (Join-Path $mainRoot "textures") },
    @{ Source = (Join-Path $localAssetMain "models"); Destination = (Join-Path $mainRoot "models") },
    @{ Source = (Join-Path $localAssetMain "textures\codex_nuke_source2"); Destination = (Join-Path $mainRoot "textures\codex_nuke_source2") }
)
foreach ($pair in $copyPairs) {
    New-Item -ItemType Directory -Path $pair.Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $pair.Source "*") -Destination $pair.Destination -Recurse -Force
}

$validationPath = Join-Path $buildRoot "source2-static-validation.json"
& $NodePath `
    (Join-Path $PSScriptRoot "validate_cs2_nuke_local.js") `
    --build-root $buildRoot `
    --manifest $manifestPath `
    --map-name $mapName |
    Out-File -LiteralPath $validationPath -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "Local Source2 validation failed"
}
$sourceValidation = Get-Content -LiteralPath $validationPath -Raw | ConvertFrom-Json
if ($PrepareOnly) {
    Write-Output "Prepared and validated local Source2 build root: $buildRoot"
    return
}

$mapPath = Join-Path $mapRoot "$mapName.map"
$bspPath = Join-Path $mapRoot "$mapName.bsp"
$q3mapLog = Join-Path $buildRoot "q3map.log"
$visLog = Join-Path $buildRoot "vis.log"
$lightLog = Join-Path $buildRoot "mohlight.log"

if (-not $SkipQ3map) {
    $probeAsset = $manifestAssets[0]
    $probeModel = ([string]$probeAsset.tiki).Replace("\", "/") -replace "^models/", ""
    $probeMap = Join-Path $mapRoot "retail_pack_resolution_probe.map"
    & $NodePath `
        (Join-Path $PSScriptRoot "build_static_model_probe.js") `
        --output $probeMap `
        --name ([string]$probeAsset.id) `
        --model $probeModel
    if ($LASTEXITCODE -ne 0) {
        throw "Retail-pack resolution probe generation failed"
    }
    $probeText = [System.IO.File]::ReadAllText($probeMap)
    foreach ($replacement in @("common/caulk", "sky/m5l2")) {
        $textureIndex = $probeText.IndexOf("codex_nuke/concrete_floor", [System.StringComparison]::Ordinal)
        if ($textureIndex -lt 0) {
            throw "Retail-pack resolution probe texture anchor is missing"
        }
        $probeText = $probeText.Remove($textureIndex, "codex_nuke/concrete_floor".Length).Insert($textureIndex, $replacement)
    }
    [System.IO.File]::WriteAllText($probeMap, $probeText, [System.Text.UTF8Encoding]::new($false))
    $probeLog = Join-Path $buildRoot "retail-pack-resolution-probe.log"
    & $Q3mapPath -threads ([Math]::Min($Threads, 2)) -gamedir $buildRoot -moddir main $probeMap 2>&1 |
        Tee-Object -FilePath $probeLog
    if ($LASTEXITCODE -ne 0) {
        throw "Retail-pack resolution Q3map probe failed with exit code $LASTEXITCODE"
    }
    $probeLines = @(Get-Content -LiteralPath $probeLog)
    $packCountLine = $probeLines | Where-Object { $_ -match "^\d+ files in pk3 files$" } | Select-Object -First 1
    $packCount = if ($packCountLine) {
        [int]([regex]::Match($packCountLine, "^(\d+)").Groups[1].Value)
    }
    else {
        0
    }
    if ($packCount -lt 1) {
        throw "Retail-pack resolution probe loaded no PK3 files"
    }
    $probeMissingImages = @($probeLines | Where-Object { $_ -match "Couldn.t find image" })
    if ($probeMissingImages.Count) {
        throw "Retail-pack resolution probe has missing images: $($probeMissingImages -join ' | ')"
    }
    $probeUnexpectedWarnings = @($probeLines | Where-Object {
        $_ -match "^WARNING" -and
        $_ -notmatch "^WARNING- DOWNGRADING TO OLD ANIMATION FORMAT FOR FILE: models/codex_nuke/source2/[a-z0-9_/-]+\.skc$" -and
        $_ -notmatch "^WARNING: Could not find 'models/codex_nuke/source2/[a-z0-9_/-]+\.map'\.$"
    })
    if ($probeUnexpectedWarnings.Count) {
        throw "Unexpected retail-pack resolution probe warnings: $($probeUnexpectedWarnings -join ' | ')"
    }
    $allModelProbeMap = Join-Path $mapRoot "all_source2_models_probe.map"
    $allModelProbeBsp = Join-Path $mapRoot "all_source2_models_probe.bsp"
    & $NodePath `
        (Join-Path $PSScriptRoot "build_static_model_probe.js") `
        --output $allModelProbeMap `
        --manifest $manifestPath
    if ($LASTEXITCODE -ne 0) {
        throw "All-model probe generation failed"
    }
    $allModelQ3Log = Join-Path $buildRoot "all-source2-models-q3map.log"
    & $Q3mapPath -threads ([Math]::Min($Threads, 2)) -gamedir $buildRoot -moddir main $allModelProbeMap 2>&1 |
        Tee-Object -FilePath $allModelQ3Log
    if ($LASTEXITCODE -ne 0) {
        throw "All-model Q3map probe failed with exit code $LASTEXITCODE"
    }
    $allModelWarnings = @(Get-Content -LiteralPath $allModelQ3Log | Where-Object { $_ -match "^WARNING" })
    $allModelExpectedWarnings = @($allModelWarnings | Where-Object {
        $_ -match "^WARNING- DOWNGRADING TO OLD ANIMATION FORMAT FOR FILE: models/codex_nuke/source2/[a-z0-9_/-]+\.skc$" -or
        $_ -match "^WARNING: Could not find 'models/codex_nuke/source2/[a-z0-9_/-]+\.map'\.$"
    })
    if ($allModelExpectedWarnings.Count -ne $allModelWarnings.Count) {
        throw "Unexpected all-model Q3map warnings: $($allModelWarnings -join ' | ')"
    }
    & $Q3mapPath -vis -fast -threads ([Math]::Min($Threads, 2)) -gamedir $buildRoot -moddir main $allModelProbeBsp 2>&1 |
        Out-File -LiteralPath (Join-Path $buildRoot "all-source2-models-vis.log") -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "All-model VIS probe failed with exit code $LASTEXITCODE"
    }
    $allModelLightLog = Join-Path $buildRoot "all-source2-models-mohlight.log"
    & $MohlightPath -threads ([Math]::Min($Threads, 2)) -gamedir $buildRoot -moddir main $allModelProbeMap 2>&1 |
        Tee-Object -FilePath $allModelLightLog
    if ($LASTEXITCODE -ne 0) {
        throw "All-model MOHlight probe failed with exit code $LASTEXITCODE"
    }
    $allModelLightLines = @(Get-Content -LiteralPath $allModelLightLog)
    $modelsLitLine = $allModelLightLines | Where-Object { $_ -match "^Total Models Lit:" } | Select-Object -First 1
    $verticesLitLine = $allModelLightLines | Where-Object { $_ -match "^Total Vertecies Lit:" } | Select-Object -First 1
    $modelsLitMatch = [regex]::Match([string]$modelsLitLine, "^Total Models Lit:\s+(\d+)$")
    $verticesLitMatch = [regex]::Match([string]$verticesLitLine, "^Total Vertecies Lit:\s+(\d+)$")
    if (
        -not $modelsLitMatch.Success -or
        [int]$modelsLitMatch.Groups[1].Value -ne $expectedStaticModels -or
        -not $verticesLitMatch.Success -or
        [int]$verticesLitMatch.Groups[1].Value -ne $staticVertexCount
    ) {
        throw "All-model MOHlight count mismatch: expected $expectedStaticModels models / $staticVertexCount vertices"
    }
    & $NodePath `
        (Join-Path $PSScriptRoot "inspect_nuke_bsp.js") `
        $allModelProbeBsp `
        --require-source2-static-count $expectedStaticModels `
        @runtimeInspectionArguments |
        Out-File -LiteralPath (Join-Path $buildRoot "all-source2-models-bsp.json") -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "All-model BSP probe inspection failed"
    }
    if ($PreflightOnly) {
        Write-Output "Retail-pack resolution preflight passed with $packCount PK3 files; $staticVertexCount / $maxMohlightStaticVertices static vertices"
        return
    }

    & $Q3mapPath -threads $Threads -gamedir $buildRoot -moddir main $mapPath 2>&1 |
        Tee-Object -FilePath $q3mapLog
    if ($LASTEXITCODE -ne 0) {
        throw "Q3map failed with exit code $LASTEXITCODE"
    }
    $q3mapWarnings = @(Get-Content -LiteralPath $q3mapLog | Where-Object { $_ -match "^WARNING" })
    $downgradeWarnings = @($q3mapWarnings | Where-Object {
        $_ -match "^WARNING- DOWNGRADING TO OLD ANIMATION FORMAT FOR FILE: models/codex_nuke/source2/[a-z0-9_/-]+\.skc$"
    })
    $collisionHelperWarnings = @($q3mapWarnings | Where-Object {
        $_ -match "^WARNING: Could not find 'models/codex_nuke/source2/[a-z0-9_/-]+\.map'\.$"
    })
    $unexpectedWarnings = @($q3mapWarnings | Where-Object {
        $_ -notmatch "^WARNING- DOWNGRADING TO OLD ANIMATION FORMAT FOR FILE: models/codex_nuke/source2/[a-z0-9_/-]+\.skc$" -and
        $_ -notmatch "^WARNING: Could not find 'models/codex_nuke/source2/[a-z0-9_/-]+\.map'\.$"
    })
    if ($downgradeWarnings.Count -ne $expectedStaticModels) {
        throw "Expected $expectedStaticModels static-model downgrade warnings, found $($downgradeWarnings.Count)"
    }
    if ($collisionHelperWarnings.Count -lt $expectedStaticModels) {
        throw "Expected at least $expectedStaticModels documented collision-helper warnings, found $($collisionHelperWarnings.Count)"
    }
    if ($unexpectedWarnings.Count) {
        throw "Unexpected Q3map warnings: $($unexpectedWarnings -join ' | ')"
    }
    $fatalQ3mapText = @(Get-Content -LiteralPath $q3mapLog | Where-Object {
        $_ -match "Couldn.t find image|TIKI_InitTiki|TIKI_ParseSetup|Too many skins defined|could not find surface|ERROR:|MAX_[A-Z_]+\s+exceeded|is incomplete"
    })
    if ($fatalQ3mapText.Count) {
        throw "Fatal Q3map diagnostics: $($fatalQ3mapText -join ' | ')"
    }
}
if (-not $SkipVis) {
    & $Q3mapPath -vis -fast -threads $Threads -gamedir $buildRoot -moddir main $bspPath 2>&1 |
        Tee-Object -FilePath $visLog
    if ($LASTEXITCODE -ne 0) {
        throw "VIS failed with exit code $LASTEXITCODE"
    }
}
if (-not $SkipLight) {
    $preRepack = Join-Path $mapRoot "$mapName-pre-repack.bsp"
    Copy-Item -LiteralPath $bspPath -Destination $preRepack -Force
    & $NodePath `
        (Join-Path $PSScriptRoot "repack_nuke_bsp_lightmaps.js") `
        $preRepack `
        $bspPath
    if ($LASTEXITCODE -ne 0) {
        throw "BSP lightmap atlas repack failed"
    }
    & $NodePath (Join-Path $PSScriptRoot "inspect_nuke_bsp.js") $bspPath --allow-unlit --require-source2-static-count $expectedStaticModels @runtimeInspectionArguments |
        Out-File -LiteralPath (Join-Path $buildRoot "bsp-prelight.json") -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "Pre-light BSP inspection failed"
    }
    & $MohlightPath -threads $Threads -gamedir $buildRoot -moddir main $mapPath 2>&1 |
        Tee-Object -FilePath $lightLog
    if ($LASTEXITCODE -ne 0) {
        throw "MOHlight failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $bspPath -PathType Leaf)) {
    throw "No compiled BSP is available to package: $bspPath"
}
& $NodePath (Join-Path $PSScriptRoot "inspect_nuke_bsp.js") $bspPath --require-source2-static-count $expectedStaticModels @runtimeInspectionArguments |
    Out-File -LiteralPath (Join-Path $buildRoot "bsp-final.json") -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "Final BSP inspection failed"
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$entries = @(
    [pscustomobject]@{ Source = $bspPath; Entry = "maps/dm/$mapName.bsp" },
    [pscustomobject]@{ Source = (Join-Path $mapRoot "$mapName.scr"); Entry = "maps/dm/$mapName.scr" },
    [pscustomobject]@{ Source = (Join-Path $mapRoot "${mapName}_precache.scr"); Entry = "maps/dm/${mapName}_precache.scr" },
    [pscustomobject]@{ Source = (Join-Path $mainRoot "scripts\codex_nuke.shader"); Entry = "scripts/codex_nuke.shader" }
)
$entries += Get-ChildItem -LiteralPath (Join-Path $mainRoot "textures\codex_nuke") -Filter "*.tga" -File |
    ForEach-Object { [pscustomobject]@{ Source = $_.FullName; Entry = "textures/codex_nuke/$($_.Name)" } }
$entries += Get-ChildItem -LiteralPath (Join-Path $mainRoot "textures\codex_nuke_source2") -Filter "*.tga" -File |
    ForEach-Object { [pscustomobject]@{ Source = $_.FullName; Entry = "textures/codex_nuke_source2/$($_.Name)" } }
$entries += Get-ChildItem -LiteralPath (Join-Path $mainRoot "models\codex_nuke\source2") -Recurse -File |
    Where-Object { $_.Extension -in @(".tik", ".skd", ".skc") } |
    ForEach-Object {
        $prefix = $mainRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $_.FullName.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Package model escaped main root: $($_.FullName)"
        }
        $relative = $_.FullName.Substring($prefix.Length).Replace("\", "/")
        [pscustomobject]@{ Source = $_.FullName; Entry = $relative }
    }
$entries = @($entries | Sort-Object Entry)
$duplicateEntries = @($entries | Group-Object Entry | Where-Object { $_.Count -ne 1 })
if ($duplicateEntries.Count) {
    throw "Duplicate package entries: $($duplicateEntries.Name -join ', ')"
}
foreach ($entry in $entries) {
    if ($entry.Entry.StartsWith("/") -or $entry.Entry.Contains("\") -or $entry.Entry.Split("/") -contains "..") {
        throw "Unsafe package entry: $($entry.Entry)"
    }
    if (-not (Test-Path -LiteralPath $entry.Source -PathType Leaf)) {
        throw "Missing package input: $($entry.Source)"
    }
}

$temporaryPackage = "$packagePath.tmp"
if (Test-Path -LiteralPath $temporaryPackage) {
    Remove-Item -LiteralPath $temporaryPackage
}
$stream = [System.IO.File]::Open(
    $temporaryPackage,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
)
try {
    $archive = [System.IO.Compression.ZipArchive]::new(
        $stream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )
    try {
        $fixedTimestamp = [System.DateTimeOffset]::new(
            2000,
            1,
            1,
            0,
            0,
            0,
            [System.TimeSpan]::Zero
        )
        foreach ($entry in $entries) {
            $archiveEntry = $archive.CreateEntry(
                $entry.Entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $archiveEntry.LastWriteTime = $fixedTimestamp
            $inputStream = [System.IO.File]::OpenRead($entry.Source)
            try {
                $outputStream = $archiveEntry.Open()
                try {
                    $inputStream.CopyTo($outputStream)
                }
                finally {
                    $outputStream.Dispose()
                }
            }
            finally {
                $inputStream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    $stream.Dispose()
}
if (Test-Path -LiteralPath $packagePath) {
    Remove-Item -LiteralPath $packagePath
}
Move-Item -LiteralPath $temporaryPackage -Destination $packagePath

$packageStream = [System.IO.File]::OpenRead($packagePath)
try {
    $packageArchive = [System.IO.Compression.ZipArchive]::new(
        $packageStream,
        [System.IO.Compression.ZipArchiveMode]::Read,
        $false
    )
    try {
        if ($packageArchive.Entries.Count -ne $entries.Count) {
            throw "Package entry count mismatch: expected $($entries.Count), found $($packageArchive.Entries.Count)"
        }
        $expectedByName = @{}
        foreach ($entry in $entries) {
            $expectedByName[$entry.Entry] = $entry.Source
        }
        foreach ($archiveEntry in $packageArchive.Entries) {
            if (-not $expectedByName.ContainsKey($archiveEntry.FullName)) {
                throw "Unexpected package entry: $($archiveEntry.FullName)"
            }
            # ZIP's DOS timestamp stores calendar fields but no UTC offset. Compare
            # those fields so verification is stable in every local time zone.
            if ($archiveEntry.LastWriteTime.DateTime -ne $fixedTimestamp.DateTime) {
                throw "Nondeterministic package timestamp: $($archiveEntry.FullName)"
            }
            $sourcePath = $expectedByName[$archiveEntry.FullName]
            if ($archiveEntry.Length -ne (Get-Item -LiteralPath $sourcePath).Length) {
                throw "Package entry length mismatch: $($archiveEntry.FullName)"
            }
            $entryStream = $archiveEntry.Open()
            try {
                $sha256 = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $archiveHash = ([System.BitConverter]::ToString($sha256.ComputeHash($entryStream))).Replace("-", "").ToLowerInvariant()
                }
                finally {
                    $sha256.Dispose()
                }
            }
            finally {
                $entryStream.Dispose()
            }
            $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($archiveHash -ne $sourceHash) {
                throw "Package entry hash mismatch: $($archiveEntry.FullName)"
            }
        }
    }
    finally {
        $packageArchive.Dispose()
    }
}
finally {
    $packageStream.Dispose()
}

$buildManifest = [ordered]@{
    schemaVersion = 1
    generatedAt = [DateTime]::UtcNow.ToString("o")
    mapName = $mapName
    localOnly = $true
    legalBoundary = "This package contains files derived from user-owned Valve data. Do not publish, commit, or redistribute it."
    source2 = [ordered]@{
        models = $manifestAssets.Count
        staticModels = $expectedStaticModels
        runtimeModels = $manifestAssets.Count - $expectedStaticModels
        vertices = [int]$sourceValidation.source2Vertices
        staticVertices = $staticVertexCount
        runtimeVertices = [int]$sourceValidation.source2RuntimeVertices
        staticVertexBudget = $maxMohlightStaticVertices
        triangles = [int]$sourceValidation.source2Triangles
        staticTriangles = [int]$sourceValidation.source2StaticTriangles
        runtimeTriangles = [int]$sourceValidation.source2RuntimeTriangles
    }
    sourceManifest = $manifestPath
    retailRoot = $( [System.IO.Path]::GetFullPath($RetailRoot) )
    retailPackDirectory = $( [System.IO.Path]::GetFullPath($retailPackDirectory) )
    retailPaks = @($retailPaks | ForEach-Object {
        [ordered]@{
            name = $_.Name
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    map = [ordered]@{
        path = $mapPath
        bytes = (Get-Item -LiteralPath $mapPath).Length
        sha256 = (Get-FileHash -LiteralPath $mapPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    bsp = [ordered]@{
        path = $bspPath
        bytes = (Get-Item -LiteralPath $bspPath).Length
        sha256 = (Get-FileHash -LiteralPath $bspPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    package = [ordered]@{
        path = $packagePath
        entries = $entries.Count
        bytes = (Get-Item -LiteralPath $packagePath).Length
        sha256 = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
[System.IO.File]::WriteAllText(
    (Join-Path $buildRoot "local-enhanced-build.json"),
    (($buildManifest | ConvertTo-Json -Depth 8) + "`n"),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Output "Created local-only package: $packagePath"
