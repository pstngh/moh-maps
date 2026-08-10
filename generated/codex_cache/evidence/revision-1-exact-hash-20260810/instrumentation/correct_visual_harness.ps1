$ErrorActionPreference = "Stop"
$path = Join-Path $PSScriptRoot "run_visual_probe.ps1"
$text = Get-Content -Raw -LiteralPath $path

$text = $text.Replace(
    "    `"thread evidence_probe`",`r`n    `"thread bot_and_door_samples`",`r`n",
    "    `"thread evidence_probe`",`r`n"
)
$text = $text.Replace(
    "    `"thread evidence_probe`",`n    `"thread bot_and_door_samples`",`n",
    "    `"thread evidence_probe`",`n"
)

$blockPattern = '(?s)\[void\]\$scriptLines\.Add\("wait 72"\)\r?\n\[void\]\$scriptLines\.Add\(''\$player stufftext "quit"''\)\r?\n\[void\]\$scriptLines\.Add\("end"\)\r?\n\[void\]\$scriptLines\.Add\(""\)\r?\n\[void\]\$scriptLines\.Add\("bot_and_door_samples:"\).*?\[void\]\$scriptLines\.Add\("end"\)\r?\n\r?\n\$looseScript'
$blockReplacement = @'
[void]$scriptLines.Add("wait 1")
[void]$scriptLines.Add('$player stufftext "quit"')
[void]$scriptLines.Add("end")

$looseScript
'@
$updated = [regex]::Replace($text, $blockPattern, $blockReplacement)
if ($updated -eq $text) { throw "Bot instrumentation block was not found" }
$text = $updated

$text = $text.Replace(
    "    `"+set`", `"sv_maxclients`", `"16`",`r`n    `"+set`", `"sv_maxbots`", `"8`",`r`n    `"+set`", `"sv_numbots`", `"8`",`r`n",
    ""
)
$text = $text.Replace(
    "    `"+set`", `"sv_maxclients`", `"16`",`n    `"+set`", `"sv_maxbots`", `"8`",`n    `"+set`", `"sv_numbots`", `"8`",`n",
    ""
)
$text = $text.Replace(
    "camera, modal-dismissal, bot-position, and door-angle instrumentation",
    "fixed-camera and modal-dismissal instrumentation"
)
$text = [regex]::Replace($text, '(?m)^    botSampleCount = .*\r?\n', '')
$text = [regex]::Replace($text, '(?m)^    doorSampleCount = .*\r?\n', '')
$text = [regex]::Replace($text, '(?m)^    botProbeComplete = .*\r?\n', '')

if ($text -match 'bot_and_door_samples|sv_numbots|botSampleCount|doorSampleCount') {
    throw "Visual harness still contains mixed bot-lane code"
}
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
