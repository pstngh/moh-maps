$ErrorActionPreference = "Stop"

$evidenceRoot = $PSScriptRoot
$harnessPath = Join-Path $evidenceRoot "run_bot_instrument_probe.ps1"
$failedRoot = Join-Path $evidenceRoot "failed-bot-instrument-smoke"

if (Test-Path -LiteralPath $failedRoot) {
    throw "Refusing to overwrite preserved failed smoke test: $failedRoot"
}
New-Item -ItemType Directory -Path $failedRoot -Force | Out-Null
foreach ($name in @(
    "bot-instrumented-qconsole.log",
    "bot-instrumented-engine.stdout.log",
    "bot-instrumented-engine.stderr.log",
    "bot-instrumented-report.json",
    "bot-instrumented.done.json"
)) {
    $source = Join-Path $evidenceRoot $name
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination $failedRoot -Recurse
    }
}
$runtimeScript = "C:\tmp\codex-cache-r1-bot-instrumented\home\main\maps\dm\codex_cache.scr"
if (Test-Path -LiteralPath $runtimeScript) {
    Copy-Item -LiteralPath $runtimeScript -Destination (Join-Path $failedRoot "codex_cache.scr")
}

$text = [IO.File]::ReadAllText($harnessPath)
$replacements = [ordered]@{
    'local.doors = getentarray "func_rotatingdoor" "classname"' = 'local.doors = getentarray "RotatingDoor" "classname"'
    'while (local.slot < 8)' = 'while (local.slot < 16)'
}
foreach ($pair in $replacements.GetEnumerator()) {
    if (-not $text.Contains($pair.Key)) {
        throw "Expected instrumentation text not found: $($pair.Key)"
    }
    $text = $text.Replace($pair.Key, $pair.Value)
}
[IO.File]::WriteAllText($harnessPath, $text, [Text.UTF8Encoding]::new($false))

foreach ($name in @("bot-instrumented-report.json", "bot-instrumented.done.json")) {
    $target = Join-Path $evidenceRoot $name
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Force
    }
}

Write-Output "Preserved failed smoke test at $failedRoot"
Write-Output "Updated $harnessPath"
