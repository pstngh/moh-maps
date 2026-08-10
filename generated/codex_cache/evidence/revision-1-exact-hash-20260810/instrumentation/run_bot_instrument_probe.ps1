[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot,
    [int]$SampleSeconds = 105,
    [int]$Port = 12390
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [IO.Path]::GetFullPath($RepositoryRoot)
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$workRoot = Split-Path -Parent $RepositoryRoot
$mapName = "codex_cache"
$expectedCandidate = "90477f688e4115400813b119a2061434a1f62324381b3cc864fa7bab29084c53"
$candidate = Join-Path $RepositoryRoot "generated\codex_cache\codex_cache.pk3"
$retailMain = Join-Path $workRoot "runtime_base_stock\main"
$engine = Join-Path $workRoot "openmohaa-bin\runtime\omohaaded.exe"
$gameDll = Join-Path $workRoot "openmohaa-bin\runtime\game.dll"

foreach ($required in @($candidate, $engine, $gameDll)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing instrumentation input: $required"
    }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash.ToLowerInvariant() -ne $expectedCandidate) {
    throw "Candidate hash mismatch"
}

$qaRoot = [IO.Path]::GetFullPath("C:\tmp\codex-cache-r1-bot-instrumented")
if (-not $qaRoot.StartsWith([IO.Path]::GetFullPath("C:\tmp\codex-cache-r1-"), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe instrumentation root: $qaRoot"
}
if (Test-Path -LiteralPath $qaRoot) {
    Remove-Item -LiteralPath $qaRoot -Recurse -Force
}
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
$looseMapRoot = Join-Path $homeMain "maps\dm"
New-Item -ItemType Directory -Path $baseMain, $homeMain, $looseMapRoot -Force | Out-Null

foreach ($index in 0..6) {
    $pack = Join-Path $retailMain ("Pak{0}.pk3" -f $index)
    if (-not (Test-Path -LiteralPath $pack -PathType Leaf)) {
        throw "Missing retail package: $pack"
    }
    $destination = Join-Path $baseMain (Split-Path -Leaf $pack)
    try {
        New-Item -ItemType HardLink -Path $destination -Target $pack -ErrorAction Stop | Out-Null
    } catch {
        Copy-Item -LiteralPath $pack -Destination $destination
    }
}
Copy-Item -LiteralPath $candidate -Destination (Join-Path $baseMain "zz_codex_cache.pk3")

$instrumentScript = @'
main:

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/codex_cache.scr
level waittill spawn
thread codex_bot_probe
end

codex_bot_probe:

wait 8
local.sample = 0

while (local.sample < 90)
{
    local.index = 1
    while (local.index < $player.size + 1)
    {
        local.ent = $player[local.index]
        local.alive = IsAlive local.ent
        println ("CODEX_BOT_SAMPLE sample=" + local.sample + " player_index=" + local.index + " alive=" + local.alive + " origin=" + local.ent.origin)
        local.index++
    }

    local.sample++
    wait 1
}

println "CODEX_BOT_PROBE_COMPLETE samples=90"
end
'@
$looseScript = Join-Path $looseMapRoot "codex_cache.scr"
[IO.File]::WriteAllText($looseScript, $instrumentScript, [Text.UTF8Encoding]::new($false))

$packageInventory = @(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File | Sort-Object Name | ForEach-Object {
    [ordered]@{
        name = $_.Name
        bytes = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        path = $_.FullName
    }
})
if ($packageInventory.Count -ne 8) {
    throw "Instrumentation runtime must contain exactly eight PK3 files"
}
$runtimeCandidate = $packageInventory | Where-Object name -eq "zz_codex_cache.pk3"
if ($runtimeCandidate.sha256 -ne $expectedCandidate) {
    throw "Instrumentation runtime candidate hash mismatch"
}

$arguments = @(
    "+set", "fs_basepath", (Join-Path $qaRoot "base"),
    "+set", "fs_homepath", (Join-Path $qaRoot "home"),
    "+set", "dedicated", "1",
    "+set", "developer", "2",
    "+set", "logfile", "2",
    "+set", "cheats", "1",
    "+set", "net_port", "$Port",
    "+set", "g_gametype", "1",
    "+set", "sv_maxclients", "16",
    "+set", "sv_maxbots", "8",
    "+set", "sv_numbots", "8",
    "+map", "dm/codex_cache"
)
$stdoutPath = Join-Path $EvidenceRoot "bot-instrumented-engine.stdout.log"
$stderrPath = Join-Path $EvidenceRoot "bot-instrumented-engine.stderr.log"
foreach ($path in @($stdoutPath, $stderrPath)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$timer = [Diagnostics.Stopwatch]::StartNew()
$process = Start-Process -FilePath $engine -ArgumentList $arguments -WorkingDirectory (Split-Path -Parent $engine) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
try {
    Start-Sleep -Seconds $SampleSeconds
} finally {
    if (-not $process.HasExited) {
        $process.Kill()
    }
    [void]$process.WaitForExit(5000)
    $timer.Stop()
}

$runtimeLog = Join-Path $homeMain "qconsole.log"
if (-not (Test-Path -LiteralPath $runtimeLog -PathType Leaf)) {
    throw "Instrumented server did not write qconsole.log"
}
$preservedLog = Join-Path $EvidenceRoot "bot-instrumented-qconsole.log"
Copy-Item -LiteralPath $runtimeLog -Destination $preservedLog -Force
$sampleLines = @(Select-String -LiteralPath $preservedLog -Pattern "CODEX_BOT_SAMPLE")
$doorLines = @(Select-String -LiteralPath $preservedLog -Pattern "CODEX_DOOR_SAMPLE")
$scriptErrors = @(Select-String -LiteralPath $preservedLog -Pattern "Script Error")
$combatLines = @(Select-String -LiteralPath $preservedLog -Pattern "(?i)bot\d+.*(?:rifled|machine-gunned|hunted down|perforated|buckshot|rocket|blew (?:himself|herself) up|was .* by bot\d+)")
$botNames = @(Select-String -LiteralPath $preservedLog -Pattern "(bot\d+) has entered the battle" | ForEach-Object { if ($_.Line -match "(bot\d+) has entered the battle") { $Matches[1] } } | Sort-Object -Unique)

$report = [ordered]@{
    schemaVersion = 1
    lane = "supplemental-instrumented-not-package-pure"
    mapName = $mapName
    qaRoot = $qaRoot
    candidateSha256 = $expectedCandidate
    runtimeCandidateSha256 = $runtimeCandidate.sha256
    exactPk3Count = $packageInventory.Count
    packageInventory = $packageInventory
    enginePath = $engine
    engineSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $engine).Hash.ToLowerInvariant()
    gameDllPath = $gameDll
    gameDllSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $gameDll).Hash.ToLowerInvariant()
    arguments = $arguments
    looseOverride = @{
        path = $looseScript
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $looseScript).Hash.ToLowerInvariant()
        purpose = "supplemental bot position/lifecycle and rotating-door sampling only"
    }
    elapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    requestedSampleSeconds = $SampleSeconds
    botSampleLines = $sampleLines.Count
    doorSampleLines = $doorLines.Count
    botNames = $botNames
    combatEvents = $combatLines.Count
    scriptErrorCount = $scriptErrors.Count
    scriptErrors = $scriptErrors
    runtimeLog = $preservedLog
    runtimeLogSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $preservedLog).Hash.ToLowerInvariant()
    stdoutLog = $stdoutPath
    stderrLog = $stderrPath
}
$reportPath = Join-Path $EvidenceRoot "bot-instrumented-report.json"
[IO.File]::WriteAllText($reportPath, (($report | ConvertTo-Json -Depth 10) + "`n"), [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $EvidenceRoot "bot-instrumented.done.json"), (([ordered]@{ report = $reportPath; elapsedSeconds = $report.elapsedSeconds; botSampleLines = $report.botSampleLines; doorSampleLines = $report.doorSampleLines; scriptErrorCount = $report.scriptErrorCount } | ConvertTo-Json) + "`n"), [Text.UTF8Encoding]::new($false))

Write-Output (([ordered]@{ report = $reportPath; botSampleLines = $report.botSampleLines; doorSampleLines = $report.doorSampleLines; scriptErrorCount = $report.scriptErrorCount } | ConvertTo-Json))
