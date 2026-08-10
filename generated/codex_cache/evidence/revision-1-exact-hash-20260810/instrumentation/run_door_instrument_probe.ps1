[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepositoryRoot,
    [Parameter(Mandatory = $true)][string]$EvidenceRoot,
    [int]$SampleSeconds = 55,
    [int]$Port = 12391
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [IO.Path]::GetFullPath($RepositoryRoot)
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$workRoot = Split-Path -Parent $RepositoryRoot
$candidate = Join-Path $RepositoryRoot "generated\codex_cache\codex_cache.pk3"
$retailMain = Join-Path $workRoot "runtime_base_stock\main"
$engine = Join-Path $workRoot "openmohaa-bin\runtime\omohaaded.exe"
$gameDll = Join-Path $workRoot "openmohaa-bin\runtime\game.dll"
$expectedCandidate = "90477f688e4115400813b119a2061434a1f62324381b3cc864fa7bab29084c53"
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash.ToLowerInvariant() -ne $expectedCandidate) { throw "Candidate hash mismatch" }

$qaRoot = [IO.Path]::GetFullPath("C:\tmp\codex-cache-r1-door-instrumented")
if (Test-Path -LiteralPath $qaRoot) { Remove-Item -LiteralPath $qaRoot -Recurse -Force }
$baseMain = Join-Path $qaRoot "base\main"
$homeMain = Join-Path $qaRoot "home\main"
$looseRoot = Join-Path $homeMain "maps\dm"
New-Item -ItemType Directory -Path $baseMain,$homeMain,$looseRoot -Force | Out-Null
foreach ($index in 0..6) {
    $source = Join-Path $retailMain ("Pak{0}.pk3" -f $index)
    $destination = Join-Path $baseMain (Split-Path -Leaf $source)
    try { New-Item -ItemType HardLink -Path $destination -Target $source -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $source -Destination $destination }
}
Copy-Item -LiteralPath $candidate -Destination (Join-Path $baseMain "zz_codex_cache.pk3")
$inventory = @(Get-ChildItem -LiteralPath $baseMain -Filter "*.pk3" -File | Sort-Object Name | ForEach-Object { [pscustomobject]@{ name=$_.Name; bytes=$_.Length; sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant(); path=$_.FullName } })
if ($inventory.Count -ne 8 -or ($inventory | Where-Object name -eq "zz_codex_cache.pk3").sha256 -ne $expectedCandidate) { throw "Door runtime identity mismatch" }

$script = @'
main:

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/codex_cache.scr
level waittill spawn
thread codex_door_probe
end

codex_door_probe:

wait 8
level.codex_door = getentbyentnum 24
if (level.codex_door.classname != "RotatingDoor")
{
    println ("CODEX_DOOR_IDENTITY_MISMATCH entnum=24 classname=" + level.codex_door.classname)
    end
}
local.distance = vector_length (level.codex_door.origin - ( 227 2058 1743 ))
println ("CODEX_NEAR_DOOR entnum=" + level.codex_door.entnum + " classname=" + level.codex_door.classname + " distance=" + local.distance + " origin=" + level.codex_door.origin)

