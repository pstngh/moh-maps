param(
    [Parameter(Mandatory = $true)]
    [string]$StageRoot,
    [string]$GeneratedRoot,
    [string]$MapName = "codex_inferno"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($GeneratedRoot)) {
    $GeneratedRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
$stage = (Resolve-Path -LiteralPath $StageRoot).Path
$generated = (Resolve-Path -LiteralPath $GeneratedRoot).Path
$canonicalMap = Join-Path $generated "main\maps\dm\$MapName.map"
$stageMap = Join-Path $stage "main\maps\dm\$MapName.map"
$canonicalTextureRoot = Join-Path $generated "main\textures\codex_inferno"
$stageTextureRoot = Join-Path $stage "main\textures\codex_inferno"

foreach ($required in @($canonicalMap, $stageMap, $canonicalTextureRoot, $stageTextureRoot)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing compile-stage input: $required"
    }
}

$failures = [System.Collections.Generic.List[string]]::new()
$canonicalMapHash = (Get-FileHash -LiteralPath $canonicalMap -Algorithm SHA256).Hash
$stageMapHash = (Get-FileHash -LiteralPath $stageMap -Algorithm SHA256).Hash
if ($canonicalMapHash -ne $stageMapHash) {
    $failures.Add("Staged MAP hash does not match the canonical generated MAP")
}

$canonicalTextures = Get-ChildItem -LiteralPath $canonicalTextureRoot -File -Filter "*.tga" |
    Sort-Object Name
$stageTextures = Get-ChildItem -LiteralPath $stageTextureRoot -File -Filter "*.tga" |
    Sort-Object Name
$stageByName = @{}
foreach ($file in $stageTextures) {
    $stageByName[$file.Name.ToLowerInvariant()] = $file
}

foreach ($file in $canonicalTextures) {
    $key = $file.Name.ToLowerInvariant()
    if (-not $stageByName.ContainsKey($key)) {
        $failures.Add("Missing staged texture: $($file.Name)")
        continue
    }
    $canonicalHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $stagedHash = (Get-FileHash -LiteralPath $stageByName[$key].FullName -Algorithm SHA256).Hash
    if ($canonicalHash -ne $stagedHash) {
        $failures.Add("Staged texture hash mismatch: $($file.Name)")
    }
}

$canonicalNames = @($canonicalTextures | ForEach-Object { $_.Name.ToLowerInvariant() })
foreach ($file in $stageTextures) {
    if ($canonicalNames -notcontains $file.Name.ToLowerInvariant()) {
        $failures.Add("Unexpected staged texture: $($file.Name)")
    }
}

$result = [ordered]@{
    mapName = $MapName
    stageRoot = $stage
    mapSha256 = $stageMapHash
    canonicalTextures = $canonicalTextures.Count
    stagedTextures = $stageTextures.Count
    failures = @($failures)
}
$result | ConvertTo-Json -Depth 4
if ($failures.Count -gt 0) {
    exit 1
}