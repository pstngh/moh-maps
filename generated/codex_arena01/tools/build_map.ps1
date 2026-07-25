[CmdletBinding()]
param(
    [string]$MapName = "codex_arena01",
    [Parameter(Mandatory = $true)]
    [string]$MOHToolsDir,
    [string]$BuildRoot = (Join-Path $PSScriptRoot "build"),
    [string]$NodeExe = "node"
)

$ErrorActionPreference = "Stop"

if ($MapName -notmatch "^[A-Za-z0-9_]+$") {
    throw "MapName may contain only letters, numbers, and underscores."
}

$node = (Get-Command $NodeExe -ErrorAction Stop).Source
$generator = Join-Path $PSScriptRoot "generate_dm_map.js"
$q3map = Join-Path $MOHToolsDir "Q3map.exe"
$mohlight = Join-Path $MOHToolsDir "MOHlight.exe"

foreach ($requiredFile in @($generator, $q3map, $mohlight)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required file not found: $requiredFile"
    }
}

New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null

& $node $generator $MapName $BuildRoot
if ($LASTEXITCODE -ne 0) { throw "Map generation failed." }

$mapPath = Join-Path $BuildRoot "main\maps\dm\$MapName.map"

& $q3map -gamedir $BuildRoot -moddir main $mapPath
if ($LASTEXITCODE -ne 0) { throw "Q3map BSP stage failed." }

& $q3map -vis -fast -gamedir $BuildRoot -moddir main $mapPath
if ($LASTEXITCODE -ne 0) { throw "Q3map VIS stage failed." }

& $mohlight -gamedir $BuildRoot -moddir main $mapPath
if ($LASTEXITCODE -ne 0) { throw "MOHlight stage failed." }

$pk3Path = Join-Path $BuildRoot "$MapName.pk3"

# Write canonical forward-slash ZIP entry names. Compress-Archive on Windows
# uses backslashes, which some PK3 readers do not normalize.
Add-Type -AssemblyName System.IO.Compression
$packageItems = @(
    @{ Source = (Join-Path $BuildRoot "main\maps\dm\$MapName.bsp"); Entry = "maps/dm/$MapName.bsp" },
    @{ Source = (Join-Path $BuildRoot "main\maps\dm\$MapName.scr"); Entry = "maps/dm/$MapName.scr" },
    @{ Source = (Join-Path $BuildRoot "main\maps\dm\${MapName}_precache.scr"); Entry = "maps/dm/${MapName}_precache.scr" },
    @{ Source = (Join-Path $BuildRoot "main\textures\codex\floor.tga"); Entry = "textures/codex/floor.tga" },
    @{ Source = (Join-Path $BuildRoot "main\textures\codex\wall.tga"); Entry = "textures/codex/wall.tga" },
    @{ Source = (Join-Path $BuildRoot "main\textures\codex\trim.tga"); Entry = "textures/codex/trim.tga" },
    @{ Source = (Join-Path $BuildRoot "main\textures\codex\ceiling.tga"); Entry = "textures/codex/ceiling.tga" }
)

$packageStream = [System.IO.File]::Open(
    $pk3Path,
    [System.IO.FileMode]::Create,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
)
try {
    $archive = [System.IO.Compression.ZipArchive]::new(
        $packageStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )
    try {
        foreach ($item in $packageItems) {
            $entry = $archive.CreateEntry(
                $item.Entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $entryStream = $entry.Open()
            try {
                $sourceStream = [System.IO.File]::OpenRead($item.Source)
                try {
                    $sourceStream.CopyTo($entryStream)
                }
                finally {
                    $sourceStream.Dispose()
                }
            }
            finally {
                $entryStream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    $packageStream.Dispose()
}

Write-Output "Built $pk3Path"
