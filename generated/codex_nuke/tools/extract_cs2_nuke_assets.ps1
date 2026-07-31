param(
    [string]$Cs2Root = "",
    [string]$VrfCli = "",
    [string]$NodePath = "",
    [string]$PythonPath = "",
    [ValidateSet("pilot", "extended")]
    [string]$Tier = "pilot",
    [string]$LocalRoot = "",
    [switch]$DownloadVrf
)

$ErrorActionPreference = "Stop"
if (-not $Cs2Root) {
    throw "-Cs2Root is required"
}
$Cs2Root = [System.IO.Path]::GetFullPath($Cs2Root)

$generatedRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultLocalRoot = [System.IO.Path]::GetFullPath((Join-Path $generatedRoot ".local-source2"))
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
$allowlistPath = Join-Path $PSScriptRoot "cs2-nuke-topology-allowlist.json"
$converterPath = Join-Path $PSScriptRoot "convert_cs2_glb_to_mohaa.js"
$textureConverterPath = Join-Path $PSScriptRoot "convert_vrf_textures.py"

$mapVpk = Join-Path $Cs2Root "game\csgo\maps\de_nuke.vpk"
$pakDirectory = Join-Path $Cs2Root "game\csgo\pak01_dir.vpk"
$gameInfo = Join-Path $Cs2Root "game\csgo\gameinfo.gi"
foreach ($required in @($mapVpk, $pakDirectory, $gameInfo, $allowlistPath, $converterPath, $textureConverterPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing required input: $required"
    }
}

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
$PythonPath = Resolve-Executable $PythonPath @("python.exe", "python", "py.exe", "py")
if (-not $NodePath) {
    throw "Node.js was not found. Supply -NodePath."
}
if (-not $PythonPath) {
    throw "Python was not found. Supply -PythonPath."
}

$vrfVersion = "19.2"
$vrfZipHash = "53e7e8dac1ddd876078346de709c8dbe613a967e94cd0c969aa34c61ec07680d"
$vrfExeHash = "36d8c9208eefa61dd695bd577e49618bb161569941318f629294a4e4af00edc0"
$vrfToolRoot = Join-Path $LocalRoot "tools\vrf-$vrfVersion"
$vrfDownload = Join-Path $vrfToolRoot "cli-windows-x64.zip"
$downloadedVrf = Join-Path $vrfToolRoot "cli\Source2Viewer-CLI.exe"

if (-not $VrfCli) {
    if (Test-Path -LiteralPath $downloadedVrf -PathType Leaf) {
        $VrfCli = $downloadedVrf
    }
    elseif (Test-Path -LiteralPath "C:\tmp\vrf-19.2\cli\Source2Viewer-CLI.exe" -PathType Leaf) {
        $VrfCli = "C:\tmp\vrf-19.2\cli\Source2Viewer-CLI.exe"
    }
    elseif ($DownloadVrf) {
        New-Item -ItemType Directory -Path $vrfToolRoot -Force | Out-Null
        $uri = "https://github.com/ValveResourceFormat/ValveResourceFormat/releases/download/$vrfVersion/cli-windows-x64.zip"
        Invoke-WebRequest -Uri $uri -OutFile $vrfDownload
        $downloadHash = (Get-FileHash -LiteralPath $vrfDownload -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($downloadHash -ne $vrfZipHash) {
            throw "VRF archive hash mismatch: $downloadHash"
        }
        Expand-Archive -LiteralPath $vrfDownload -DestinationPath (Join-Path $vrfToolRoot "cli") -Force
        $VrfCli = $downloadedVrf
    }
    else {
        throw "VRF CLI was not found. Rerun with -DownloadVrf or supply -VrfCli."
    }
}
$VrfCli = [System.IO.Path]::GetFullPath($VrfCli)
if (-not (Test-Path -LiteralPath $VrfCli -PathType Leaf)) {
    throw "VRF CLI not found: $VrfCli"
}
$actualVrfHash = (Get-FileHash -LiteralPath $VrfCli -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualVrfHash -ne $vrfExeHash) {
    throw "Expected VRF $vrfVersion executable hash $vrfExeHash, found $actualVrfHash"
}

$allowlist = Get-Content -LiteralPath $allowlistPath -Raw | ConvertFrom-Json
$tiers = if ($Tier -eq "pilot") { @("pilot") } else { @("pilot", "extended") }
$resources = @($allowlist.resources | Where-Object { $tiers -contains $_.tier })
if (-not $resources.Count) {
    throw "The selected tier contains no resources."
}

$vrfRoot = Join-Path $LocalRoot "vrf"
$mohaaRoot = Join-Path $LocalRoot "mohaa"
$mohaaMain = Join-Path $mohaaRoot "main"
foreach ($staleRoot in @($vrfRoot, $mohaaRoot)) {
    if (Test-Path -LiteralPath $staleRoot) {
        $resolvedStale = [System.IO.Path]::GetFullPath($staleRoot)
        $requiredPrefix = $LocalRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $resolvedStale.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean output outside LocalRoot: $resolvedStale"
        }
        Remove-Item -LiteralPath $resolvedStale -Recurse
    }
}
$modelRoot = Join-Path $mohaaMain "models\codex_nuke\source2"
$textureRoot = Join-Path $mohaaMain "textures\codex_nuke_source2"
New-Item -ItemType Directory -Path $vrfRoot -Force | Out-Null
New-Item -ItemType Directory -Path $modelRoot -Force | Out-Null
New-Item -ItemType Directory -Path $textureRoot -Force | Out-Null

