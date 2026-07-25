param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$MapName = "codex_dust2_v2",
    [string]$GeneratedFolder = "generated_dust2_v2",
    [switch]$SkipSource
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$generatedRoot = Join-Path $Workspace "work\$GeneratedFolder"
$mapRoot = Join-Path $generatedRoot "main\maps\dm"
$outputRoot = Join-Path $Workspace "outputs"
$packagePath = Join-Path $outputRoot "$MapName.pk3"
$sourcePath = Join-Path $outputRoot "$MapName-source.zip"

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
if (Test-Path -LiteralPath $packagePath) {
    Remove-Item -LiteralPath $packagePath
}

$stream = [System.IO.File]::Open(
    $packagePath,
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
        $entries = @(
            @{ Source = (Join-Path $mapRoot "$MapName.bsp"); Entry = "maps/dm/$MapName.bsp" },
            @{ Source = (Join-Path $mapRoot "$MapName.scr"); Entry = "maps/dm/$MapName.scr" },
            @{ Source = (Join-Path $mapRoot "${MapName}_precache.scr"); Entry = "maps/dm/${MapName}_precache.scr" }
        )

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

$file = Get-Item -LiteralPath $packagePath
Write-Output ("Created {0} ({1:N0} bytes)" -f $file.FullName, $file.Length)

if ($SkipSource) {
    return
}

if (Test-Path -LiteralPath $sourcePath) {
    Remove-Item -LiteralPath $sourcePath
}

$sourceStream = [System.IO.File]::Open(
    $sourcePath,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
)

try {
    $sourceArchive = [System.IO.Compression.ZipArchive]::new(
        $sourceStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )
    try {
        $sourceEntries = @(
            @{ Source = (Join-Path $mapRoot "$MapName.map"); Entry = "$MapName/main/maps/dm/$MapName.map" },
            @{ Source = (Join-Path $mapRoot "$MapName.scr"); Entry = "$MapName/main/maps/dm/$MapName.scr" },
            @{ Source = (Join-Path $mapRoot "${MapName}_precache.scr"); Entry = "$MapName/main/maps/dm/${MapName}_precache.scr" },
            @{ Source = (Join-Path $generatedRoot "$MapName-conversion-report.json"); Entry = "$MapName/conversion-report.json" },
            @{ Source = (Join-Path $Workspace "work\mapgen\analyze_vmf.js"); Entry = "$MapName/tools/analyze_vmf.js" },
            @{ Source = (Join-Path $Workspace "work\mapgen\generate_dust2_v2.js"); Entry = "$MapName/tools/generate_dust2_v2.js" },
            @{ Source = (Join-Path $Workspace "work\mapgen\package_dust2_v2.ps1"); Entry = "$MapName/tools/package_dust2_v2.ps1" },
            @{ Source = (Join-Path $Workspace "work\mapgen\README-dust2-v2.md"); Entry = "$MapName/README.md" }
        )

        foreach ($item in $sourceEntries) {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $sourceArchive,
                $item.Source,
                $item.Entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    }
    finally {
        $sourceArchive.Dispose()
    }
}
finally {
    $sourceStream.Dispose()
}

$sourceFile = Get-Item -LiteralPath $sourcePath
Write-Output ("Created {0} ({1:N0} bytes)" -f $sourceFile.FullName, $sourceFile.Length)
