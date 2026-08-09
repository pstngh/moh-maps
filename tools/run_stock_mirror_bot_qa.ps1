[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedRoot,
    [int]$SampleSeconds = 35,
    [int]$Port = 12371,
    [int]$GameTypeOverride = -1,
    [switch]$AllowNoCombat,
    [string]$ReportSuffix = "",
    [string]$RetailRoot = "",
    [string]$EnginePath = ""
)

$ErrorActionPreference = "Stop"
if ($SampleSeconds -lt 10 -or $SampleSeconds -gt 180) { throw "SampleSeconds must be between 10 and 180" }
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Port is outside the allowed range" }
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Split-Path -Parent $repositoryRoot
$GeneratedRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $GeneratedRoot))
if (-not $GeneratedRoot.StartsWith((Join-Path $repositoryRoot "generated"), [StringComparison]::OrdinalIgnoreCase)) {
    throw "GeneratedRoot must resolve below the repository generated directory"
}
$configPath = Join-Path $GeneratedRoot "mirror-config.json"
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "Missing mirror config: $configPath" }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
$packagePath = Join-Path $GeneratedRoot "$($config.mapName).pk3"
if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) { throw "Missing candidate package: $packagePath" }
if (-not $RetailRoot) { $RetailRoot = Join-Path $workRoot "runtime_base_stock" }
if (-not $EnginePath) { $EnginePath = Join-Path $workRoot "openmohaa-bin\runtime\omohaaded.exe" }
$RetailRoot = [IO.Path]::GetFullPath($RetailRoot)
$EnginePath = [IO.Path]::GetFullPath($EnginePath)
if (-not (Test-Path -LiteralPath $EnginePath -PathType Leaf)) { throw "Missing OpenMoHAA server: $EnginePath" }

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
if (-not $retailPackDirectory) { throw "Retail Pak0.pk3 through Pak6.pk3 were not found" }
$retailPaks = @(0..6 | ForEach-Object { $retailPackLookup["pak$_.pk3"] })

$qaRoot = [IO.Path]::GetFullPath((Join-Path "C:\tmp" "codex-$($config.mapName)-runtime"))
$expectedPrefix = [IO.Path]::GetFullPath("C:\tmp\codex-")
if (-not $qaRoot.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe QA root: $qaRoot" }
if (Test-Path -LiteralPath $qaRoot) { Remove-Item -LiteralPath $qaRoot -Recurse -Force }
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
New-Item -ItemType Directory -Path $baseMain,$homeMain -Force | Out-Null
foreach ($pack in $retailPaks) {
    $destination = Join-Path $baseMain $pack.Name
    try { New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $pack.FullName -Destination $destination }
}
$candidateName = "zz_$($config.mapName).pk3"
Copy-Item -LiteralPath $packagePath -Destination (Join-Path $baseMain $candidateName)
if (@(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count -ne 8) { throw "Isolated runtime must contain exactly eight PK3 files" }

$basePath = Join-Path $qaRoot "base"
$homePath = Join-Path $qaRoot "home"
$gameType = if ($GameTypeOverride -ge 0) { $GameTypeOverride } elseif ($config.gameDirectory -eq "obj") { 4 } else { 1 }
$mapPath = "$($config.gameDirectory)/$($config.mapName)"
$arguments = @(
    "+set", "fs_basepath", $basePath,
    "+set", "fs_homepath", $homePath,
    "+set", "dedicated", "1",
    "+set", "developer", "2",
    "+set", "logfile", "2",
    "+set", "net_port", "$Port",
    "+set", "g_gametype", "$gameType",
    "+set", "sv_maxclients", "16",
    "+set", "sv_maxbots", "8",
    "+set", "sv_numbots", "8",
    "+map", $mapPath
)
$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $EnginePath
$startInfo.Arguments = $arguments -join " "
$startInfo.WorkingDirectory = Split-Path -Parent $EnginePath
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$process = [Diagnostics.Process]::Start($startInfo)
try {
    Start-Sleep -Seconds $SampleSeconds
}
finally {
    if (-not $process.HasExited) { $process.Kill() }
    [void]$process.WaitForExit(2000)
}

$logPath = Join-Path $homeMain "qconsole.log"
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) { throw "OpenMoHAA did not write qconsole.log" }
$logLines = @(Get-Content -LiteralPath $logPath | ForEach-Object { $_.ToString() })
$botNames = @($logLines | ForEach-Object { if ($_ -match "(bot\d+) has entered the battle") { $Matches[1] } } | Sort-Object -Unique)
$combatLines = @($logLines | Where-Object {
    $_ -match "(?i)bot\d+.*(?:rifled|machine-gunned|hunted down|perforated|buckshot|rocket|blew (?:himself|herself) up|was .* by bot\d+)"
})
$candidateDiagnostics = @($logLines | Where-Object {
    $_ -match [regex]::Escape($config.mapName) -and $_ -match "(?i)error|failed|couldn.t|can't|not properly loaded|missing"
})
$bspParse = @($logLines | Where-Object { $_ -match "BSP file loaded and parsed in" })
$recast = @($logLines | Where-Object { $_ -match "Recast navigation mesh\(es\) generated in" })
$wrapperPrecache = @($logLines | Where-Object { $_ -match [regex]::Escape("maps/$($config.gameDirectory)/$($config.mapName)_precache.scr") }).Count

$report = [ordered]@{
    schemaVersion = 1
    qaRoot = $qaRoot
    mapName = $config.mapName
    gameType = $gameType
    exactPk3Count = @(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count
    candidateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant()
    engineSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnginePath).Hash.ToLowerInvariant()
    bspParse = $bspParse
    recast = $recast
    botsEntered = $botNames.Count
    botNames = $botNames
    combatEvents = $combatLines.Count
    combatRequired = -not [bool]$AllowNoCombat
    candidateDiagnostics = $candidateDiagnostics
    wrapperPrecacheReferences = $wrapperPrecache
    expectedRetailBotRunDiagnostics = @($logLines | Where-Object { $_ -match "global/bot_run.scr" }).Count
    scriptErrorCount = @($logLines | Where-Object { $_ -match "Script Error" }).Count
    sampleSeconds = $SampleSeconds
    log = $logPath
}
$reportStem = if ($ReportSuffix) { "$($config.mapName)-$ReportSuffix-runtime-qa.json" } else { "$($config.mapName)-runtime-qa.json" }
$reportPath = Join-Path $GeneratedRoot $reportStem
[IO.File]::WriteAllText($reportPath, (($report | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
if (-not $bspParse.Count -or -not $recast.Count) { throw "BSP/Recast completion was not observed" }
if ($botNames.Count -ne 8) { throw "Expected eight bots, observed $($botNames.Count)" }
if (-not $AllowNoCombat -and $combatLines.Count -lt 1) { throw "No bot combat event was observed" }
if ($candidateDiagnostics.Count) { throw "Candidate-specific runtime diagnostics: $($candidateDiagnostics -join ' | ')" }
Write-Output ($report | ConvertTo-Json -Depth 8)