$assetRecords = @()
foreach ($asset in $resources) {
    $assetResources = if ($asset.resources) { @($asset.resources) } else { @($asset.resource) }
    if (-not $assetResources.Count -or $assetResources | Where-Object { -not $_ }) {
        throw "Asset $($asset.id) has no valid Source 2 resources"
    }
    $glbs = @()
    foreach ($assetResource in $assetResources) {
        Write-Output "Extracting $($asset.id): $assetResource"
        $previousErrorAction = $ErrorActionPreference
        try {
            # Windows PowerShell promotes native stderr to ErrorRecord objects when
            # a caller pipes this script. VRF 19.2 writes its known VCS-71 warning
            # there despite a successful export, so capture it without allowing
            # the warning stream to abort an otherwise valid conversion.
            $ErrorActionPreference = "Continue"
            $vrfOutput = @(& $VrfCli `
                -i $mapVpk `
                -o $vrfRoot `
                -d `
                -f $assetResource `
                --gltf_export_format glb `
                --gltf_export_materials 2>&1)
            $vrfExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorAction
        }
        $vrfOutput | ForEach-Object { Write-Output $_ }
        if ($vrfExitCode -ne 0) {
            throw "VRF failed for $($asset.id) resource $assetResource with exit code $vrfExitCode"
        }

        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($assetResource)
        $glbMatches = @(Get-ChildItem -LiteralPath $vrfRoot -Recurse -Filter "$baseName.glb" -File)
        if (-not $glbMatches.Count) {
            throw "VRF reported success but did not emit $baseName.glb"
        }
        if ($glbMatches.Count -ne 1) {
            throw "VRF emitted an ambiguous $baseName.glb set: $($glbMatches.FullName -join ', ')"
        }
        $glb = $glbMatches[0]
        $glbs += $glb
    }

    $modelOutput = Join-Path $modelRoot $asset.id
    New-Item -ItemType Directory -Path $modelOutput -Force | Out-Null
    $converterArguments = @($converterPath)
    foreach ($glb in $glbs) {
        $converterArguments += @("--input", $glb.FullName)
    }
    $converterArguments += @(
        "--output", $modelOutput,
        "--name", $asset.id,
        "--model-path", "models/codex_nuke/source2/$($asset.id)",
        "--shader-prefix", "textures/codex_nuke_source2"
    )
    if ($asset.recenter) {
        if ($asset.recenter -ne "bounds") {
            throw "Unsupported recenter mode for $($asset.id): $($asset.recenter)"
        }
        $converterArguments += "--recenter-bounds"
    }
    & $NodePath @converterArguments
    if ($LASTEXITCODE -ne 0) {
        throw "MOHAA model conversion failed for $($asset.id)"
    }

    & $NodePath (Join-Path $PSScriptRoot "inspect_mohaa_static_model.js") (Join-Path $modelOutput "$($asset.id).skd") | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "MOHAA model validation failed for $($asset.id)"
    }
    $conversion = Get-Content -LiteralPath (Join-Path $modelOutput "$($asset.id).conversion.json") -Raw |
        ConvertFrom-Json
    $placementOrigin = @($conversion.conversion.placementOrigin)
    $invalidOrigin = @($placementOrigin | Where-Object {
        [double]::IsNaN([double]$_) -or [double]::IsInfinity([double]$_)
    })
    if ($placementOrigin.Count -ne 3 -or $invalidOrigin.Count) {
        throw "Invalid placement origin for $($asset.id)"
    }

    $assetRecords += [ordered]@{
        id = $asset.id
        tier = $asset.tier
        role = $asset.role
        compileMode = if ($asset.compileMode) { $asset.compileMode } else { "static" }
        origin = @($placementOrigin)
        resource = $assetResources[0]
        resources = @($assetResources)
        glb = $glbs[0].FullName
        glbBytes = $glbs[0].Length
        glbSha256 = (Get-FileHash -LiteralPath $glbs[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        glbs = @($glbs | ForEach-Object {
            [ordered]@{
                path = $_.FullName
                bytes = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        })
        tiki = "models/codex_nuke/source2/$($asset.id)/$($asset.id).tik"
        suppressSource1ModelPatterns = @($asset.suppressSource1ModelPatterns)
    }
}
& $PythonPath `
    $textureConverterPath `
    --manifest-root $modelRoot `
    --output $textureRoot `
    --max-size 1024 `
    --report (Join-Path $LocalRoot "texture-conversion.json")
if ($LASTEXITCODE -ne 0) {
    throw "VRF texture conversion failed"
}

$fragmentLines = @(
    "// Local-only CS2 topology entities for codex_nuke."
    "// Model qpaths are relative to MOHAA's implicit models/ root."
)
foreach ($asset in $assetRecords) {
    $classname = if ($asset.compileMode -eq "runtime") {
        "script_model"
    }
    else {
        "static_codex_nuke_$($asset.id)"
    }
    $fragmentLines += @(
        "{"
        "`"classname`" `"$classname`""
        "`"model`" `"codex_nuke/source2/$($asset.id)/$($asset.id).tik`""
    )
    if ($asset.compileMode -eq "runtime") {
        $fragmentLines += "`"testanim`" `"idle`""
    }
    $fragmentLines += @(
        "`"origin`" `"$($asset.origin -join ' ')`""
        "`"angles`" `"0 0 0`""
        "`"scale`" `"1`""
        "`"angle`" `"0`""
        "}"
    )
}
$fragmentPath = Join-Path $LocalRoot "source2-static-entities.mapfrag"
[System.IO.File]::WriteAllLines($fragmentPath, $fragmentLines, [System.Text.UTF8Encoding]::new($false))

