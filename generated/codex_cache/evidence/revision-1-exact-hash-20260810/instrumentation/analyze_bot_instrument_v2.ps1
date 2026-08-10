[CmdletBinding()]
param([string]$EvidenceRoot = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$logPath = Join-Path $EvidenceRoot "bot-instrumented-qconsole.log"
$logHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $logPath).Hash.ToLowerInvariant()
$pattern = 'CODEX_BOT_SAMPLE sample=(\d+) player_index=(\d+) alive=(\d+) origin=\(\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\)'
$culture = [Globalization.CultureInfo]::InvariantCulture
$byPlayer = @{}

foreach ($line in [IO.File]::ReadLines($logPath)) {
    if ($line -notmatch $pattern) { continue }
    $index = [int]$Matches[2]
    if (-not $byPlayer.ContainsKey($index)) { $byPlayer[$index] = @() }
    $byPlayer[$index] += [pscustomobject]@{
        sample = [int]$Matches[1]
        alive = [int]$Matches[3]
        x = [double]::Parse($Matches[4], $culture)
        y = [double]::Parse($Matches[5], $culture)
        z = [double]::Parse($Matches[6], $culture)
        raw = $line
    }
}

function Zone([double]$x, [double]$y) {
    $xb = if ($x -lt -500) { "west" } elseif ($x -gt 500) { "east" } else { "central" }
    $yb = if ($y -lt 300) { "south" } elseif ($y -gt 1200) { "north" } else { "mid" }
    "$xb`_$yb"
}

$playerStats = @()
$routeLines = @()
$lifecycleLines = @()
$allPairs = @()
$totalSamples = 0
$totalUniquePositions = 0
$totalDistance = 0.0
$totalDeaths = 0
$totalRespawns = 0

foreach ($index in @($byPlayer.Keys | Sort-Object)) {
    $records = @($byPlayer[$index] | Sort-Object sample)
    $positions = @{}
    $zones = @{}
    $distance = 0.0
    $deaths = 0
    $respawns = 0
    for ($i = 0; $i -lt $records.Count; $i++) {
        $cur = $records[$i]
        $positions[('{0:F1},{1:F1},{2:F1}' -f $cur.x,$cur.y,$cur.z)] = $true
        $curZone = Zone $cur.x $cur.y
        $zones[$curZone] = $true
        if ($i -eq 0) { continue }
        $prev = $records[$i - 1]
        $dx = $cur.x - $prev.x; $dy = $cur.y - $prev.y; $dz = $cur.z - $prev.z
        $step = [Math]::Sqrt($dx*$dx + $dy*$dy + $dz*$dz)
        $distance += $step
        $prevZone = Zone $prev.x $prev.y
        if ($prev.alive -eq 1 -and $cur.alive -eq 0) {
            $deaths++
            $lifecycleLines += "CODEX_LIFECYCLE_OBSERVATION event=death_transition player_index=$index from_sample=$($prev.sample) to_sample=$($cur.sample) raw_log_sha256=$logHash"
        } elseif ($prev.alive -eq 0 -and $cur.alive -eq 1) {
            $respawns++
            $lifecycleLines += "CODEX_LIFECYCLE_OBSERVATION event=respawn_transition player_index=$index from_sample=$($prev.sample) to_sample=$($cur.sample) raw_log_sha256=$logHash"
        }
        if ($prev.alive -eq 1 -and $cur.alive -eq 1 -and $prevZone -ne $curZone -and $step -ge 32) {
            $pair = "$prevZone->$curZone"
            $allPairs += $pair
            $routeLines += ("CODEX_ROUTE_OBSERVATION player_index={0} from_sample={1} to_sample={2} from_zone={3} to_zone={4} distance={5:F3} raw_log_sha256={6}" -f $index,$prev.sample,$cur.sample,$prevZone,$curZone,$step,$logHash)
        }
    }
    $playerStats += [pscustomobject]@{
        playerIndex = [int]$index
        samples = $records.Count
        uniquePositions = $positions.Count
        zonesVisited = @($zones.Keys | Sort-Object)
        approximateDistance = [Math]::Round($distance,3)
        liveToDeadTransitions = $deaths
        deadToLiveTransitions = $respawns
    }
    $totalSamples += $records.Count
    $totalUniquePositions += $positions.Count
    $totalDistance += $distance
    $totalDeaths += $deaths
    $totalRespawns += $respawns
}

$routePath = Join-Path $EvidenceRoot "bot-route-observations.log"
$lifecyclePath = Join-Path $EvidenceRoot "bot-lifecycle-observations.log"
[IO.File]::WriteAllLines($routePath, $routeLines, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllLines($lifecyclePath, $lifecycleLines, [Text.UTF8Encoding]::new($false))

$summary = [pscustomobject]@{
    schemaVersion = 2
    sourceLog = $logPath
    sourceLogSha256 = $logHash
    analysisMethod = "one-second samples; zones west/central/east at x=-500/500 and south/mid/north at y=300/1200; route transitions require both samples alive and >=32 units displacement"
    players = $playerStats
    totals = [pscustomobject]@{
        players = $playerStats.Count
        samples = $totalSamples
        uniquePositions = $totalUniquePositions
        approximateDistance = [Math]::Round($totalDistance,3)
        liveToDeadTransitions = $totalDeaths
        deadToLiveTransitions = $totalRespawns
        routeTransitions = $routeLines.Count
        distinctRoutePairs = @($allPairs | Sort-Object -Unique)
    }
    routeObservationLog = $routePath
    routeObservationLogSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $routePath).Hash.ToLowerInvariant()
    lifecycleObservationLog = $lifecyclePath
    lifecycleObservationLogSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $lifecyclePath).Hash.ToLowerInvariant()
}
$summaryPath = Join-Path $EvidenceRoot "bot-route-analysis.json"
[IO.File]::WriteAllText($summaryPath, (($summary | ConvertTo-Json -Depth 6) + "`n"), [Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    analysis = $summaryPath
    sourceLogSha256 = $logHash
    players = $playerStats.Count
    samples = $totalSamples
    uniquePositions = $totalUniquePositions
    liveToDeadTransitions = $totalDeaths
    deadToLiveTransitions = $totalRespawns
    routeTransitions = $routeLines.Count
    distinctRoutePairs = @($allPairs | Sort-Object -Unique).Count
    routeObservationLogSha256 = $summary.routeObservationLogSha256
    lifecycleObservationLogSha256 = $summary.lifecycleObservationLogSha256
} | ConvertTo-Json -Depth 4
