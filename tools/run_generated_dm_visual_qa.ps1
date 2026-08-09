[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedRoot,
    [string]$MapName = "",
    [int]$TimeoutSeconds = 45,
    [string]$RetailRoot = "",
    [string]$EnginePath = ""
)

$ErrorActionPreference = "Stop"
if ($TimeoutSeconds -lt 15 -or $TimeoutSeconds -gt 60) { throw "TimeoutSeconds must be between 15 and 60" }
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Split-Path -Parent $repositoryRoot
$GeneratedRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $GeneratedRoot))
$generatedPrefix = [IO.Path]::GetFullPath((Join-Path $repositoryRoot "generated"))
if (-not $GeneratedRoot.StartsWith($generatedPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "GeneratedRoot must resolve below generated" }
if (-not $MapName) { $MapName = Split-Path -Leaf $GeneratedRoot }
if ($MapName -notmatch "^[A-Za-z0-9_]+$") { throw "Invalid map name" }
if (-not $RetailRoot) { $RetailRoot = Join-Path $workRoot "runtime_base_stock" }
if (-not $EnginePath) { $EnginePath = Join-Path $workRoot "openmohaa-bin\runtime\openmohaa.exe" }
$EnginePath = [IO.Path]::GetFullPath($EnginePath)
$packagePath = Join-Path $GeneratedRoot "$MapName.pk3"
$designReportPath = Join-Path $GeneratedRoot "$MapName-design-report.json"
foreach ($required in @($EnginePath, $packagePath, $designReportPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing visual-QA input: $required" }
}
$design = Get-Content -Raw -LiteralPath $designReportPath | ConvertFrom-Json
if (@($design.fixedViews).Count -lt 6) { throw "Design report lacks a useful fixed-view matrix" }

$retailPackDirectory = ""
foreach ($candidate in @($RetailRoot, (Join-Path $RetailRoot "main"))) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) { continue }
    $lookup = @{}
    foreach ($pack in Get-ChildItem -LiteralPath $candidate -Filter "*.pk3" -File) { $lookup[$pack.Name.ToLowerInvariant()] = $pack }
    if (@(0..6 | Where-Object { -not $lookup.ContainsKey("pak$_.pk3") }).Count -eq 0) { $retailPackLookup = $lookup; $retailPackDirectory = $candidate; break }
}
if (-not $retailPackDirectory) { throw "Retail Pak0.pk3 through Pak6.pk3 were not found" }