$manifest = [ordered]@{
    schemaVersion = 1
    generatedAt = [DateTime]::UtcNow.ToString("o")
    tier = $Tier
    legalBoundary = "All GLB, PNG, TGA, SKD, SKC, TIKI, and enhanced PK3 outputs are derived from user-owned Valve data and must remain local/untracked."
    source = [ordered]@{
        cs2Root = [System.IO.Path]::GetFullPath($Cs2Root)
        deNukeVpk = [ordered]@{
            path = $mapVpk
            bytes = (Get-Item -LiteralPath $mapVpk).Length
            sha256 = (Get-FileHash -LiteralPath $mapVpk -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        pak01Directory = [ordered]@{
            path = $pakDirectory
            bytes = (Get-Item -LiteralPath $pakDirectory).Length
            sha256 = (Get-FileHash -LiteralPath $pakDirectory -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    tools = [ordered]@{
        vrfVersion = $vrfVersion
        vrfPath = $VrfCli
        vrfSha256 = $actualVrfHash
        nodePath = $NodePath
        pythonPath = $PythonPath
    }
    assets = $assetRecords
    mapFragment = $fragmentPath
}
$manifestPath = Join-Path $LocalRoot "local-build-manifest.json"
[System.IO.File]::WriteAllText(
    $manifestPath,
    (($manifest | ConvertTo-Json -Depth 10) + "`n"),
    [System.Text.UTF8Encoding]::new($false)
)

$sourceResourceCount = ($assetRecords | ForEach-Object { @($_.resources).Count } | Measure-Object -Sum).Sum
Write-Output "Converted $($assetRecords.Count) CS2 Nuke model assets from $sourceResourceCount Source 2 resources."
Write-Output "Local MOHAA root: $mohaaMain"
Write-Output "Map fragment: $fragmentPath"
Write-Output "Manifest: $manifestPath"
