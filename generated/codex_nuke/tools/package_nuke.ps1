param(
    [string]$MapName = "codex_nuke",
    [string]$GeneratedRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$mainRoot = Join-Path $GeneratedRoot "main"
$packagePath = Join-Path $GeneratedRoot "$MapName.pk3"
$requiredEntries = @(
    @{ Source = (Join-Path $mainRoot "maps\dm\$MapName.bsp"); Entry = "maps/dm/$MapName.bsp" },
    @{ Source = (Join-Path $mainRoot "maps\dm\$MapName.scr"); Entry = "maps/dm/$MapName.scr" },
    @{ Source = (Join-Path $mainRoot "maps\dm\${MapName}_precache.scr"); Entry = "maps/dm/${MapName}_precache.scr" },
    @{ Source = (Join-Path $mainRoot "scripts\codex_nuke.shader"); Entry = "scripts/codex_nuke.shader" }
)

$textureRoot = Join-Path $mainRoot "textures\codex_nuke"
$textureEntries = Get-ChildItem -LiteralPath $textureRoot -Filter "*.tga" -File |
    Sort-Object Name |
    ForEach-Object {
        @{
            Source = $_.FullName
            Entry = "textures/codex_nuke/$($_.Name)"
        }
    }

$entries = @($requiredEntries) + @($textureEntries)
foreach ($item in $entries) {
    if (-not (Test-Path -LiteralPath $item.Source -PathType Leaf)) {
        throw "Missing package input: $($item.Source)"
    }
}

$temporaryPath = "$packagePath.tmp"
if (Test-Path -LiteralPath $temporaryPath) {
    Remove-Item -LiteralPath $temporaryPath
}

$stream = [System.IO.File]::Open(
    $temporaryPath,
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
        foreach ($item in $entries) {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive,
                $item.Source,
                $item.Entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
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
Move-Item -LiteralPath $temporaryPath -Destination $packagePath

$package = Get-Item -LiteralPath $packagePath
$hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output ("Created {0} ({1:N0} bytes, sha256 {2})" -f $package.FullName, $package.Length, $hash)