$qaRoot = [IO.Path]::GetFullPath((Join-Path "C:\tmp" "codex-$MapName-visual"))
$safePrefix = [IO.Path]::GetFullPath("C:\tmp\codex-")
if (-not $qaRoot.StartsWith($safePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe visual QA root: $qaRoot" }
if (Test-Path -LiteralPath $qaRoot) { Remove-Item -LiteralPath $qaRoot -Recurse -Force }
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
$looseMapRoot = Join-Path $homeMain "maps\dm"
New-Item -ItemType Directory -Path $baseMain, $looseMapRoot -Force | Out-Null
foreach ($number in 0..6) {
    $pack = $retailPackLookup["pak$number.pk3"]
    $destination = Join-Path $baseMain $pack.Name
    try { New-Item -ItemType HardLink -Path $destination -Target $pack.FullName -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $pack.FullName -Destination $destination }
}
Copy-Item -LiteralPath $packagePath -Destination (Join-Path $baseMain "zz_$MapName.pk3")
if (@(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File).Count -ne 8) { throw "Visual root must contain exactly eight PK3 files" }

$scriptLines = [Collections.Generic.List[string]]::new()
foreach ($line in @(
    "main:", "", "level waittill prespawn", "exec global/DMprecache.scr", "level.script = maps/dm/$MapName.scr", "level waittill spawn", "thread visual_qa", "", "end", "", "visual_qa:", "", "wait 4", '$player stufftext "noclip"', '$player stufftext "notarget"', "wait 1"
)) { [void]$scriptLines.Add($line) }
foreach ($view in @($design.fixedViews)) {
    $origin = @($view.origin) -join " "
    $angles = @($view.viewangles) -join " "
    [void]$scriptLines.Add(('println "CODEX_VISUAL_QA {0}"' -f $view.id))
    [void]$scriptLines.Add("`$player.origin = ( $origin )")
    [void]$scriptLines.Add("`$player.viewangles = ( $angles )")
    [void]$scriptLines.Add("wait .2")
    [void]$scriptLines.Add("`$player.viewangles = ( $angles )")
    [void]$scriptLines.Add('$player stufftext "screenshot"')
    [void]$scriptLines.Add("wait .8")
}
[void]$scriptLines.Add('$player stufftext "quit"')
[void]$scriptLines.Add("end")
$looseScript = Join-Path $looseMapRoot "$MapName.scr"
[IO.File]::WriteAllText($looseScript, (($scriptLines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))

$basePath = Join-Path $qaRoot "base"
$homePath = Join-Path $qaRoot "home"
$arguments = @(
    "+set", "fs_basepath", $basePath,
    "+set", "fs_homepath", $homePath,
    "+set", "developer", "2",
    "+set", "logfile", "2",
    "+set", "g_gametype", "1",
    "+set", "r_fullscreen", "0",
    "+set", "r_mode", "-1",
    "+set", "r_customwidth", "1280",
    "+set", "r_customheight", "720",
    "+set", "com_maxfps", "60",
    "+map", "dm/$MapName"
)
$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $EnginePath
$startInfo.Arguments = $arguments -join " "
$startInfo.WorkingDirectory = Split-Path -Parent $EnginePath
$startInfo.UseShellExecute = $true
$process = [Diagnostics.Process]::Start($startInfo)
$timer = [Diagnostics.Stopwatch]::StartNew()
try {
    while (-not $process.HasExited -and $timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
}
finally {
    if (-not $process.HasExited) {
        $taskKillPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::System)) "taskkill.exe"
        Start-Process -FilePath $taskKillPath -ArgumentList @("/PID", $process.Id, "/T", "/F") -WindowStyle Hidden | Out-Null
        Start-Sleep -Milliseconds 1000
    }
    $timer.Stop()
}

$screenshots = @()
foreach ($candidate in @((Join-Path $homeMain "screenshots"), (Join-Path $homePath "screenshots"), $homeMain)) {
    if (Test-Path -LiteralPath $candidate -PathType Container) {
        $screenshots += @(Get-ChildItem -LiteralPath $candidate -Filter "*.tga" -File)
    }
}
$screenshots = @($screenshots | Sort-Object FullName -Unique)
$logPath = Join-Path $homeMain "qconsole.log"
$logLines = if (Test-Path -LiteralPath $logPath -PathType Leaf) { @([IO.File]::ReadAllLines($logPath)) } else { @() }
$viewMarkers = @($logLines | Where-Object { $_ -match "CODEX_VISUAL_QA" })
$scriptErrors = @($logLines | Where-Object { $_ -match "Script Error" })
$report = [ordered]@{
    schemaVersion = 1
    mapName = $MapName
    qaRoot = $qaRoot
    exactPk3Count = 8
    candidateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant()
    looseOverride = "maps/dm/$MapName.scr only; BSP/assets remain from exact candidate PK3"
    requestedViews = @($design.fixedViews | ForEach-Object { $_.id })
    viewMarkers = $viewMarkers
    screenshotCount = $screenshots.Count
    screenshots = @($screenshots | ForEach-Object { [ordered]@{ path = $_.FullName; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() } })
    scriptErrorCount = $scriptErrors.Count
    elapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
    log = $logPath
}
$reportPath = Join-Path $GeneratedRoot "$MapName-visual-qa.json"
[IO.File]::WriteAllText($reportPath, (($report | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
if ($scriptErrors.Count) { throw "Visual QA script errors: $($scriptErrors -join ' | ')" }
if ($screenshots.Count -lt @($design.fixedViews).Count) { throw "Expected $(@($design.fixedViews).Count) screenshots, found $($screenshots.Count)" }
Write-Output ($report | ConvertTo-Json -Depth 8)