println ("CODEX_DOOR_FOUND entnum=" + level.codex_door.entnum + " classname=" + level.codex_door.classname + " origin=" + level.codex_door.origin)
local.sample = 0
while (local.sample < 40)
{
    if (local.sample == 10)
    {
        println "CODEX_DOOR_COMMAND doopen"
        level.codex_door doopen $player[1]
    }
    if (local.sample == 20)
    {
        println "CODEX_DOOR_COMMAND doclose"
        level.codex_door doclose
    }
    println ("CODEX_DOOR_SAMPLE sample=" + local.sample + " angles=" + level.codex_door.angles + " isopen=" + level.codex_door.isOpen + " origin=" + level.codex_door.origin)
    local.sample++
    wait 1
}
println "CODEX_DOOR_PROBE_COMPLETE samples=40"
end
'@
$looseScript = Join-Path $looseRoot "codex_cache.scr"
[IO.File]::WriteAllText($looseScript,$script,[Text.UTF8Encoding]::new($false))
$arguments = @(
    "+set","fs_basepath",(Join-Path $qaRoot "base"),
    "+set","fs_homepath",(Join-Path $qaRoot "home"),
    "+set","dedicated","1",
    "+set","developer","2",
    "+set","logfile","2",
    "+set","cheats","1",
    "+set","net_port","$Port",
    "+set","g_gametype","1",
    "+set","sv_maxclients","16",
    "+set","sv_maxbots","8",
    "+set","sv_numbots","8",
    "+map","dm/codex_cache"
)
$stdoutPath = Join-Path $EvidenceRoot "door-instrumented-engine.stdout.log"
$stderrPath = Join-Path $EvidenceRoot "door-instrumented-engine.stderr.log"
$timer=[Diagnostics.Stopwatch]::StartNew()
$process=Start-Process -FilePath $engine -ArgumentList $arguments -WorkingDirectory (Split-Path -Parent $engine) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
try { Start-Sleep -Seconds $SampleSeconds }
finally { if(-not $process.HasExited){$process.Kill()}; [void]$process.WaitForExit(5000); $timer.Stop() }

$runtimeLog=Join-Path $homeMain "qconsole.log"
$logPath=Join-Path $EvidenceRoot "door-instrumented-qconsole.log"
Copy-Item -LiteralPath $runtimeLog -Destination $logPath -Force
$found=@(Select-String -LiteralPath $logPath -Pattern "CODEX_DOOR_FOUND")
$samples=@(Select-String -LiteralPath $logPath -Pattern "CODEX_DOOR_SAMPLE sample=")
$near=@(Select-String -LiteralPath $logPath -Pattern "CODEX_NEAR_DOOR")
$errors=@(Select-String -LiteralPath $logPath -Pattern "Script Error")
$commands=@(Select-String -LiteralPath $logPath -Pattern "CODEX_DOOR_COMMAND")
$report=[pscustomobject]@{
    schemaVersion=1
    lane="supplemental-controlled-door-instrumentation-not-package-pure"
    mapName="codex_cache"
    qaRoot=$qaRoot
    candidateSha256=$expectedCandidate
    runtimeCandidateSha256=($inventory|Where-Object name -eq "zz_codex_cache.pk3").sha256
    exactPk3Count=$inventory.Count
    packageInventory=$inventory
    engineSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $engine).Hash.ToLowerInvariant()
    gameDllSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $gameDll).Hash.ToLowerInvariant()
    looseScriptPath=$looseScript
    looseScriptSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $looseScript).Hash.ToLowerInvariant()
    controlledEvents=@("doopen at sample 10 using bot player 1 as opener","doclose at sample 20")
    elapsedSeconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)
    foundLines=$found.Count
    nearDoorLines=$near.Count
    doorSampleLines=$samples.Count
    commandLines=$commands.Count
    scriptErrorCount=$errors.Count
    runtimeLog=$logPath
    runtimeLogSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $logPath).Hash.ToLowerInvariant()
    stdoutLog=$stdoutPath
    stderrLog=$stderrPath
}
$reportPath=Join-Path $EvidenceRoot "door-instrumented-report.json"
[IO.File]::WriteAllText($reportPath,(($report|ConvertTo-Json -Depth 7)+"`n"),[Text.UTF8Encoding]::new($false))
$donePath=Join-Path $EvidenceRoot "door-instrumented.done.json"
[IO.File]::WriteAllText($donePath,(([pscustomobject]@{report=$reportPath;foundLines=$report.foundLines;doorSampleLines=$report.doorSampleLines;scriptErrorCount=$report.scriptErrorCount}|ConvertTo-Json)+"`n"),[Text.UTF8Encoding]::new($false))
[pscustomobject]@{report=$reportPath;foundLines=$report.foundLines;doorSampleLines=$report.doorSampleLines;scriptErrorCount=$report.scriptErrorCount}|ConvertTo-Json
