[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedRoot,
    [string]$MapName = "",
    [int]$SampleSeconds = 35,
    [int]$Port = 12381,
    [int]$MinimumCombatEvents = 1,
    [string]$RetailRoot = "",
    [string]$EnginePath = ""
)

$ErrorActionPreference = "Stop"
if ($SampleSeconds -lt 10 -or $SampleSeconds -gt 180) { throw "SampleSeconds must be between 10 and 180" }
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Port is outside the allowed range" }
if ($MinimumCombatEvents -lt 1) { throw "MinimumCombatEvents must be positive" }
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Split-Path -Parent $repositoryRoot
$GeneratedRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $GeneratedRoot))
$generatedPrefix = [IO.Path]::GetFullPath((Join-Path $repositoryRoot "generated"))
if (-not $GeneratedRoot.StartsWith($generatedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "GeneratedRoot must resolve below the repository generated directory"
}
if (-not $MapName) { $MapName = Split-Path -Leaf $GeneratedRoot }
if ($MapName -notmatch "^[A-Za-z0-9_]+$") { throw "MapName may contain only letters, numbers, and underscores" }
$packagePath = Join-Path $GeneratedRoot "$MapName.pk3"
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

$qaRoot = [IO.Path]::GetFullPath((Join-Path "C:\tmp" "codex-$MapName-runtime"))
$expectedPrefix = [IO.Path]::GetFullPath("C:\tmp\codex-")
if (-not $qaRoot.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe QA root: $qaRoot" }
if (Test-Path -LiteralPath $qaRoot) { Remove-Item -LiteralPath $qaRoot -Recurse -Force }
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
New-Item -ItemType Directory -Path $baseMain, $homeMain -Force | Out-Null
foreach ($pack in $retailPaks) {
    $destination = Join-Path $baseMain $pack.Name
    try { New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $pack.FullName -Destination $destination }
}
Copy-Item -LiteralPath $packagePath -Destination (Join-Path $baseMain "zz_$MapName.pk3")
if (@(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count -ne 8) { throw "Isolated runtime must contain exactly eight PK3 files" }

$basePath = Join-Path $qaRoot "base"
$homePath = Join-Path $qaRoot "home"
$arguments = @(
    "+set", "fs_basepath", $basePath,
    "+set", "fs_homepath", $homePath,
    "+set", "dedicated", "1",
    "+set", "developer", "2",
    "+set", "logfile", "2",
    "+set", "net_port", "$Port",
    "+set", "g_gametype", "1",
    "+set", "sv_maxclients", "16",
    "+set", "sv_maxbots", "8",
    "+set", "sv_numbots", "8",
    "+map", "dm/$MapName"
)
$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $EnginePath
$startInfo.Arguments = $arguments -join " "
$startInfo.WorkingDirectory = Split-Path -Parent $EnginePath
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$process = [Diagnostics.Process]::Start($startInfo)
try { Start-Sleep -Seconds $SampleSeconds }
finally {
    if (-not $process.HasExited) { $process.Kill() }
    [void]$process.WaitForExit(3000)
}

$logPath = Join-Path $homeMain "qconsole.log"
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) { throw "OpenMoHAA did not write qconsole.log" }
$logLines = @(Get-Content -LiteralPath $logPath | ForEach-Object { $_.ToString() })
$botNames = @($logLines | ForEach-Object { if ($_ -match "(bot\d+) has entered the battle") { $Matches[1] } } | Sort-Object -Unique)
$combatLines = @($logLines | Where-Object {
    $_ -match "(?i)bot\d+.*(?:rifled|machine-gunned|hunted down|perforated|buckshot|rocket|blew (?:himself|herself) up|was .* by bot\d+)"
})
$candidateDiagnostics = @($logLines | Where-Object {
    $_ -match [regex]::Escape($MapName) -and $_ -match "(?i)error|failed|couldn.t|can't|not properly loaded|missing"
})
$assetDiagnostics = @($logLines | Where-Object {
    $_ -match "(?i)lightbulb_caged|corona_orange|vehicle_opeltruck" -and $_ -match "(?i)error|failed|couldn.t|can't|not properly loaded|missing"
})
$bspParse = @($logLines | Where-Object { $_ -match "BSP file loaded and parsed in" })
$recast = @($logLines | Where-Object { $_ -match "Recast navigation mesh\(es\) generated in" })
$scriptErrors = @($logLines | Where-Object { $_ -match "Script Error" })

$report = [ordered]@{
    schemaVersion = 1
    qaRoot = $qaRoot
    mapName = $MapName
    gameType = 1
    exactPk3Count = @(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count
    candidateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant()
    engineSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnginePath).Hash.ToLowerInvariant()
    bspParse = $bspParse
    recast = $recast
    botsEntered = $botNames.Count
    botNames = $botNames
    combatEvents = $combatLines.Count
    minimumCombatEvents = $MinimumCombatEvents
    candidateDiagnostics = $candidateDiagnostics
    stockAssetDiagnostics = $assetDiagnostics
    scriptErrorCount = $scriptErrors.Count
    sampleSeconds = $SampleSeconds
    log = $logPath
}
$reportPath = Join-Path $GeneratedRoot "$MapName-runtime-qa.json"
[IO.File]::WriteAllText($reportPath, (($report | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
if (-not $bspParse.Count -or -not $recast.Count) { throw "BSP/Recast completion was not observed" }
if ($botNames.Count -ne 8) { throw "Expected eight bots, observed $($botNames.Count)" }
if ($combatLines.Count -lt $MinimumCombatEvents) { throw "Only $($combatLines.Count) combat events were observed" }
if ($candidateDiagnostics.Count) { throw "Candidate-specific runtime diagnostics: $($candidateDiagnostics -join ' | ')" }
if ($assetDiagnostics.Count) { throw "Stock model runtime diagnostics: $($assetDiagnostics -join ' | ')" }
if ($scriptErrors.Count) { throw "Unexpected script errors: $($scriptErrors -join ' | ')" }
Write-Output ($report | ConvertTo-Json -Depth 8)
