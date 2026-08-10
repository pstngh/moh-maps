[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent $PSCommandPath
$DestinationRoot = Join-Path $RepositoryRoot "generated\codex_cache\evidence\revision-1-exact-hash-20260810"
$Screenshots = Join-Path $DestinationRoot "screenshots"
$Logs = Join-Path $DestinationRoot "logs"
$Reports = Join-Path $DestinationRoot "reports"
$Instrumentation = Join-Path $DestinationRoot "instrumentation"
foreach ($Directory in @($DestinationRoot, $Screenshots, $Logs, $Reports, $Instrumentation)) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
}

Get-ChildItem -LiteralPath (Join-Path $SourceRoot "visual-png") -Filter "shot*.png" -File |
    Copy-Item -Destination $Screenshots -Force

$LogNames = @(
    "visual-qconsole.log", "visual-engine.stdout.log", "visual-engine.stderr.log",
    "visual-launch.stdout.log", "visual-launch.stderr.log",
    "bot-standard-qconsole.log", "bot-standard-launch.stdout.log", "bot-standard-launch.stderr.log",
    "bot-instrumented-qconsole.log", "bot-instrumented-engine.stdout.log", "bot-instrumented-engine.stderr.log",
    "bot-instrument-full-launch.stdout.log", "bot-instrument-full-launch.stderr.log",
    "bot-lifecycle-observations.log", "bot-route-observations.log",
    "door-instrumented-qconsole.log", "door-instrumented-engine.stdout.log", "door-instrumented-engine.stderr.log",
    "door-instrument-clean-launch.stdout.log", "door-instrument-clean-launch.stderr.log"
)
foreach ($Name in $LogNames) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination (Join-Path $Logs $Name) -Force
}

$ReportNames = @(
    "fixed-view-plan.json", "bot-standard-package-inventory.json",
    "bot-instrumented-report.json", "bot-route-analysis.json", "door-instrumented-report.json"
)
foreach ($Name in $ReportNames) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination (Join-Path $Reports $Name) -Force
}
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "generated\codex_cache\codex_cache-runtime-qa.json") `
    -Destination (Join-Path $Reports "bot-runtime-report.json") -Force

$HarnessNames = @(
    "run_visual_probe.ps1", "correct_visual_harness.ps1",
    "run_bot_instrument_probe.ps1", "correct_bot_instrument_harness.ps1",
    "analyze_bot_instrument_v2.ps1", "run_door_instrument_probe.ps1",
    "fix_door_instrument_harness.ps1"
)
foreach ($Name in $HarnessNames) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination (Join-Path $Instrumentation $Name) -Force
}

$LooseScripts = @(
    @{ Source = "C:\tmp\codex-cache-r1-exact-visual\home\main\maps\dm\codex_cache.scr"; Destination = "visual-codex_cache.scr" },
    @{ Source = "C:\tmp\codex-cache-r1-bot-instrumented\home\main\maps\dm\codex_cache.scr"; Destination = "bot-codex_cache.scr" },
    @{ Source = "C:\tmp\codex-cache-r1-door-instrumented\home\main\maps\dm\codex_cache.scr"; Destination = "door-codex_cache.scr" }
)
foreach ($Script in $LooseScripts) {
    if (-not (Test-Path -LiteralPath $Script.Source -PathType Leaf)) {
        throw "Required final instrumentation script is missing: $($Script.Source)"
    }
    Copy-Item -LiteralPath $Script.Source -Destination (Join-Path $Instrumentation $Script.Destination) -Force
}

Write-Output $DestinationRoot
