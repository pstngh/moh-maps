[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot,
    [int]$TimeoutSeconds = 125
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [IO.Path]::GetFullPath($RepositoryRoot)
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$workRoot = Split-Path -Parent $RepositoryRoot
$mapName = "codex_cache"
$candidateExpected = "90477f688e4115400813b119a2061434a1f62324381b3cc864fa7bab29084c53"
$candidate = Join-Path $RepositoryRoot "generated\codex_cache\codex_cache.pk3"
$viewPlanPath = Join-Path $EvidenceRoot "fixed-view-plan.json"
$retailRoot = Join-Path $workRoot "runtime_base_stock\main"
$engine = Join-Path $workRoot "openmohaa-bin\runtime\openmohaa.exe"

foreach ($required in @($candidate, $viewPlanPath, $engine)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing input: $required" }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash.ToLowerInvariant() -ne $candidateExpected) {
    throw "Candidate hash changed before visual launch"
}
$viewPlan = Get-Content -Raw -LiteralPath $viewPlanPath | ConvertFrom-Json
if ($viewPlan.mapName -ne $mapName -or @($viewPlan.fixedViews).Count -lt 6) { throw "Invalid fixed-view plan" }

$qaRoot = [IO.Path]::GetFullPath("C:\tmp\codex-cache-r1-exact-visual")
$safeRoot = [IO.Path]::GetFullPath("C:\tmp\codex-")
if (-not $qaRoot.StartsWith($safeRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe QA root" }
if (Test-Path -LiteralPath $qaRoot) { Remove-Item -LiteralPath $qaRoot -Recurse -Force }
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
$looseMapRoot = Join-Path $homeMain "maps\dm"
$screenshotRoot = Join-Path $EvidenceRoot "visual-screenshots"
if (Test-Path -LiteralPath $screenshotRoot) { Remove-Item -LiteralPath $screenshotRoot -Recurse -Force }
New-Item -ItemType Directory -Path $baseMain, $looseMapRoot, $screenshotRoot -Force | Out-Null

$inventory = [Collections.Generic.List[object]]::new()
foreach ($number in 0..6) {
    $source = Join-Path $retailRoot "Pak$number.pk3"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing retail pack: $source" }
    $destination = Join-Path $baseMain "Pak$number.pk3"
    try { New-Item -ItemType HardLink -Path $destination -Target $source -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $source -Destination $destination }
    $item = Get-Item -LiteralPath $destination
    $inventory.Add([ordered]@{
        name = $item.Name
        bytes = $item.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
    })
}
$runtimePackage = Join-Path $baseMain "zz_codex_cache.pk3"
Copy-Item -LiteralPath $candidate -Destination $runtimePackage
$inventory.Add([ordered]@{
    name = "zz_codex_cache.pk3"
    bytes = (Get-Item -LiteralPath $runtimePackage).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimePackage).Hash.ToLowerInvariant()
})
if (@(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count -ne 8) { throw "Visual runtime does not contain exactly eight PK3s" }
if ($inventory[-1].sha256 -ne $candidateExpected) { throw "Visual runtime candidate copy hash mismatch" }

$scriptLines = [Collections.Generic.List[string]]::new()
foreach ($line in @(
    "main:",
    "",
    "level waittill prespawn",
    "exec global/DMprecache.scr",
    "level.script = maps/dm/codex_cache.scr",
    "level waittill spawn",
    "thread evidence_probe",
    "end",
    "",
    "evidence_probe:",
    "wait 6",
    '$player stufftext "ui_applyplayermodel"',
    "wait .25",
    '$player stufftext "con_notifytime 0"',
    "wait .25",
    '$player auto_join_team',
    "wait 3",
    '$player primarydmweapon rifle',
    "wait 3",
    '$player stufftext "popmenu 0"',
    "wait .25",
    '$player stufftext "popmenu 0"',
    "wait .25",
    '$player stufftext "popmenu 0"',
    "wait .25",
    '$player stufftext "ui_hidemouse"
$player stufftext "ui_hud 0"
$player stufftext "cg_drawviewmodel 0"
$player stufftext "clear"',
    '$player stufftext "noclip"',
    '$player stufftext "notarget"',
    "wait 8"
)) { [void]$scriptLines.Add($line) }

foreach ($view in @($viewPlan.fixedViews)) {
    $origin = @($view.origin) -join " "
    $angles = @($view.viewangles) -join " "
    [void]$scriptLines.Add('$player stufftext "popmenu 0"')
    [void]$scriptLines.Add('$player stufftext "ui_hidemouse"
$player stufftext "ui_hud 0"')
    [void]$scriptLines.Add(('println "CODEX_VISUAL_QA {0}"' -f $view.id))
    [void]$scriptLines.Add("`$player.origin = ( $origin )")
    [void]$scriptLines.Add("`$player.viewangles = ( $angles )")
    [void]$scriptLines.Add("wait .35")
    [void]$scriptLines.Add("`$player.viewangles = ( $angles )")
    [void]$scriptLines.Add('$player stufftext "screenshot"')
    [void]$scriptLines.Add("wait 5")
}
[void]$scriptLines.Add("wait 1")
[void]$scriptLines.Add('$player stufftext "quit"')
[void]$scriptLines.Add("end")

$looseScript = Join-Path $looseMapRoot "codex_cache.scr"
[IO.File]::WriteAllText($looseScript, (($scriptLines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))

$basePath = Join-Path $qaRoot "base"
$homePath = Join-Path $qaRoot "home"
$arguments = @(
    "+set", "fs_basepath", $basePath,
    "+set", "fs_homepath", $homePath,
    "+set", "developer", "2",
    "+set", "logfile", "2",
    "+set", "g_gametype", "1",
    "+set", "g_inactiveSpectate", "0",
    "+set", "g_inactiveKick", "0",
    "+set", "cg_drawviewmodel", "0",
    "+set", "r_fullscreen", "0",
    "+set", "r_mode", "-1",
    "+set", "r_customwidth", "1280",
    "+set", "r_customheight", "720",
    "+set", "com_maxfps", "60",
    "+map", "dm/codex_cache"
)
$stdoutPath = Join-Path $EvidenceRoot "visual-engine.stdout.log"
$stderrPath = Join-Path $EvidenceRoot "visual-engine.stderr.log"
foreach ($path in @($stdoutPath, $stderrPath)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }

$timedOut = $false
$timer = [Diagnostics.Stopwatch]::StartNew()
$process = Start-Process -FilePath $engine -ArgumentList $arguments -WorkingDirectory (Split-Path -Parent $engine) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
try {
    while (-not $process.HasExited -and $timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
}
finally {
    if (-not $process.HasExited) {
        $timedOut = $true
        $taskKillPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::System)) "taskkill.exe"
        Start-Process -FilePath $taskKillPath -ArgumentList @("/PID", $process.Id, "/T", "/F") -WindowStyle Hidden | Out-Null
        Start-Sleep -Milliseconds 1000
    }
    $timer.Stop()
}

$qconsoleRuntime = Join-Path $homeMain "qconsole.log"
$qconsoleCopy = Join-Path $EvidenceRoot "visual-qconsole.log"
if (Test-Path -LiteralPath $qconsoleRuntime -PathType Leaf) { Copy-Item -LiteralPath $qconsoleRuntime -Destination $qconsoleCopy -Force }
$logLines = if (Test-Path -LiteralPath $qconsoleCopy -PathType Leaf) { @([IO.File]::ReadAllLines($qconsoleCopy)) } else { @() }
$runtimeScreenshots = [Collections.Generic.List[IO.FileInfo]]::new()
foreach ($candidateDirectory in @((Join-Path $homeMain "screenshots"), (Join-Path $homePath "screenshots"), $homeMain)) {
    if (Test-Path -LiteralPath $candidateDirectory -PathType Container) {
        foreach ($shot in Get-ChildItem -LiteralPath $candidateDirectory -Filter "*.tga" -File | Sort-Object FullName) { $runtimeScreenshots.Add($shot) }
    }
}
$uniqueScreenshots = @($runtimeScreenshots | Sort-Object FullName -Unique)
$screenshotRecords = [Collections.Generic.List[object]]::new()
foreach ($shot in $uniqueScreenshots) {
    $copy = Join-Path $screenshotRoot $shot.Name
    Copy-Item -LiteralPath $shot.FullName -Destination $copy -Force
    $item = Get-Item -LiteralPath $copy
    $screenshotRecords.Add([ordered]@{
        path = $item.FullName
        bytes = $item.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
    })
}
$markers = @($logLines | Where-Object { $_ -match "CODEX_VISUAL_QA" })
$scriptErrors = @($logLines | Where-Object { $_ -match "Script Error" })
$report = [ordered]@{
    schemaVersion = 2
    mapName = $mapName
    qaRoot = $qaRoot
    exactPk3Count = 8
    candidateSha256 = $candidateExpected
    runtimePackage = $runtimePackage
    runtimePackageSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimePackage).Hash.ToLowerInvariant()
    enginePath = $engine
    engineSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $engine).Hash.ToLowerInvariant()
    arguments = $arguments
    fsBasepath = $basePath
    fsHomepath = $homePath
    packageInventory = $inventory
    looseOverride = "maps/dm/codex_cache.scr only; fixed-camera and modal-dismissal instrumentation; BSP/assets remain from exact candidate PK3"
    looseScript = $looseScript
    looseScriptSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $looseScript).Hash.ToLowerInvariant()
    clientEntryAndModalDismissal = @("launch +set g_inactiveSpectate 0", "launch +set g_inactiveKick 0", "launch +set cg_drawviewmodel 0", "ui_applyplayermodel", "con_notifytime 0", "direct server-side $player auto_join_team event", "3-second event sequencing wait", "direct server-side $player primarydmweapon rifle event", "3-second server-response wait", "popmenu 0", "popmenu 0", "popmenu 0", "ui_hidemouse", "ui_hud 0", "cg_drawviewmodel 0 reaffirmed", "clear", "8-second notification fade before first capture", "repeated popmenu 0, ui_hidemouse, and ui_hud 0 before each screenshot", "5-second notification fade after each screenshot")
    requestedViews = @($viewPlan.fixedViews | ForEach-Object { $_.id })
    viewMarkers = $markers
    screenshotCount = $screenshotRecords.Count
    screenshots = $screenshotRecords
    scriptErrorCount = $scriptErrors.Count
    scriptErrors = $scriptErrors
    elapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    timedOut = $timedOut
    exitCode = if ($process.HasExited) { $process.ExitCode } else { $null }
    log = $qconsoleCopy
    runtimeLog = $qconsoleRuntime
    stdoutLog = $stdoutPath
    stderrLog = $stderrPath
}
$reportPath = Join-Path $EvidenceRoot "visual-report.json"
[IO.File]::WriteAllText($reportPath, (($report | ConvertTo-Json -Depth 12) + "`n"), [Text.UTF8Encoding]::new($false))
$donePath = Join-Path $EvidenceRoot "visual-probe.done.json"
[IO.File]::WriteAllText($donePath, (([ordered]@{ report = $reportPath; elapsedSeconds = $report.elapsedSeconds; screenshotCount = $report.screenshotCount; scriptErrorCount = $report.scriptErrorCount } | ConvertTo-Json) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output ($report | ConvertTo-Json -Depth 12)
