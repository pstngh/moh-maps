$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$harness = Join-Path $root "run_door_instrument_probe.ps1"
$failed = Join-Path $root "failed-door-entity-scan-probe"
if (Test-Path -LiteralPath $failed) { throw "Refusing to overwrite $failed" }
New-Item -ItemType Directory -Path $failed -Force | Out-Null
foreach ($name in @("door-instrumented-report.json","door-instrumented.done.json","door-instrumented-qconsole.log","door-instrumented-engine.stdout.log","door-instrumented-engine.stderr.log","door-instrument-launch.stdout.log","door-instrument-launch.stderr.log")) {
    $source = Join-Path $root $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $failed }
}
$runtimeScript = "C:\tmp\codex-cache-r1-door-instrumented\home\main\maps\dm\codex_cache.scr"
if (Test-Path -LiteralPath $runtimeScript) { Copy-Item -LiteralPath $runtimeScript -Destination (Join-Path $failed "codex_cache.scr") }

$text = [IO.File]::ReadAllText($harness)
$old = @'
level.codex_door = NIL
local.i = 0
while (local.i < 512)
{
    local.ent = getentbyentnum local.i
    if (local.ent != NIL)
    {
        local.class = local.ent.classname
        local.distance = vector_length (local.ent.origin - ( 227 2058 1743 ))
        if (local.distance < 220)
            println ("CODEX_NEAR_DOOR entnum=" + local.ent.entnum + " classname=" + local.class + " distance=" + local.distance + " origin=" + local.ent.origin)
        if (local.class == "RotatingDoor")
            level.codex_door = local.ent
        if (local.class == "func_rotatingdoor")
            level.codex_door = local.ent
    }
    local.i++
}

if (level.codex_door == NIL)
{
    println "CODEX_DOOR_NOT_FOUND"
    end
}

'@
$new = @'
level.codex_door = getentbyentnum 24
if (level.codex_door.classname != "RotatingDoor")
{
    println ("CODEX_DOOR_IDENTITY_MISMATCH entnum=24 classname=" + level.codex_door.classname)
    end
}
local.distance = vector_length (level.codex_door.origin - ( 227 2058 1743 ))
println ("CODEX_NEAR_DOOR entnum=" + level.codex_door.entnum + " classname=" + level.codex_door.classname + " distance=" + local.distance + " origin=" + level.codex_door.origin)

'@
if (-not $text.Contains($old)) { throw "Expected broad scan block not found" }
$text = $text.Replace($old,$new)
[IO.File]::WriteAllText($harness,$text,[Text.UTF8Encoding]::new($false))
foreach ($name in @("door-instrumented-report.json","door-instrumented.done.json")) { $target=Join-Path $root $name; if(Test-Path -LiteralPath $target){Remove-Item -LiteralPath $target -Force} }
Write-Output "Preserved failed scan at $failed"
Write-Output "Updated $harness"
